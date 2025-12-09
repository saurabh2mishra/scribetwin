# ScribeTwin :  AI-Powered Personalized Blog Writer

**Write blogs that sound like you, powered by advanced AI agents and style analysis.**

![ScribeTwin](static/scribetwin.webp)

ScribeTwin is an intelligent blog generation `toy application` that uses multi-agent AI systems to create content that matches your unique writing style. ScribeTwin orchestrates multiple specialized AI agents to produce high-quality, personalized blog posts.

## Key Features

### Multi-Agent Architecture
- **OutlineAgent**: Creates structured, compelling blog outlines with engaging hooks and clear sections
- **WriterAgent**: Transforms outlines into comprehensive, well-written blog content
- **StyleRefinementPipeline**: Analyzes author writing style and iteratively refines content to match it
- **EditorAgent**: Polishes and refines content for grammar, clarity, and flow


### Intelligent Style Matching
- **Author Style Learning**: Analyzes RSS feeds to extract writing patterns, tone, and vocabulary
- **Semantic Embeddings**: Uses sentence transformers to understand writing style at a deep level
- **Iterative Refinement**: Continuously improves content similarity with your unique voice
- **Multi-Modal Scoring**: Combines LLM-based and embedding-based similarity metrics for accurate matching

### Real-Time WebSocket Communication
- Live status updates as content is being generated
- Stream agent responses and refinement progress
- Interactive feedback loop between user and AI agents

### RSS Feed Integration
- Automatic fetching of author blogs from RSS feeds
- Caching system for efficient style analysis
- Support for custom RSS feed sources (e.g., Medium, personal blogs)

### Web Interface
- Clean, responsive UI for blog generation
- Real-time progress tracking
- Generated content preview and download

## 🚀 Quick Start

### Prerequisites
- Python 3.9+
- [uv](https://github.com/astral-sh/uv) package manager
- Google API credentials for Gemini
- Environment variables configured

### Installation

1. **Clone the repository:**
```bash
git clone https://github.com/saurabh2mishra/scribetwin.git
cd scribetwin
```

2. **Install dependencies using uv:**
```bash
uv sync
```

3. **Set up environment variables:**
Create a `.env` file in the project root:
```env
GOOGLE_API_KEY=your_google_api_key
# Add other required configuration
```

4. **Run the application:**
```bash
uv run python src/app.py
```

The application will start on `http://localhost:8000`


### Agent Workflow
```
User Input (Topic + RSS Feed)
    ↓
[OutlineAgent] → Creates structured outline
    ↓
[WriterAgent] → Generates full blog content
    ↓
[StyleRefinementPipeline] → Matches your writing style
    ↓
[EditorAgent] → Polishes and refines
    ↓
Final Personalized Blog Post
```

### Style Matching Process
1. **Style Extraction**: Analyzes author blogs to extract writing characteristics
   - Sentence structure and length
   - Vocabulary preferences
   - Tone and voice
   - Grammar and punctuation patterns

2. **Embedding-Based Analysis**: Converts style samples into semantic vectors using sentence transformers

3. **Iterative Refinement**: 
   - Compares generated content with author style using multi-modal metrics
   - Rewrites content to improve similarity
   - Validates against word count and quality constraints
   - Stops when similarity threshold is reached

### Web Interface
1. Navigate to `http://localhost:8000`
2. Enter your blog topic
3. (Optional) Provide a custom RSS feed URL for style matching
4. Click "Generate Blog"
5. Watch real-time progress as agents work
6. Download or copy your personalized blog post

### Via API
```python
import asyncio
from app import app
from agents import build_pipeline_without_style

async def generate_blog():
    config = Config()
    pipeline = build_pipeline_without_style(
        rss_api_url=config.rss_feed,
        config=config
    )
    # Execute pipeline...
```
## 📝 License

This project is open source and available under the MIT License.

## 🤝 Contributing

Clone and Code. If you want to add more features, feel free to do it. 

---

**Made with ❤️ for writers who want their AI to match their voice.**
