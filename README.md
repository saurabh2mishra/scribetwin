# ScribeTwin : AI Blog writer that sounds like you.

![ScribeTwin](static/scribetwin.webp)

I started this project out of curiosity. I wanted to build a small, fun AI application to see an agent in action. The core idea is to teach the agent to copy my writing style. After a few days of fun, vibecodeed experimentation with multi-agent systems, I'm happy with the result!

This is ScribeTwin, a smart, personalized blog generator. It orchestrates multiple specialized AI agents to create content that seamlessly matches your unique voice.


## Setup

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
2. **Set up environment variables:**
Create a `.env` file in the project root:
```env
GOOGLE_API_KEY=your_google_api_key
# Add other required configuration
```

4. **Run the application:**
```bash
source ./start.sh
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
3. Provide a custom RSS feed URL for style matching. For example I have used my personal MEDIUM BLOG feed.
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