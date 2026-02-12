"""Template loading and variable substitution."""

import re
from pathlib import Path

from rich.console import Console

from .config import TEMPLATES_DIR


def load_template(tone: str) -> str:
    """Load a template file by tone name."""
    template_path = TEMPLATES_DIR / f"{tone}.txt"

    if not template_path.exists():
        raise FileNotFoundError(
            f"Template not found: {template_path}\n"
            f"Available templates: {', '.join(t.stem for t in TEMPLATES_DIR.glob('*.txt'))}"
        )

    content = template_path.read_text()

    if content.strip() == "# Paste your template prompt here":
        raise ValueError(
            f"Template '{tone}.txt' is a placeholder. "
            f"Please paste your prompt template into: {template_path}"
        )

    return content


def render_template(
    template: str,
    topic: str,
    article_type: str,
    core_message: str | None,
    notes: str | None,
    keyword: str | None,
) -> str:
    """Replace placeholder variables in the template."""
    # Generate defaults if not provided
    if not core_message:
        core_message = f"Practical insights to help operators succeed with {topic}"

    if not keyword:
        keyword = generate_keyword(topic)

    # Extra notes handling
    if notes:
        extra_notes_block = f"## EXTRA NOTES\n{notes}"
    else:
        extra_notes_block = ""

    rendered = template.replace("{{TOPIC}}", topic)
    rendered = rendered.replace("{{ARTICLE_TYPE}}", article_type)
    rendered = rendered.replace("{{CORE_MESSAGE}}", core_message)
    rendered = rendered.replace("{{FOCUS_KEYWORD}}", keyword)
    rendered = rendered.replace("{{EXTRA_NOTES}}", extra_notes_block)

    return rendered, keyword


def generate_keyword(topic: str) -> str:
    """Generate a focus keyword from the topic.

    Simplifies the topic into a concise keyword phrase.
    """
    # Clean up common filler words for a tighter keyword
    words = topic.lower().split()
    stop_words = {"for", "the", "a", "an", "and", "or", "of", "in", "on", "to", "with", "is", "are", "how"}
    filtered = [w for w in words if w not in stop_words]

    # Keep it to 3-5 words max for a keyword phrase
    if len(filtered) > 5:
        filtered = filtered[:5]

    return " ".join(filtered) if filtered else topic.lower()
