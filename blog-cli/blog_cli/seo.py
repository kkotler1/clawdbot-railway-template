"""SEO pre-check system for generated blog posts."""

import re

from rich.console import Console


class SEOResult:
    """Result of a single SEO check."""

    def __init__(self, name: str, passed: bool, warning: bool = False, detail: str = ""):
        self.name = name
        self.passed = passed
        self.warning = warning  # True = yellow warning, False + not passed = red fail
        self.detail = detail

    @property
    def is_fail(self) -> bool:
        return not self.passed and not self.warning


def run_seo_checks(content: str, keyword: str) -> list[SEOResult]:
    """Run all SEO checks on generated blog content and return results."""
    results = []
    metadata = _parse_metadata(content)
    blog_body = _extract_blog_body(content)
    headings = _extract_headings(content)

    results.append(_check_keyword_in_title(metadata, keyword))
    results.append(_check_keyword_in_meta(metadata, keyword))
    results.append(_check_meta_length(metadata))
    results.append(_check_keyword_in_first_paragraph(blog_body, keyword))
    results.append(_check_keyword_in_slug(metadata, keyword))
    density_result, exact_count, total_count = _check_keyword_density(blog_body, keyword)
    results.append(density_result)
    results.append(_check_exact_match_ratio(blog_body, keyword, exact_count, total_count))
    results.append(_check_subheading_keywords(headings, keyword))
    results.append(_check_image_alt_text(content, keyword))
    results.append(_check_word_count(blog_body))
    results.append(_check_sources(content))
    results.append(_check_internal_links(content))

    return results


def display_results(results: list[SEOResult], console: Console) -> bool:
    """Display SEO check results and return True if there are any hard failures."""
    console.print("\n[bold]=== SEO PRE-CHECK ===[/bold]\n")

    passed = 0
    warnings = 0
    failures = 0

    for r in results:
        if r.passed:
            icon = "[green]✅[/green]"
            passed += 1
        elif r.warning:
            icon = "[yellow]⚠️ [/yellow]"
            warnings += 1
        else:
            icon = "[red]❌[/red]"
            failures += 1

        detail = f" — {r.detail}" if r.detail else ""
        console.print(f" {icon} {r.name}{detail}")

    total = len(results)
    console.print(
        f"\nScore: {passed}/{total} checks passed | "
        f"{warnings} warning{'s' if warnings != 1 else ''}"
        + (f" | {failures} failure{'s' if failures != 1 else ''}" if failures else "")
    )

    has_failures = failures > 0
    return has_failures


def _parse_metadata(content: str) -> dict:
    """Extract metadata fields from the blog post header."""
    metadata = {}

    title_match = re.search(r"\*\*SEO Title \(H1\):\*\*\s*(.+)", content)
    if title_match:
        metadata["title"] = title_match.group(1).strip()

    keyword_match = re.search(r"\*\*Focus Keyword:\*\*\s*(.+)", content)
    if keyword_match:
        metadata["keyword"] = keyword_match.group(1).strip()

    meta_match = re.search(r"\*\*Meta Description:\*\*\s*(.+)", content)
    if meta_match:
        metadata["meta_description"] = meta_match.group(1).strip()

    slug_match = re.search(r"\*\*URL Slug:\*\*\s*(.+)", content)
    if slug_match:
        metadata["slug"] = slug_match.group(1).strip()

    type_match = re.search(r"\*\*Article Type:\*\*\s*(.+)", content)
    if type_match:
        metadata["article_type"] = type_match.group(1).strip()

    return metadata


def _extract_blog_body(content: str) -> str:
    """Extract the main blog body text (VISUAL FORMAT section)."""
    # Look for the VISUAL FORMAT section
    pattern = r"#\s*VISUAL FORMAT:?\s*FULL BLOG POST\s*\n(.*?)(?=\n---\n|\n#\s*HTML FORMAT)"
    match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()

    # Fallback: try to get everything between metadata and HTML sections
    pattern = r"---\s*\n(.*?)(?=\n#\s*HTML FORMAT)"
    matches = list(re.finditer(pattern, content, re.DOTALL))
    # The blog body is typically the largest section between separators
    if len(matches) >= 2:
        return matches[1].group(1).strip()

    return content


def _extract_headings(content: str) -> list[str]:
    """Extract H2 and H3 headings from blog body."""
    blog_body = _extract_blog_body(content)
    # Match markdown headings ## and ###
    headings = re.findall(r"^#{2,3}\s+(.+)$", blog_body, re.MULTILINE)
    # Also check HTML headings
    html_headings = re.findall(r"<h[23][^>]*>(.*?)</h[23]>", content, re.IGNORECASE)
    return headings + html_headings


def _check_keyword_in_title(metadata: dict, keyword: str) -> SEOResult:
    """Check if focus keyword appears in the SEO title within first 60 chars."""
    title = metadata.get("title", "")
    first_60 = title[:60].lower()
    kw_lower = keyword.lower()

    if kw_lower in first_60:
        return SEOResult("Focus keyword in title (within first 60 chars)", True)

    if kw_lower in title.lower():
        return SEOResult(
            "Focus keyword in title",
            False,
            warning=True,
            detail="keyword found but not within first 60 characters",
        )

    return SEOResult("Focus keyword in title", False, detail="keyword not found in title")


def _check_keyword_in_meta(metadata: dict, keyword: str) -> SEOResult:
    """Check if exact-match focus keyword is in the meta description."""
    meta = metadata.get("meta_description", "")
    if keyword.lower() in meta.lower():
        return SEOResult("Focus keyword in meta description (exact match)", True)
    return SEOResult(
        "Focus keyword in meta description",
        False,
        detail="exact-match keyword not found",
    )


def _check_meta_length(metadata: dict) -> SEOResult:
    """Check if meta description is 150-160 characters."""
    meta = metadata.get("meta_description", "")
    length = len(meta)

    if 150 <= length <= 160:
        return SEOResult(f"Meta description length: {length} characters", True)

    if 140 <= length < 150 or 160 < length <= 170:
        return SEOResult(
            f"Meta description length: {length} characters",
            False,
            warning=True,
            detail=f"target is 150-160 characters",
        )

    return SEOResult(
        f"Meta description length: {length} characters",
        False,
        detail=f"target is 150-160 characters",
    )


def _check_keyword_in_first_paragraph(blog_body: str, keyword: str) -> SEOResult:
    """Check if focus keyword appears in the first 150 words."""
    words = blog_body.split()
    first_150_words = " ".join(words[:150]).lower()

    if keyword.lower() in first_150_words:
        return SEOResult("Focus keyword in first paragraph", True)
    return SEOResult(
        "Focus keyword in first paragraph",
        False,
        detail="keyword not found in first 150 words",
    )


def _check_keyword_in_slug(metadata: dict, keyword: str) -> SEOResult:
    """Check if keyword (or close variation) is in the URL slug."""
    slug = metadata.get("slug", "")
    # Convert keyword to slug form for comparison
    kw_slug = keyword.lower().replace(" ", "-")
    kw_words = set(keyword.lower().split())
    slug_words = set(slug.lower().replace("-", " ").split())

    if kw_slug in slug.lower():
        return SEOResult("Focus keyword in URL slug", True)

    # Check if most keyword words are in the slug
    overlap = kw_words & slug_words
    if len(overlap) >= len(kw_words) * 0.6:
        return SEOResult(
            "Focus keyword in URL slug",
            True,
            detail="close variation found",
        )

    return SEOResult(
        "Focus keyword in URL slug",
        False,
        warning=True,
        detail="keyword or close variation not found in slug",
    )


def _check_keyword_density(blog_body: str, keyword: str) -> tuple[SEOResult, int, int]:
    """Check keyword density is between 1-2%."""
    text_lower = blog_body.lower()
    words = text_lower.split()
    word_count = len(words)

    if word_count == 0:
        result = SEOResult("Keyword density", False, detail="no content found")
        return result, 0, 0

    # Count exact matches
    exact_count = text_lower.count(keyword.lower())

    # Count variations (individual keyword words appearing together in different forms)
    kw_words = keyword.lower().split()
    variation_count = 0
    if len(kw_words) > 1:
        # Count instances where keyword words appear near each other but not exact match
        for i in range(len(words) - len(kw_words) + 1):
            window = " ".join(words[i : i + len(kw_words) + 1])
            if keyword.lower() not in window:
                # Check if all keyword words are present in this window
                if all(kw_word in window for kw_word in kw_words):
                    variation_count += 1

    total_instances = exact_count + variation_count
    kw_word_count = len(kw_words)
    # Density = (keyword instances * words in keyword) / total words * 100
    density = (total_instances * kw_word_count) / word_count * 100

    if 1.0 <= density <= 2.0:
        result = SEOResult(f"Keyword density: {density:.1f}% (target: 1-2%)", True)
    elif 0.8 <= density < 1.0:
        deficit = max(1, round((1.0 - density) * word_count / kw_word_count))
        result = SEOResult(
            f"Keyword density: {density:.1f}% (target: 1-2%)",
            False,
            warning=True,
            detail=f"consider adding {deficit} more instance{'s' if deficit > 1 else ''}",
        )
    elif 2.0 < density <= 2.5:
        result = SEOResult(
            f"Keyword density: {density:.1f}% (target: 1-2%)",
            False,
            warning=True,
            detail="slightly high, consider reducing",
        )
    else:
        result = SEOResult(
            f"Keyword density: {density:.1f}% (target: 1-2%)",
            False,
            detail=f"{'too low' if density < 1.0 else 'too high'}",
        )

    return result, exact_count, total_instances


def _check_exact_match_ratio(
    blog_body: str, keyword: str, exact_count: int, total_count: int
) -> SEOResult:
    """Check if at least 40% of keyword instances are exact match."""
    if total_count == 0:
        return SEOResult(
            "Exact match ratio",
            False,
            warning=True,
            detail="no keyword instances found",
        )

    ratio = (exact_count / total_count) * 100

    if ratio >= 40:
        return SEOResult(f"Exact match ratio: {ratio:.0f}% (target: 40%+)", True)

    return SEOResult(
        f"Exact match ratio: {ratio:.0f}% (target: 40%+)",
        False,
        warning=True,
        detail="consider using more exact-match keyword instances",
    )


def _check_subheading_keywords(headings: list[str], keyword: str) -> SEOResult:
    """Check if focus keyword or variation appears in at least 2 H2/H3 headings."""
    kw_lower = keyword.lower()
    kw_words = set(kw_lower.split())
    matches = 0

    for heading in headings:
        heading_lower = heading.lower()
        # Exact match
        if kw_lower in heading_lower:
            matches += 1
            continue
        # Variation: at least half of keyword words present
        heading_words = set(heading_lower.split())
        overlap = kw_words & heading_words
        if len(overlap) >= max(1, len(kw_words) // 2):
            matches += 1

    total = len(headings)
    if matches >= 2:
        return SEOResult(
            f"Keyword in subheadings: found in {matches} of {total} H2/H3 tags",
            True,
        )

    if matches == 1:
        return SEOResult(
            f"Keyword in subheadings: found in {matches} of {total} H2/H3 tags",
            False,
            warning=True,
            detail="target is 2+ subheadings",
        )

    return SEOResult(
        "Keyword in subheadings: not found in any H2/H3 tags",
        False,
        detail="add keyword to at least 2 subheadings",
    )


def _check_image_alt_text(content: str, keyword: str) -> SEOResult:
    """Check if at least one image alt text contains the exact-match keyword."""
    # Check for alt text in HTML img tags
    alt_texts = re.findall(r'alt=["\']([^"\']*)["\']', content, re.IGNORECASE)

    # Also check image prompt sections for keyword usage
    image_sections = re.findall(
        r"##\s*Image\s*\d.*?\n(.*?)(?=##\s*Image|\n---|\Z)",
        content,
        re.DOTALL | re.IGNORECASE,
    )

    kw_lower = keyword.lower()

    for alt in alt_texts:
        if kw_lower in alt.lower():
            return SEOResult("Image alt text: exact match found", True)

    # Check image prompt content as a fallback
    for section in image_sections:
        if kw_lower in section.lower():
            return SEOResult("Image alt text: keyword found in image prompts", True)

    return SEOResult(
        "Image alt text: keyword not found",
        False,
        warning=True,
        detail="add exact-match keyword to at least one image alt text",
    )


def _check_word_count(blog_body: str) -> SEOResult:
    """Check if word count is between 1,200 and 2,000."""
    # Strip markdown formatting for a cleaner count
    clean = re.sub(r"[#*_`\[\]()]", "", blog_body)
    clean = re.sub(r"<!--.*?-->", "", clean)
    words = [w for w in clean.split() if w.strip()]
    count = len(words)

    if 1200 <= count <= 2000:
        return SEOResult(f"Word count: {count:,} words", True)

    if 1000 <= count < 1200 or 2000 < count <= 2200:
        return SEOResult(
            f"Word count: {count:,} words",
            False,
            warning=True,
            detail="target: 1,200-2,000 words",
        )

    return SEOResult(
        f"Word count: {count:,} words",
        False,
        detail="target: 1,200-2,000 words",
    )


def _check_sources(content: str) -> SEOResult:
    """Check if there's a Sources section with at least 3 links."""
    # Look for a Sources section
    sources_match = re.search(
        r"(?:^|\n)#{1,3}\s*(?:Sources|References|Bibliography)\s*\n(.*?)(?=\n#{1,2}\s|\n---|\Z)",
        content,
        re.DOTALL | re.IGNORECASE,
    )

    if not sources_match:
        # Also check within HTML sections
        html_sources = re.search(
            r"(?:Sources|References)</h[23]>(.*?)(?:</div>|</section>|\Z)",
            content,
            re.DOTALL | re.IGNORECASE,
        )
        if html_sources:
            sources_match = html_sources

    if not sources_match:
        return SEOResult(
            "Sources section",
            False,
            warning=True,
            detail="no Sources section detected",
        )

    # Count links
    section_text = sources_match.group(1) if sources_match else ""
    md_links = re.findall(r"\[.*?\]\(https?://.*?\)", section_text)
    html_links = re.findall(r'href=["\']https?://.*?["\']', section_text)
    total_links = len(md_links) + len(html_links)

    if total_links >= 3:
        return SEOResult(f"Sources section: {total_links} links found", True)

    return SEOResult(
        f"Sources section: {total_links} links found",
        False,
        warning=True,
        detail="target is at least 3 source links",
    )


def _check_internal_links(content: str) -> SEOResult:
    """Check if there's an internal link section placeholder."""
    patterns = [
        r"related\s*articles",
        r"further\s*reading",
        r"internal\s*links",
        r"read\s*more",
        r"you\s*might\s*also\s*like",
        r"related\s*posts",
    ]

    content_lower = content.lower()
    for pattern in patterns:
        if re.search(pattern, content_lower):
            return SEOResult("Internal link section: detected", True)

    return SEOResult(
        "Internal link section: not detected",
        False,
        warning=True,
        detail="Cowork will add this automatically",
    )
