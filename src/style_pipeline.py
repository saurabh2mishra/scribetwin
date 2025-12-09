import logging
import asyncio
import traceback
from typing import Dict, Any, Optional
import requests

from config import Config
from utils import get_retry_session, validate_content
from rss_fetcher import fetch_author_blogs
from style_analysis import (
    extract_style_features,
    format_style_features,
    select_diverse_examples,
)
from embedding_model import AuthorStyleModel
from multimodal_model import MultiModalStyleModel
from llm_services import rewrite_to_style

logger = logging.getLogger(__name__)


async def style_refinement_pipeline(
    draft: str,
    rss_api_url: str,
    config: Config,
    session: Optional[requests.Session] = None,
) -> Dict[str, Any]:
    """
    Standalone function to refine blog draft to match author style.

    Args:
        draft: Blog draft to refine
        rss_api_url: RSS feed URL for author style data
        config: Configuration object
        session: Optional requests session

    Returns:
        Dictionary with styled_blog and metadata
    """
    logger.info("=" * 60)
    logger.info("Starting style refinement pipeline")
    logger.info("=" * 60)

    if not draft or not draft.strip():
        logger.error("No draft provided to style refinement")
        return {
            "styled_blog": "",
            "style_similarity": 0.0,
            "embedding_similarity": None,
            "llm_similarity": None,
            "rewrite_attempts": 0,
            "closest_author": None,
            "error": "No draft provided",
            "success": False,
        }

    logger.info(f"Input draft: {len(draft)} chars, {len(draft.split())} words")

    # Validate input content
    is_valid, error_msg = validate_content(draft, config, check_word_count=False)
    if not is_valid:
        logger.warning(f"Draft validation warning: {error_msg}")

    try:
        # Initialize models
        logger.info("Initializing multi-modal style model...")
        embedding_model = AuthorStyleModel(config)
        style_model = MultiModalStyleModel(config, embedding_model)

        # Fetch author data
        if session is None:
            session = get_retry_session(config)

        logger.info("Fetching author blogs...")
        author_blogs = fetch_author_blogs(rss_api_url, config, session)

        logger.info("Building style centroids...")
        embedding_model.build_centroids(author_blogs)

        # Prepare style examples
        style_examples_dict = {}
        for author, content in author_blogs.items():
            if config.use_multiple_style_examples:
                examples = select_diverse_examples(
                    content,
                    num_examples=config.num_style_examples,
                    min_length=config.style_example_length // config.num_style_examples,
                )
                style_examples_dict[author] = examples
            else:
                style_examples_dict[author] = [content[: config.style_example_length]]

        # Find closest matching author
        logger.info("Finding closest author match...")
        author_id, initial_emb_score = await style_model.find_closest_author(draft)
        style_examples = style_examples_dict.get(author_id, [])

        if not style_examples:
            logger.warning(f"No style examples for author '{author_id}'")
            return {
                "styled_blog": draft,
                "style_similarity": initial_emb_score,
                "embedding_similarity": initial_emb_score,
                "llm_similarity": None,
                "rewrite_attempts": 0,
                "closest_author": author_id,
                "error": "No style examples available",
                "success": False,
            }

        # Compute initial multi-modal similarity
        logger.info("Computing initial multi-modal similarity...")
        initial_similarity = await style_model.compute_similarity(
            draft, author_id, style_examples
        )
        
        initial_combined_score = initial_similarity["combined_score"]
        initial_emb_sim = initial_similarity["embedding_score"]
        initial_llm_sim = initial_similarity["llm_score"]

        logger.info(
            f"Matched author: '{author_id}' "
            f"(combined: {initial_combined_score:.4f}, "
            f"embedding: {initial_emb_sim:.4f if initial_emb_sim else 'N/A'}, "
            f"llm: {initial_llm_sim:.4f if initial_llm_sim else 'N/A'})"
        )

        # Extract and log style features
        if config.extract_style_features:
            features = extract_style_features(style_examples[0])
            style_desc = format_style_features(features)
            logger.info(f"Author style: {style_desc}")

        # Check if already similar enough
        if initial_combined_score >= config.similarity_threshold:
            logger.info(
                f"Draft already meets similarity threshold "
                f"({initial_combined_score:.4f} >= {config.similarity_threshold})"
            )
            return {
                "styled_blog": draft,
                "style_similarity": initial_combined_score,
                "embedding_similarity": initial_emb_sim,
                "llm_similarity": initial_llm_sim,
                "rewrite_attempts": 0,
                "closest_author": author_id,
                "initial_similarity": initial_combined_score,
                "success": True,
            }

        # Iterative refinement
        logger.info(
            f"Starting iterative refinement (threshold: {config.similarity_threshold})"
        )
        current_text = draft
        current_score = initial_combined_score
        current_emb_sim = initial_emb_sim
        current_llm_sim = initial_llm_sim
        attempts = 0
        improvement_history = [initial_combined_score]

        while (
            current_score < config.similarity_threshold
            and attempts < config.max_rewrite_attempts
        ):
            logger.info(
                f"Rewrite attempt {attempts + 1}/{config.max_rewrite_attempts} "
                f"(current score: {current_score:.4f})"
            )

            try:
                # Rewrite with style matching
                rewritten = await rewrite_to_style(
                    current_text, style_examples, config, author_name=author_id
                )

                if not rewritten or not rewritten.strip():
                    logger.warning("Rewrite returned empty text, stopping")
                    break

                # Validate rewritten content
                is_valid, error_msg = validate_content(
                    rewritten, config, check_word_count=True
                )
                if not is_valid:
                    logger.warning(f"Rewritten content invalid: {error_msg}")

                # Check new multi-modal similarity
                new_similarity = await style_model.compute_similarity(
                    rewritten, author_id, style_examples
                )
                
                new_score = new_similarity["combined_score"]
                new_emb_sim = new_similarity["embedding_score"]
                new_llm_sim = new_similarity["llm_score"]
                
                improvement = new_score - current_score

                logger.info(
                    f"Rewrite {attempts + 1}: "
                    f"combined {current_score:.4f} -> {new_score:.4f} (Δ {improvement:+.4f}), "
                    f"embedding: {new_emb_sim:.4f if new_emb_sim else 'N/A'}, "
                    f"llm: {new_llm_sim:.4f if new_llm_sim else 'N/A'}"
                )

                # Check for convergence
                if improvement <= 0.01:
                    logger.info("Similarity plateaued, stopping refinement")
                    break

                # Accept improvement
                current_text = rewritten
                current_score = new_score
                current_emb_sim = new_emb_sim
                current_llm_sim = new_llm_sim
                improvement_history.append(new_score)
                attempts += 1

                # Rate limiting
                await asyncio.sleep(0.5)

            except Exception as e:
                logger.error(f"Rewrite attempt {attempts + 1} failed: {e}")
                break

        # Final validation
        is_valid, error_msg = validate_content(current_text, config)
        if not is_valid:
            logger.warning(f"Final content validation failed: {error_msg}")

        logger.info(
            f"Style refinement complete: "
            f"combined {initial_combined_score:.4f} -> {current_score:.4f}, "
            f"embedding: {current_emb_sim:.4f if current_emb_sim else 'N/A'}, "
            f"llm: {current_llm_sim:.4f if current_llm_sim else 'N/A'} "
            f"after {attempts} attempts"
        )

        # Build result
        result = {
            "styled_blog": current_text,
            "style_similarity": float(current_score),
            "embedding_similarity": float(current_emb_sim) if current_emb_sim is not None else None,
            "llm_similarity": float(current_llm_sim) if current_llm_sim is not None else None,
            "rewrite_attempts": attempts,
            "closest_author": author_id,
            "initial_similarity": float(initial_combined_score),
            "improvement_history": [float(s) for s in improvement_history],
            "success": True,
        }

        if current_score < config.similarity_threshold:
            logger.warning(
                f"Failed to reach similarity threshold "
                f"({current_score:.4f} < {config.similarity_threshold})"
            )
            result["warning"] = "Similarity threshold not reached"

        return result

    except Exception as e:
        logger.error(f"Style refinement failed: {e}", exc_info=True)
        return {
            "styled_blog": draft,
            "style_similarity": 0.0,
            "embedding_similarity": None,
            "llm_similarity": None,
            "rewrite_attempts": 0,
            "closest_author": None,
            "error": f"{type(e).__name__}: {str(e)}",
            "error_traceback": traceback.format_exc(),
            "success": False,
        }