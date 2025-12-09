import logging
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from dotenv import load_dotenv

from config import Config
from agents import build_pipeline_without_style, build_editor_agent
from style_pipeline import style_refinement_pipeline
from style_analysis import extract_style_features
from utils import validate_content, safe_get_nested
from google.adk.runners import InMemoryRunner

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

load_dotenv()

app = FastAPI(title="ScribeTwin - Personalized Blog Writer")

# Serve static files
app.mount("/static", StaticFiles(directory="static"), name="static")


class BlogRequest(BaseModel):
    topic: str
    rss_feed: str = Config.rss_feed


class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_status(self, websocket: WebSocket, data: dict):
        try:
            await websocket.send_json(data)
        except Exception as e:
            logger.error(f"Error sending status: {e}")


manager = ConnectionManager()


@app.get("/")
async def read_root():
    return FileResponse("static/index.html")


@app.websocket("/ws/generate")
async def websocket_generate(websocket: WebSocket):
    await manager.connect(websocket)

    try:
        # Receive blog request
        data = await websocket.receive_json()
        topic = data.get("topic", "")
        rss_feed = data.get("rss_feed", Config.rss_feed)

        if not topic:
            await manager.send_status(
                websocket, {"type": "error", "message": "Topic is required"}
            )
            return

        # Initialize config
        config = Config(
            similarity_threshold=0.65,
            max_rewrite_attempts=4,
            style_example_length=4000,
            use_multiple_style_examples=True,
            num_style_examples=3,
            extract_style_features=True,
            use_detailed_style_prompt=True,
            use_llm_similarity=True,
            use_embedding_similarity=True,
            llm_similarity_weight=0.6,
            embedding_similarity_weight=0.4,
            cache_llm_scores=True,
            max_output_tokens=1024,
            enable_cache=True,
        )

        # Send initial status
        await manager.send_status(
            websocket,
            {
                "type": "status",
                "stage": "starting",
                "message": "Initializing blog generation pipeline...",
            },
        )

        # Stage 1: Outline Agent
        await manager.send_status(
            websocket,
            {
                "type": "status",
                "stage": "outline",
                "message": "Creating blog outline...",
            },
        )

        # Stage 2: Writer Agent
        await manager.send_status(
            websocket,
            {"type": "status", "stage": "writer", "message": "Writing blog draft..."},
        )

        # Build and run pipeline
        pipeline_without_style = build_pipeline_without_style(rss_feed, config)
        runner = InMemoryRunner(agent=pipeline_without_style)

        result = await runner.run_debug(f"Write a blog post about {topic}")

        # Extract draft
        if isinstance(result, list):
            final_state = result[-1] if result else {}
        else:
            final_state = result

        if hasattr(final_state, "model_dump"):
            final_state = final_state.model_dump()
        elif hasattr(final_state, "dict"):
            final_state = final_state.dict()

        blog_draft = (
            safe_get_nested(final_state, "actions", "state_delta", "blog_draft")
            or safe_get_nested(final_state, "blog_draft")
            or safe_get_nested(final_state, "WriterAgent", "blog_draft")
            or ""
        )

        if not blog_draft:
            await manager.send_status(
                websocket, {"type": "error", "message": "Failed to generate blog draft"}
            )
            return

        await manager.send_status(
            websocket,
            {
                "type": "progress",
                "draft_length": len(blog_draft),
                "word_count": len(blog_draft.split()),
            },
        )

        # Stage 3: Style Agent
        await manager.send_status(
            websocket,
            {
                "type": "status",
                "stage": "style",
                "message": "Applying style refinement...",
            },
        )

        try:
            style_result = await style_refinement_pipeline(
                draft=blog_draft, rss_api_url=rss_feed, config=config
            )
        except Exception as e:
            logger.error(f"Style refinement failed: {e}")
            style_result = {
                "styled_blog": blog_draft,
                "style_similarity": 0.0,
                "embedding_similarity": None,
                "llm_similarity": None,
                "rewrite_attempts": 0,
                "closest_author": "unknown",
                "error": str(e),
                "success": False,
            }

        styled_blog = style_result.get("styled_blog", blog_draft)
        style_similarity = style_result.get("style_similarity", 0.0)
        rewrite_attempts = style_result.get("rewrite_attempts", 0)
        closest_author = style_result.get("closest_author", "unknown")
        embedding_sim = style_result.get("embedding_similarity")
        llm_sim = style_result.get("llm_similarity")

        logger.info(
            f"Style result - Combined: {style_similarity if style_similarity is not None else 'N/A'}, "
            f"Embedding: {embedding_sim if embedding_sim is not None else 'N/A'}, "
            f"LLM: {llm_sim if llm_sim is not None else 'N/A'}, "
            f"Author: {closest_author}, Attempts: {rewrite_attempts}"
        )

        await manager.send_status(
            websocket,
            {
                "type": "similarity",
                "combined_similarity": (
                    float(style_similarity) if style_similarity is not None else 0.0
                ),
                "embedding_similarity": (
                    float(embedding_sim) if embedding_sim is not None else None
                ),
                "llm_similarity": float(llm_sim) if llm_sim is not None else None,
                "rewrite_attempts": rewrite_attempts,
                "author": closest_author,
            },
        )

        # Stage 4: Editor Agent
        await manager.send_status(
            websocket,
            {"type": "status", "stage": "editor", "message": "Polishing final blog..."},
        )

        editor_agent = build_editor_agent(config)
        editor_runner = InMemoryRunner(agent=editor_agent)

        editor_result = await editor_runner.run_debug(
            f"Edit and polish this blog post:\n\n{styled_blog}"
        )

        # Extract final blog
        if isinstance(editor_result, list):
            editor_state = editor_result[-1] if editor_result else {}
        else:
            editor_state = editor_result

        if hasattr(editor_state, "model_dump"):
            editor_state = editor_state.model_dump()
        elif hasattr(editor_state, "dict"):
            editor_state = editor_state.dict()

        blog_content = (
            safe_get_nested(editor_state, "actions", "state_delta", "final_blog")
            or safe_get_nested(editor_state, "final_blog")
            or safe_get_nested(editor_state, "content", "parts", 0, "text")
            or styled_blog
        )

        # Validate and send final result
        is_valid, error_msg = validate_content(blog_content, config)

        await manager.send_status(
            websocket,
            {
                "type": "complete",
                "stage": "complete",
                "message": "Blog generation complete!",
                "blog": blog_content,
                "metadata": {
                    "author": closest_author,
                    "combined_similarity": (
                        float(style_similarity) if style_similarity is not None else 0.0
                    ),
                    "embedding_similarity": (
                        float(embedding_sim) if embedding_sim is not None else None
                    ),
                    "llm_similarity": float(llm_sim) if llm_sim is not None else None,
                    "rewrite_attempts": rewrite_attempts,
                    "word_count": len(blog_content.split()),
                    "validated": is_valid,
                },
            },
        )

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.error(f"Error in websocket: {e}", exc_info=True)
        try:
            await manager.send_status(websocket, {"type": "error", "message": str(e)})
        except:
            pass
    finally:
        manager.disconnect(websocket)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
