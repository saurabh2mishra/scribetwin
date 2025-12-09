import logging
from typing import Dict, List, Any, Tuple, Optional

from config import Config
from embedding_model import AuthorStyleModel
from llm_services import llm_similarity_score

logger = logging.getLogger(__name__)


class MultiModalStyleModel:
    """Combines embedding-based and LLM-based similarity scoring."""

    def __init__(
        self, config: Config, embedding_model: Optional[AuthorStyleModel] = None
    ):
        self.config = config
        self.embedding_model = embedding_model or AuthorStyleModel(config)

    async def compute_similarity(
        self, text: str, author_id: str, style_examples: List[str]
    ) -> Dict[str, Any]:
        """Compute multi-modal similarity combining embeddings and LLM scoring."""
        results = {
            "embedding_score": None,
            "llm_score": None,
            "combined_score": 0.0,
            "llm_reasoning": "",
            "method_used": [],
        }

        # 1. Embedding-based similarity
        if self.config.use_embedding_similarity:
            try:
                embedding_score = self.embedding_model.similarity_to_author(
                    text, author_id
                )
                results["embedding_score"] = float(embedding_score)
                results["method_used"].append("embedding")
                logger.debug(f"Embedding similarity: {embedding_score:.4f}")
            except Exception as e:
                logger.warning(f"Embedding similarity failed: {e}")
                results["embedding_score"] = None

        # 2. LLM-based similarity
        if self.config.use_llm_similarity:
            try:
                llm_score, reasoning = await llm_similarity_score(
                    text, style_examples, self.config, author_name=author_id
                )
                results["llm_score"] = float(llm_score)
                results["llm_reasoning"] = reasoning
                results["method_used"].append("llm")
                logger.debug(f"LLM similarity: {llm_score:.4f}")
            except Exception as e:
                logger.warning(f"LLM similarity failed: {e}")
                results["llm_score"] = None

        # 3. Combine scores with weighted average
        scores_to_combine = []
        weights_to_use = []

        if results["embedding_score"] is not None:
            scores_to_combine.append(results["embedding_score"])
            weights_to_use.append(self.config.embedding_similarity_weight)

        if results["llm_score"] is not None:
            scores_to_combine.append(results["llm_score"])
            weights_to_use.append(self.config.llm_similarity_weight)

        if scores_to_combine:
            total_weight = sum(weights_to_use)
            normalized_weights = [w / total_weight for w in weights_to_use]
            combined = sum(s * w for s, w in zip(scores_to_combine, normalized_weights))
            results["combined_score"] = float(combined)
        else:
            logger.error("No similarity scores available!")
            results["combined_score"] = 0.0

        logger.info(
            f"Multi-modal similarity: "
            f"embedding={results['embedding_score']:.4f if results['embedding_score'] else 'N/A'}, "
            f"llm={results['llm_score']:.4f if results['llm_score'] else 'N/A'}, "
            f"combined={results['combined_score']:.4f}"
        )

        return results

    async def find_closest_author(self, text: str) -> Tuple[str, float]:
        """Find closest author using embedding-based centroid matching."""
        try:
            return self.embedding_model.find_closest_author(text)
        except Exception as e:
            logger.error(f"Failed to find closest author: {e}", exc_info=True)
            raise RuntimeError(f"Author matching failed: {e}") from e
