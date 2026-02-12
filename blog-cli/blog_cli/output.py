"""Output file formatting and saving."""

import re
from pathlib import Path

from .config import get_output_dir


def extract_slug(content: str, keyword: str) -> str:
    """Extract the URL slug from generated content, or generate one from keyword."""
    slug_match = re.search(r"\*\*URL Slug:\*\*\s*(.+)", content)
    if slug_match:
        slug = slug_match.group(1).strip()
        # Clean up any markdown or extra formatting
        slug = re.sub(r"[`*]", "", slug)
        return slug

    # Generate slug from keyword
    slug = keyword.lower()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"\s+", "-", slug.strip())
    slug = re.sub(r"-+", "-", slug)
    return slug


def save_blog(content: str, keyword: str) -> Path:
    """Save the blog content to the output directory and return the file path."""
    slug = extract_slug(content, keyword)
    filename = f"{slug}.md"

    output_dir = get_output_dir()
    output_dir.mkdir(parents=True, exist_ok=True)

    filepath = output_dir / filename
    filepath.write_text(content)

    return filepath
