import hashlib
import logging
from typing import Dict, Tuple
import numpy as np
from sentence_transformers import SentenceTransformer

from config import Config
from utils import chunk_text

logger = logging.getLogger(__name__)


class AuthorStyleModel:
    """Manages author style embeddings and similarity computations."""

    def __init__(self, config: Config, emb_model_name: str = "all-MiniLM-L6-v2"):
        self.config = config
        self.emb_model_name = emb_model_name
        self.encoder = None
        self.centroids: Dict[str, np.ndarray] = {}
        self._embedding_cache: Dict[str, np.ndarray] = {}
        self._cache_hits = 0
        self._cache_misses = 0

    def _get_encoder(self) -> SentenceTransformer:
        """Lazy load the sentence transformer model."""
        if self.encoder is None:
            logger.info(f"Loading embedding model: {self.emb_model_name}")
            self.encoder = SentenceTransformer(self.emb_model_name)
        return self.encoder

    def _embed_and_normalize(self, text: str) -> np.ndarray:
        """Embed text and normalize to unit vector."""
        cache_key = hashlib.md5(text.encode()).hexdigest()
        if cache_key in self._embedding_cache:
            self._cache_hits += 1
            return self._embedding_cache[cache_key]

        self._cache_misses += 1
        encoder = self._get_encoder()
        emb = encoder.encode([text], show_progress_bar=False)[0]

        norm = np.linalg.norm(emb)
        if norm > 0:
            emb = emb / norm

        if len(self._embedding_cache) < 1000:
            self._embedding_cache[cache_key] = emb
        else:
            logger.debug("Embedding cache full, not caching new embeddings")

        return emb

    def clear_cache(self) -> None:
        """Clear embedding cache to free memory."""
        cache_size = len(self._embedding_cache)
        self._embedding_cache.clear()
        logger.info(
            f"Cleared embedding cache: {cache_size} entries "
            f"(hits: {self._cache_hits}, misses: {self._cache_misses})"
        )
        self._cache_hits = 0
        self._cache_misses = 0

    def build_centroids(self, author_blogs_dict: Dict[str, str]) -> None:
        """Build centroid embeddings for all authors."""
        if not author_blogs_dict:
            raise ValueError("Cannot build centroids: no author data provided")

        self.centroids = {}

        for author, all_text in author_blogs_dict.items():
            try:
                chunks = chunk_text(all_text, self.config)

                if not chunks:
                    logger.warning(f"No chunks for author '{author}', skipping")
                    continue

                encoder = self._get_encoder()
                embeddings = encoder.encode(chunks, show_progress_bar=False)

                centroid = np.mean(embeddings, axis=0)
                norm = np.linalg.norm(centroid)

                if norm > 0:
                    centroid = centroid / norm
                else:
                    logger.warning(f"Zero norm centroid for '{author}', skipping")
                    continue

                self.centroids[author] = centroid
                logger.info(f"Built centroid for '{author}': {len(chunks)} chunks")

            except Exception as e:
                logger.error(f"Failed to build centroid for '{author}': {e}")
                continue

        if not self.centroids:
            raise ValueError("Failed to build any valid centroids")

        logger.info(f"Successfully built {len(self.centroids)} author centroids")

    def similarity_to_author(self, text: str, author_id: str) -> float:
        """Compute cosine similarity of text to a specific author's style."""
        if author_id not in self.centroids:
            available = list(self.centroids.keys())
            raise ValueError(
                f"Author '{author_id}' not found. Available authors: {available}"
            )

        emb = self._embed_and_normalize(text)
        score = float(np.dot(emb, self.centroids[author_id]))
        return score

    def find_closest_author(self, text: str) -> Tuple[str, float]:
        """Find the author with the most similar style."""
        if not self.centroids:
            raise RuntimeError("No centroids available. Call build_centroids() first.")

        emb = self._embed_and_normalize(text)

        best_author = None
        best_score = -1.0

        for author, centroid in self.centroids.items():
            score = float(np.dot(emb, centroid))
            if score > best_score:
                best_author = author
                best_score = score

        logger.info(f"Closest author: '{best_author}' (similarity: {best_score:.4f})")
        return best_author, best_score
