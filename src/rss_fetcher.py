import json
import hashlib
import logging
from typing import Dict, List, Optional
import requests

from config import Config
from utils import get_retry_session, clean_html

logger = logging.getLogger(__name__)


class NetworkError(Exception):
    """Raised when network operations fail after retries."""

    pass


def validate_rss_data(data: dict) -> None:
    """Validate RSS feed data structure."""
    if not isinstance(data, dict):
        raise ValueError("RSS data must be a dictionary")

    if "items" not in data:
        raise ValueError("RSS data missing 'items' field")

    items = data.get("items", [])
    if not isinstance(items, list):
        raise ValueError("RSS 'items' must be a list")

    if len(items) == 0:
        raise ValueError("RSS feed contains no items")

    logger.info(f"RSS feed validated: {len(items)} items found")


def fetch_author_blogs(
    rss_api_url: str, config: Config, session: Optional[requests.Session] = None
) -> Dict[str, str]:
    """
    Fetch and parse author blogs from RSS feed.

    Returns:
        Dictionary mapping author names to their concatenated blog content
    """
    if session is None:
        session = get_retry_session(config)

    # Check cache first
    cache_key = hashlib.md5(rss_api_url.encode()).hexdigest()
    cache_file = config.cache_dir / f"rss_{cache_key}.json"

    if config.enable_cache and cache_file.exists():
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                cached_data = json.load(f)
                logger.info(f"Loaded author blogs from cache: {cache_file}")
                return cached_data
        except Exception as e:
            logger.warning(f"Cache read failed: {e}")

    try:
        logger.info(f"Fetching RSS feed from: {rss_api_url}")
        resp = session.get(rss_api_url, timeout=config.request_timeout)
        resp.raise_for_status()
        data = resp.json()
        validate_rss_data(data)

    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch RSS feed: {e}")
        raise NetworkError(f"RSS feed fetch failed: {e}") from e
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in RSS response: {e}")
        raise ValueError(f"RSS feed returned invalid JSON: {e}") from e

    # Process items
    author_blogs_temp: Dict[str, List[str]] = {}
    processed_items = 0

    for item in data.get("items", []):
        author = item.get("author", "").strip() or "unknown_author"

        content = (
            item.get("content")
            or item.get("content:encoded")
            or item.get("description", "")
        )

        text = clean_html(content)

        if not text or len(text) < 50:
            continue

        if len(text) > 50000:
            text = text[:50000]
            logger.warning(f"Truncated oversized content from {author}")

        author_blogs_temp.setdefault(author, []).append(text)
        processed_items += 1

    if not author_blogs_temp:
        raise ValueError("No valid blog content extracted from RSS feed")

    # Concatenate blogs per author
    author_blogs: Dict[str, str] = {
        author: "\n\n".join(texts) for author, texts in author_blogs_temp.items()
    }

    logger.info(f"Processed {processed_items} items from {len(author_blogs)} authors")

    # Cache the results
    if config.enable_cache:
        try:
            config.cache_dir.mkdir(parents=True, exist_ok=True)
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(author_blogs, f, ensure_ascii=False, indent=2)
            logger.info(f"Cached author blogs to: {cache_file}")
        except Exception as e:
            logger.warning(f"Cache write failed: {e}")

    return author_blogs
