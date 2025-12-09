from dataclasses import dataclass, field
from pathlib import Path
from typing import List


@dataclass
class Config:
    """Centralized configuration with documented parameters."""

    rss_feed = "https://api.rss2json.com/v1/api.json?rss_url=https://medium.com/feed/@saurabh2.mishra"

    # Text chunking
    chunk_size: int = 500
    chunk_overlap: int = 50

    # Style matching
    similarity_threshold: float = 0.80
    max_rewrite_attempts: int = 3
    style_example_length: int = 4000

    # Style analysis features
    use_multiple_style_examples: bool = True
    num_style_examples: int = 3
    extract_style_features: bool = True
    use_detailed_style_prompt: bool = True

    # Multi-modal similarity scoring
    use_llm_similarity: bool = True
    use_embedding_similarity: bool = True
    llm_similarity_weight: float = 0.6
    embedding_similarity_weight: float = 0.4
    llm_similarity_model: str = "gemini-2.5-flash-lite"
    cache_llm_scores: bool = True

    # API settings
    gemini_model: str = "gemini-2.5-flash-lite"
    max_output_tokens: int = 1024
    retry_attempts: int = 5
    retry_base: int = 7
    initial_delay: float = 1.0

    # Content validation
    min_word_count: int = 150
    max_word_count: int = 400

    # Network
    request_timeout: int = 20
    retry_status_codes: List[int] = field(default_factory=lambda: [429, 500, 503, 504])

    # Caching
    cache_dir: Path = field(default_factory=lambda: Path("cache"))
    enable_cache: bool = True
