import os
import logging
from typing import Any
from google.adk.agents import Agent, SequentialAgent
from google.adk.models.google_llm import Gemini
from pydantic import PrivateAttr

from config import Config
from utils import get_retry_session
from style_pipeline import style_refinement_pipeline

logger = logging.getLogger(__name__)


def build_retry_config(config: Config) -> dict:
    """Build retry configuration for Gemini API."""
    return {
        "attempts": config.retry_attempts,
        "exp_base": config.retry_base,
        "initial_delay": config.initial_delay,
        "http_status_codes": config.retry_status_codes,
    }


def build_outline_agent(config: Config) -> Agent:
    """Build outline generation agent."""
    return Agent(
        name="OutlineAgent",
        model=Gemini(
            model=config.gemini_model, retry_options=build_retry_config(config)
        ),
        instruction="""Create a clear, structured blog outline for the given topic.

Include:
1. A compelling, specific headline
2. An engaging introduction hook (4-5 sentences)
3. 4-5 main sections with:
   - Clear section titles
   - 5-6 bullet points per section outlining key points
4. Section titles must have architecture and code overview if topics are technical to software, IT.
4. A memorable concluding thought

Make the outline actionable and specific.""",
        output_key="blog_outline",
    )


def build_writer_agent(config: Config) -> Agent:
    """Build blog writer agent."""
    return Agent(
        name="WriterAgent",
        model=Gemini(
            model=config.gemini_model, retry_options=build_retry_config(config)
        ),
        instruction=f"""Write a blog post following this outline: {{blog_outline}}

Requirements:
- Length: {config.min_word_count}-{config.max_word_count} words
- Tone: Engaging, informative, and conversational
- Structure: Follow the outline sections exactly
- Style: Clear, concise, with specific examples where relevant
- Formatting: Use headings, bullet points, and short paragraphs for readability
- Grammar: Perfect grammar, spelling, and punctuation
- Design: Draw design and architectural workflow diagrams where applicable
- Code: Include code snippets in appropriate programming languages where relevant; preferebly Python

Write the complete blog post now.""",
        output_key="blog_draft",
    )


def build_editor_agent(config: Config) -> Agent:
    """Build standalone editor agent."""
    return Agent(
        name="EditorAgent",
        model=Gemini(
            model=config.gemini_model, retry_options=build_retry_config(config)
        ),
        instruction="""Polish this blog post for grammar, flow, clarity, and readability.

Preserve the author's voice and style. Return ONLY the polished blog post.""",
        output_key="final_blog",
    )


def build_pipeline_without_style(rss_api_url: str, config: Config) -> SequentialAgent:
    """Build pipeline with outline and writer only (no style agent)."""
    outline_agent = build_outline_agent(config)
    writer_agent = build_writer_agent(config)

    return SequentialAgent(
        name="BlogPipeline", sub_agents=[outline_agent, writer_agent]
    )


class StyleRefinementAgent(Agent):
    """
    Wrapper agent that calls the style refinement function.
    This integrates with SequentialAgent while giving us full control.
    """

    _rss_api_url: str = PrivateAttr()
    _config: Config = PrivateAttr()
    _session: Any = PrivateAttr()

    def __init__(self, rss_api_url: str, config: Config):
        self._rss_api_url = rss_api_url
        self._config = config
        self._session = get_retry_session(config)

        if not os.getenv("GOOGLE_API_KEY"):
            raise RuntimeError("GOOGLE_API_KEY environment variable must be set")

        logger.info(
            f"StyleRefinementAgent initialized (threshold: {config.similarity_threshold})"
        )

        super().__init__(
            name="StyleRefinementAgent",
            model=None,
            instruction="",
            output_key="styled_blog",
        )

    def __del__(self):
        """Cleanup resources."""
        if hasattr(self, "_session") and self._session:
            self._session.close()

    async def __call__(self, state: dict, **kwargs) -> dict:
        """Make the agent callable."""
        logger.info("StyleRefinementAgent.__call__() invoked")
        return await self.forward(state)

    async def forward(self, state: dict) -> dict:
        """Forward method called by SequentialAgent."""
        logger.info("=" * 60)
        logger.info("StyleRefinementAgent.forward() CALLED")
        logger.info("=" * 60)

        # Extract draft from state
        draft = state.get("blog_draft", "").strip()

        # Fallback: check nested states
        if not draft:
            for key in ["WriterAgent", "writer_agent"]:
                if key in state:
                    draft = state[key].get("blog_draft", "").strip()
                    if draft:
                        logger.info(f"Found draft in nested state: {key}")
                        break

        if not draft:
            logger.error("No blog draft found in state")
            logger.debug(f"Available state keys: {list(state.keys())}")
            state["styled_blog"] = ""
            state["style_similarity"] = 0.0
            state["rewrite_attempts"] = 0
            state["closest_author"] = None
            return state

        logger.info("Calling style refinement pipeline...")
        result = await style_refinement_pipeline(
            draft=draft,
            rss_api_url=self._rss_api_url,
            config=self._config,
            session=self._session,
        )

        logger.info(
            f"Style refinement returned: similarity={result.get('style_similarity', 0):.4f}"
        )
        state.update(result)

        return state

    async def run(self, *args, **kwargs):
        """Override run() as well in case that's what gets called."""
        logger.info("StyleRefinementAgent.run() CALLED")
        if args:
            state = args[0] if isinstance(args[0], dict) else {}
        else:
            state = kwargs.get("state", {}) or kwargs.get("context", {})

        return await self.forward(state)
