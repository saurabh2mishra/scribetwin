import logging
from typing import List, Any, Tuple
from bs4 import BeautifulSoup
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config import Config

logger = logging.getLogger(__name__)


def get_retry_session(config: Config) -> requests.Session:
    """Create a requests session with retry logic."""
    session = requests.Session()
    retry_strategy = Retry(
        total=config.retry_attempts,
        backoff_factor=config.initial_delay,
        status_forcelist=config.retry_status_codes,
        allowed_methods=["GET", "POST"],
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


def clean_html(html_text: str) -> str:
    """Clean HTML and extract text content safely."""
    if not html_text:
        return ""

    try:
        soup = BeautifulSoup(html_text, "html.parser")
        for tag in soup(["script", "style", "meta", "link", "noscript"]):
            tag.decompose()
        text = soup.get_text(separator=" ", strip=True)
        return " ".join(text.split())
    except Exception as e:
        logger.warning(f"HTML cleaning failed: {e}")
        return ""


def chunk_text(text: str, config: Config) -> List[str]:
    """Split text into overlapping chunks for embedding."""
    if not text:
        return []

    words = text.split()
    if len(words) <= config.chunk_size:
        return [text]

    chunks = []
    i = 0
    while i < len(words):
        chunk_words = words[i : i + config.chunk_size]
        chunks.append(" ".join(chunk_words))
        i += config.chunk_size - config.chunk_overlap

    logger.debug(f"Created {len(chunks)} chunks from {len(words)} words")
    return chunks


def validate_content(
    text: str, config: Config, check_word_count: bool = True
) -> Tuple[bool, str]:
    """Validate blog content quality."""
    if not text or not text.strip():
        return False, "Content is empty"

    word_count = len(text.split())

    if check_word_count:
        if word_count < config.min_word_count:
            return (
                False,
                f"Content too short: {word_count} words (min: {config.min_word_count})",
            )
        if word_count > config.max_word_count:
            return (
                False,
                f"Content too long: {word_count} words (max: {config.max_word_count})",
            )

    unique_words = len(set(text.lower().split()))
    if unique_words < word_count * 0.3:
        return False, "Content appears repetitive"

    return True, ""


def safe_get_nested(data: Any, *keys: str, default: Any = None) -> Any:
    """Safely extract nested dictionary values."""
    current = data
    for key in keys:
        if current is None:
            return default

        if isinstance(current, dict):
            current = current.get(key)
        elif hasattr(current, key):
            current = getattr(current, key)
        else:
            return default

    return current if current is not None else default
