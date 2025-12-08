import os
import re
import json
import hashlib
import logging
import asyncio
from typing import List, Tuple
from google import genai

from config import Config

logger = logging.getLogger(__name__)


async def rewrite_to_style(
    text: str, 
    style_examples: List[str],
    config: Config,
    author_name: str = "the author"
) -> str:
    """Rewrite text to match a given style using Gemini API."""
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY environment variable not set")
    
    try:
        client = genai.Client(api_key=api_key)
        
        # Build style guidance
        from style_analysis import extract_style_features, format_style_features
        
        style_description = ""
        if config.extract_style_features and style_examples:
            features = extract_style_features(style_examples[0])
            style_description = format_style_features(features)
        
        examples_section = ""
        if config.use_multiple_style_examples and len(style_examples) > 1:
            examples_section = "\n\n".join([
                f"STYLE EXAMPLE {i+1}:\n{ex}" 
                for i, ex in enumerate(style_examples[:config.num_style_examples])
            ])
        else:
            examples_section = f"STYLE EXAMPLE:\n{style_examples[0]}"
        
        if config.use_detailed_style_prompt:
            prompt = f"""You are rewriting a blog post to match {author_name}'s distinctive writing style.

ORIGINAL TEXT TO REWRITE:
{text}

---

{examples_section}

---

STYLE ANALYSIS:
{author_name}'s writing style is characterized by: {style_description}

REWRITING INSTRUCTIONS:
1. **Sentence Structure**: Match the rhythm and length of sentences from the examples
2. **Vocabulary**: Use similar word choices, technical terms, and expressions
3. **Tone**: Capture the same level of formality/casualness and enthusiasm
4. **Punctuation**: Mirror the use of dashes, commas, exclamations, and questions
5. **Paragraph Flow**: Follow similar paragraph transitions and structure
6. **Rhetorical Devices**: If the author uses metaphors, analogies, or questions, include similar devices
7. **Content Preservation**: Keep ALL factual information and key points from the original
8. **Length Target**: {config.min_word_count}-{config.max_word_count} words

CRITICAL: The rewrite must sound like {author_name} wrote it while preserving all original information.

Rewritten blog post:"""
        else:
            prompt = f"""Rewrite this blog post to match {author_name}'s writing style.

STYLE EXAMPLES from {author_name}:
{examples_section}

TEXT TO REWRITE:
{text}

Instructions:
- Match the tone, vocabulary, and sentence patterns from the examples
- Preserve all key facts and information
- Target length: {config.min_word_count}-{config.max_word_count} words
- Make it sound authentically like {author_name}

Rewritten post:"""
        
        response = await asyncio.to_thread(
            client.models.generate_content,
            model=config.gemini_model,
            contents=prompt,
            config={
                'max_output_tokens': config.max_output_tokens,
                'temperature': 0.8
            }
        )
        
        output = (
            getattr(response, "text", None) or 
            getattr(response, "output_text", None) or 
            ""
        )
        
        result = output.strip()
        
        if not result:
            logger.warning("API returned empty response")
            return text
        
        logger.debug(f"Rewrite complete: {len(result)} chars")
        return result
        
    except Exception as e:
        logger.error(f"Rewrite failed: {e}")
        raise RuntimeError(f"Style rewrite failed: {e}") from e


async def llm_similarity_score(
    text: str,
    style_examples: List[str],
    config: Config,
    author_name: str = "the author"
) -> Tuple[float, str]:
    """Use LLM to evaluate style similarity between text and author examples."""
    
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY environment variable not set")
    
    # Check cache
    if config.cache_llm_scores:
        content_hash = hashlib.md5(
            (text + "".join(style_examples[:1])).encode()
        ).hexdigest()
        cache_file = config.cache_dir / f"llm_sim_{content_hash}.json"
        
        if cache_file.exists():
            try:
                with open(cache_file, 'r') as f:
                    cached = json.load(f)
                    logger.debug(f"LLM similarity cache hit: {cached['score']:.4f}")
                    return cached['score'], cached.get('reasoning', '')
            except Exception as e:
                logger.warning(f"Failed to read LLM similarity cache: {e}")
    
    try:
        client = genai.Client(api_key=api_key)
        
        examples_text = "\n\n---\n\n".join([
            f"AUTHOR EXAMPLE {i+1}:\n{ex[:1500]}" 
            for i, ex in enumerate(style_examples[:2])
        ])
        
        prompt = f"""You are an expert literary analyst evaluating writing style similarity.

TASK: Rate how well the TEXT TO EVALUATE matches {author_name}'s distinctive writing style.

{examples_text}

---

TEXT TO EVALUATE:
{text[:2000]}

---

EVALUATION CRITERIA:
Analyze these specific aspects and provide detailed reasoning:

1. **Sentence Structure** (20 points)
2. **Vocabulary & Word Choice** (20 points)
3. **Tone & Voice** (20 points)
4. **Punctuation & Formatting** (15 points)
5. **Rhetorical Devices** (15 points)
6. **Paragraph Structure** (10 points)

Provide your response in this EXACT format:

SCORE: [0.0 to 1.0]

REASONING:
[Detailed analysis]

STRENGTHS:
[What matches well]

WEAKNESSES:
[What doesn't match]"""

        response = await asyncio.to_thread(
            client.models.generate_content,
            model=config.llm_similarity_model,
            contents=prompt,
            config={
                'max_output_tokens': 800,
                'temperature': 0.3
            }
        )
        
        output = (
            getattr(response, "text", None) or 
            getattr(response, "output_text", None) or 
            ""
        )
        
        if not output:
            logger.warning("LLM similarity scoring returned empty response")
            return 0.5, "No response from LLM"
        
        # Parse score
        score = 0.5
        reasoning = output
        
        score_patterns = [
            r'SCORE:\s*([0-9]*\.?[0-9]+)',
            r'Score:\s*([0-9]*\.?[0-9]+)',
            r'score:\s*([0-9]*\.?[0-9]+)',
            r'([0-9]*\.?[0-9]+)\s*/\s*1\.0',
            r'rating:\s*([0-9]*\.?[0-9]+)',
        ]
        
        for pattern in score_patterns:
            match = re.search(pattern, output, re.IGNORECASE)
            if match:
                try:
                    parsed_score = float(match.group(1))
                    if parsed_score > 1.0:
                        if parsed_score <= 10.0:
                            parsed_score = parsed_score / 10.0
                        elif parsed_score <= 100.0:
                            parsed_score = parsed_score / 100.0
                    score = max(0.0, min(1.0, parsed_score))
                    break
                except ValueError:
                    continue
        
        logger.debug(f"LLM similarity score: {score:.4f}")
        
        # Cache result
        if config.cache_llm_scores:
            try:
                config.cache_dir.mkdir(parents=True, exist_ok=True)
                with open(cache_file, 'w') as f:
                    json.dump({
                        'score': score,
                        'reasoning': reasoning,
                        'timestamp': asyncio.get_event_loop().time()
                    }, f)
            except Exception as e:
                logger.warning(f"Failed to cache LLM similarity score: {e}")
        
        return score, reasoning
        
    except Exception as e:
        logger.error(f"LLM similarity scoring failed: {e}")
        return 0.5, f"Error: {str(e)}"