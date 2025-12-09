from typing import Dict, List, Any


def extract_style_features(text: str) -> Dict[str, Any]:
    """Extract explicit stylistic features from text."""
    if not text:
        return {}

    sentences = [
        s.strip()
        for s in text.replace("!", ".").replace("?", ".").split(".")
        if s.strip()
    ]
    words = text.split()

    features = {
        # Sentence structure
        "avg_sentence_length": len(words) / max(len(sentences), 1),
        "sentence_count": len(sentences),
        "short_sentences": sum(1 for s in sentences if len(s.split()) < 10),
        "long_sentences": sum(1 for s in sentences if len(s.split()) > 20),
        # Word choice
        "avg_word_length": sum(len(w) for w in words) / max(len(words), 1),
        "unique_word_ratio": len(set(w.lower() for w in words)) / max(len(words), 1),
        # Punctuation style
        "exclamation_count": text.count("!"),
        "question_count": text.count("?"),
        "comma_density": text.count(",") / max(len(words), 1),
        "dash_usage": text.count("--") + text.count("—"),
        "colon_usage": text.count(":"),
        # Paragraph structure
        "paragraph_count": text.count("\n\n") + 1,
        # Formatting
        "bold_usage": text.count("**") // 2,
        "italic_usage": text.count("*") - text.count("**") * 2,
        "list_usage": text.count("\n*") + text.count("\n-"),
        # Tone indicators
        "uses_contractions": any(
            word in text.lower()
            for word in ["don't", "can't", "won't", "it's", "you're", "we're"]
        ),
        "uses_questions": "?" in text,
        "uses_em_dash": "—" in text or "--" in text,
    }

    return features


def format_style_features(features: Dict[str, Any]) -> str:
    """Format style features into readable description."""
    desc = []

    # Sentence style
    avg_sent = features.get("avg_sentence_length", 0)
    if avg_sent < 12:
        desc.append("very short, punchy sentences")
    elif avg_sent < 18:
        desc.append("moderate-length sentences")
    else:
        desc.append("longer, more complex sentences")

    # Punctuation personality
    if features.get("exclamation_count", 0) > 2:
        desc.append("enthusiastic tone with exclamations")
    if features.get("question_count", 0) > 2:
        desc.append("engages reader with questions")
    if features.get("dash_usage", 0) > 1:
        desc.append("uses dashes for emphasis or asides")

    # Formality
    if features.get("uses_contractions"):
        desc.append("conversational with contractions")
    else:
        desc.append("more formal without contractions")

    # Formatting
    if features.get("bold_usage", 0) > 3:
        desc.append("emphasizes key points with bold text")
    if features.get("list_usage", 0) > 3:
        desc.append("uses bullet points or lists")

    return "; ".join(desc) if desc else "neutral style"


def select_diverse_examples(
    text: str, num_examples: int = 3, min_length: int = 500
) -> List[str]:
    """Select diverse excerpts from author's content to show variety of style."""
    paragraphs = [p.strip() for p in text.split("\n\n") if len(p.strip()) > 100]

    if not paragraphs:
        paragraphs = [p.strip() for p in text.split("\n") if len(p.strip()) > 100]

    if len(paragraphs) < num_examples:
        return [text[: min_length * num_examples]]

    examples = []
    step = len(paragraphs) // num_examples

    for i in range(num_examples):
        start_idx = i * step
        excerpt_paragraphs = []
        current_length = 0

        for j in range(start_idx, min(start_idx + 10, len(paragraphs))):
            excerpt_paragraphs.append(paragraphs[j])
            current_length += len(paragraphs[j])
            if current_length >= min_length:
                break

        if excerpt_paragraphs:
            examples.append("\n\n".join(excerpt_paragraphs))

    return examples if examples else [text[: min_length * num_examples]]
