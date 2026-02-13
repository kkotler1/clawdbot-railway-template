"""WordPress API integration for creating drafts, uploading media, and setting SEO metadata."""

import base64
import re
from pathlib import Path

import requests
from rich.console import Console

from .config import load_config, get_output_dir

console = Console()


class WordPressError(Exception):
    """Raised when a WordPress API call fails."""


def _get_auth_headers(config: dict) -> dict:
    """Build HTTP Basic Auth headers from config."""
    username = config.get("wordpress_username", "")
    app_password = config.get("wordpress_app_password", "")
    if not username or not app_password:
        raise WordPressError(
            "WordPress credentials not configured. "
            "Run: blog --setup and enter your WordPress username and Application Password."
        )
    token = base64.b64encode(f"{username}:{app_password}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


def _wp_url(config: dict) -> str:
    """Get the WordPress site URL from config, stripping trailing slash."""
    url = config.get("wordpress_url", "").rstrip("/")
    if not url:
        raise WordPressError(
            "WordPress URL not configured. Run: blog --setup"
        )
    return url


def validate_credentials(config: dict) -> bool:
    """Test WordPress credentials by fetching one post. Returns True if valid."""
    wp_url = _wp_url(config)
    headers = _get_auth_headers(config)
    headers["Content-Type"] = "application/json"

    resp = requests.get(
        f"{wp_url}/wp-json/wp/v2/posts",
        headers=headers,
        params={"per_page": 1},
        timeout=15,
    )
    if resp.status_code == 200:
        return True
    if resp.status_code == 401:
        raise WordPressError(
            "WordPress authentication failed (401). "
            "Check your username and Application Password in ~/.blog-cli/config.json. "
            "Generate an Application Password at: Users > Profile > Application Passwords."
        )
    raise WordPressError(
        f"WordPress API returned status {resp.status_code}: {resp.text[:200]}"
    )


# ---------------------------------------------------------------------------
# Metadata / HTML Parsing Helpers
# ---------------------------------------------------------------------------

def parse_metadata(content: str) -> dict:
    """Extract SEO metadata fields from generated blog content."""
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
        slug = slug_match.group(1).strip()
        slug = re.sub(r"[`*]", "", slug)
        metadata["slug"] = slug

    return metadata


def extract_html_sections(content: str) -> str:
    """Extract and combine the 3 HTML sections from the blog content."""
    sections = []
    for i in range(1, 4):
        pattern = (
            rf"#\s*HTML FORMAT:\s*SECTION\s*{i}\s*OF\s*3\s*\n"
            r"(.*?)"
            r"(?=\n#\s*HTML FORMAT|\n#\s*SEO CHECKLIST|\n---\s*\n#|\Z)"
        )
        match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
        if match:
            section_text = match.group(1).strip()
            # Strip wrapping code fences if present
            section_text = re.sub(r"^```html?\s*\n?", "", section_text)
            section_text = re.sub(r"\n?```\s*$", "", section_text)
            sections.append(section_text.strip())

    if not sections:
        return ""
    return "\n\n".join(sections)


# ---------------------------------------------------------------------------
# Image Upload
# ---------------------------------------------------------------------------

def find_local_images(slug: str) -> list[Path]:
    """Look for image files in ~/Desktop/BlogDrafts/images/[slug]/."""
    output_dir = get_output_dir()
    images_dir = output_dir / "images" / slug
    if not images_dir.exists():
        return []
    extensions = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
    files = sorted(
        f for f in images_dir.iterdir()
        if f.is_file() and f.suffix.lower() in extensions
    )
    return files


def _parse_image_alt_texts(html: str) -> dict[int, str]:
    """Parse image placeholder comments to extract alt text per image number.

    Looks for patterns like:
      <!-- [IMAGE 1: HERO/BANNER IMAGE] -->
      <!-- Alt text: "some description" -->
    """
    alt_map: dict[int, str] = {}
    # Match image comments followed by an optional alt text comment
    pattern = re.compile(
        r'<!--\s*\[?IMAGE\s*(\d+)[^\]]*\]?\s*[^>]*-->'
        r'(?:\s*<!--\s*Alt\s*text:\s*["\']?([^"\'<>]+)["\']?\s*-->)?',
        re.IGNORECASE,
    )
    for m in pattern.finditer(html):
        num = int(m.group(1))
        alt = m.group(2).strip() if m.group(2) else ""
        alt_map[num] = alt
    return alt_map


def upload_image(filepath: Path, slug: str, position: int, alt_text: str, config: dict) -> dict:
    """Upload a single image to the WordPress media library.

    Returns dict with keys: id, url, alt_text.
    """
    wp_url = _wp_url(config)
    auth_headers = _get_auth_headers(config)
    title = f"{slug}-image-{position}"

    mime_map = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }
    mime = mime_map.get(filepath.suffix.lower(), "image/jpeg")

    with open(filepath, "rb") as f:
        resp = requests.post(
            f"{wp_url}/wp-json/wp/v2/media",
            headers={
                **auth_headers,
                "Content-Disposition": f'attachment; filename="{filepath.name}"',
                "Content-Type": mime,
            },
            data=f,
            timeout=60,
        )

    if resp.status_code not in (200, 201):
        raise WordPressError(f"Image upload failed ({resp.status_code}): {resp.text[:200]}")

    media = resp.json()
    media_id = media["id"]

    # Set alt text via update
    requests.post(
        f"{wp_url}/wp-json/wp/v2/media/{media_id}",
        headers={**auth_headers, "Content-Type": "application/json"},
        json={"alt_text": alt_text, "title": title},
        timeout=15,
    )

    return {
        "id": media_id,
        "url": media.get("source_url", ""),
        "alt_text": alt_text,
    }


def upload_images_for_slug(slug: str, config: dict) -> list[dict]:
    """Upload all local images for a slug and return media info list."""
    images = find_local_images(slug)
    if not images:
        return []

    # We'll read alt texts from the draft if possible, but fall back to slug-based alt
    results = []
    for idx, img_path in enumerate(images, start=1):
        alt = f"{slug.replace('-', ' ')} image {idx}"
        try:
            info = upload_image(img_path, slug, idx, alt, config)
            results.append(info)
            console.print(f"  [green]Uploaded image {idx}:[/green] {img_path.name}")
        except WordPressError as e:
            console.print(f"  [red]Failed to upload {img_path.name}: {e}[/red]")
    return results


def replace_image_placeholders(html: str, media_list: list[dict]) -> str:
    """Replace <!-- IMAGE N --> placeholders with actual <img> tags."""
    alt_map = _parse_image_alt_texts(html)

    for idx, media in enumerate(media_list, start=1):
        alt = alt_map.get(idx, media.get("alt_text", ""))
        img_tag = (
            f'<img src="{media["url"]}" alt="{alt}" '
            f'style="width:100%; height:auto;" />'
        )
        # Remove the image placeholder comment block (image line + optional alt text line)
        pattern = re.compile(
            rf'<!--\s*\[?IMAGE\s*{idx}[^\]]*\]?\s*[^>]*-->'
            rf'(?:\s*<!--\s*Alt\s*text:[^>]*-->)?',
            re.IGNORECASE,
        )
        html = pattern.sub(img_tag, html, count=1)

    return html


# ---------------------------------------------------------------------------
# Internal Links
# ---------------------------------------------------------------------------

def fetch_recent_posts(config: dict, count: int = 20) -> list[dict]:
    """Fetch recent published posts from WordPress."""
    wp_url = _wp_url(config)
    headers = _get_auth_headers(config)
    headers["Content-Type"] = "application/json"

    resp = requests.get(
        f"{wp_url}/wp-json/wp/v2/posts",
        headers=headers,
        params={
            "per_page": count,
            "status": "publish",
            "orderby": "date",
            "order": "desc",
        },
        timeout=15,
    )
    if resp.status_code != 200:
        raise WordPressError(f"Failed to fetch posts ({resp.status_code}): {resp.text[:200]}")

    posts = resp.json()
    return [
        {
            "id": p["id"],
            "title": p["title"]["rendered"],
            "link": p["link"],
            "slug": p["slug"],
        }
        for p in posts
    ]


def pick_related_posts(posts: list[dict], title: str, keyword: str, limit: int = 3) -> list[dict]:
    """Pick the most relevant posts based on keyword/title word overlap.

    Falls back to the most recent posts if relevance scoring produces nothing.
    """
    if not posts:
        return []

    kw_words = set(keyword.lower().split())
    title_words = set(re.sub(r"[^a-z0-9\s]", "", title.lower()).split())
    query_words = kw_words | title_words
    stop_words = {"the", "a", "an", "and", "or", "of", "in", "on", "to", "for", "with", "is", "are", "how", "your"}
    query_words -= stop_words

    scored = []
    for post in posts:
        post_words = set(re.sub(r"[^a-z0-9\s]", "", post["title"].lower()).split())
        post_words |= set(post["slug"].replace("-", " ").lower().split())
        post_words -= stop_words
        overlap = len(query_words & post_words)
        scored.append((overlap, post))

    scored.sort(key=lambda x: x[0], reverse=True)

    # If top results have zero overlap, just return most recent
    selected = [p for score, p in scored[:limit]]
    return selected


def build_internal_links_html(posts: list[dict]) -> str:
    """Build the 'More From the Blaze Vending Blog' HTML block."""
    if not posts:
        return ""
    items = "\n".join(
        f'  <li><a href="{p["link"]}">{p["title"]}</a></li>' for p in posts
    )
    return (
        '<h2>More From the Blaze Vending Blog</h2>\n'
        '<p>If you found this helpful, here are a few other posts worth checking out:</p>\n'
        f'<ul>\n{items}\n</ul>'
    )


def insert_internal_links(html: str, links_html: str) -> str:
    """Insert internal links section before <h2>Sources</h2>, or append at end."""
    if not links_html:
        return html

    # Try to insert before Sources heading
    sources_pattern = re.compile(r"(<h2[^>]*>\s*Sources\s*</h2>)", re.IGNORECASE)
    if sources_pattern.search(html):
        return sources_pattern.sub(links_html + "\n\n" + r"\1", html, count=1)

    # Append at end
    return html + "\n\n" + links_html


# ---------------------------------------------------------------------------
# Draft Creation & SEO Metadata
# ---------------------------------------------------------------------------

def create_draft(title: str, html_content: str, slug: str, config: dict) -> dict:
    """Create a WordPress draft post. Returns dict with id and edit_url."""
    wp_url = _wp_url(config)
    headers = _get_auth_headers(config)
    headers["Content-Type"] = "application/json"

    resp = requests.post(
        f"{wp_url}/wp-json/wp/v2/posts",
        headers=headers,
        json={
            "title": title,
            "content": html_content,
            "status": "draft",
            "slug": slug,
        },
        timeout=30,
    )

    if resp.status_code not in (200, 201):
        raise WordPressError(f"Draft creation failed ({resp.status_code}): {resp.text[:300]}")

    post = resp.json()
    post_id = post["id"]
    edit_url = f"{wp_url}/wp-admin/post.php?post={post_id}&action=edit"

    return {"id": post_id, "edit_url": edit_url}


def set_featured_image(post_id: int, media_id: int, config: dict):
    """Set the featured image (post thumbnail) on a post."""
    wp_url = _wp_url(config)
    headers = _get_auth_headers(config)
    headers["Content-Type"] = "application/json"

    resp = requests.post(
        f"{wp_url}/wp-json/wp/v2/posts/{post_id}",
        headers=headers,
        json={"featured_media": media_id},
        timeout=15,
    )
    if resp.status_code not in (200, 201):
        raise WordPressError(f"Failed to set featured image ({resp.status_code})")


def set_rankmath_meta(post_id: int, metadata: dict, config: dict) -> bool:
    """Attempt to set Rank Math SEO fields on the post.

    Tries the Rank Math REST endpoint first, then falls back to post meta.
    Returns True if any method succeeded.
    """
    wp_url = _wp_url(config)
    headers = _get_auth_headers(config)
    headers["Content-Type"] = "application/json"

    seo_title = metadata.get("title", "")
    seo_desc = metadata.get("meta_description", "")
    focus_kw = metadata.get("keyword", "")

    # Approach 1: Rank Math REST API
    try:
        resp = requests.post(
            f"{wp_url}/wp-json/rankmath/v1/updateMeta",
            headers=headers,
            json={
                "objectID": post_id,
                "objectType": "post",
                "meta": {
                    "rank_math_title": seo_title,
                    "rank_math_description": seo_desc,
                    "rank_math_focus_keyword": focus_kw,
                },
            },
            timeout=15,
        )
        if resp.status_code in (200, 201):
            return True
    except Exception:
        pass

    # Approach 2: Post meta via WP REST API
    try:
        resp = requests.post(
            f"{wp_url}/wp-json/wp/v2/posts/{post_id}",
            headers=headers,
            json={
                "meta": {
                    "rank_math_title": seo_title,
                    "rank_math_description": seo_desc,
                    "rank_math_focus_keyword": focus_kw,
                }
            },
            timeout=15,
        )
        if resp.status_code in (200, 201):
            return True
    except Exception:
        pass

    return False


# ---------------------------------------------------------------------------
# High-level Orchestrators
# ---------------------------------------------------------------------------

def publish_to_wordpress(
    blog_content: str,
    keyword: str,
    skip_images: bool = False,
) -> dict:
    """Full WordPress publishing pipeline after blog generation.

    Returns a summary dict with keys: post_id, edit_url, images_status,
    internal_links_count, rankmath_set, slug.
    """
    config = load_config()
    metadata = parse_metadata(blog_content)
    title = metadata.get("title", keyword)
    slug = metadata.get("slug", keyword.lower().replace(" ", "-"))
    summary: dict = {"slug": slug}

    # Step 1: Connect
    console.print("\n[cyan]Connecting to {0}...[/cyan]".format(
        config.get("wordpress_url", "WordPress")
    ))
    try:
        validate_credentials(config)
    except WordPressError as e:
        console.print(f"[red]WordPress auth error: {e}[/red]")
        raise

    # Step 2: Fetch existing posts for internal links
    console.print("[cyan]Fetching existing posts for internal links...[/cyan]")
    related_posts = []
    try:
        all_posts = fetch_recent_posts(config)
        related_posts = pick_related_posts(all_posts, title, keyword)
        console.print(
            f"[green]Found {len(related_posts)} related posts for internal linking[/green]"
        )
    except WordPressError as e:
        console.print(f"[yellow]Could not fetch posts for internal links: {e}[/yellow]")

    summary["internal_links_count"] = len(related_posts)

    # Step 3: Build HTML content
    html_content = extract_html_sections(blog_content)
    if not html_content:
        console.print("[yellow]No HTML sections found — using raw content as fallback.[/yellow]")
        html_content = blog_content

    # Insert internal links
    links_html = build_internal_links_html(related_posts)
    html_content = insert_internal_links(html_content, links_html)

    # Step 4: Handle images
    media_list = []
    if not skip_images:
        images = find_local_images(slug)
        if images:
            console.print(f"[cyan]Uploading {len(images)} images...[/cyan]")
            # Get alt texts from html to pass to uploader
            alt_map = _parse_image_alt_texts(html_content)
            for idx, img_path in enumerate(images, start=1):
                alt = alt_map.get(idx, f"{slug.replace('-', ' ')} image {idx}")
                try:
                    info = upload_image(img_path, slug, idx, alt, config)
                    media_list.append(info)
                    console.print(f"  [green]Uploaded:[/green] {img_path.name}")
                except WordPressError as e:
                    console.print(f"  [red]Failed: {img_path.name} — {e}[/red]")
        else:
            console.print(
                f"[yellow]No images found in ~/Desktop/BlogDrafts/images/{slug}/[/yellow]"
            )
            console.print(
                f"[yellow]  Generate images and run: blog --upload-images {slug}[/yellow]"
            )

    if media_list:
        html_content = replace_image_placeholders(html_content, media_list)
        summary["images_status"] = f"{len(media_list)} uploaded"
    else:
        summary["images_status"] = f"pending (run blog --upload-images {slug})"

    # Step 5: Create draft
    console.print("[cyan]Creating WordPress draft...[/cyan]")
    try:
        draft = create_draft(title, html_content, slug, config)
    except WordPressError as e:
        console.print(f"[red]Draft creation failed: {e}[/red]")
        raise

    summary["post_id"] = draft["id"]
    summary["edit_url"] = draft["edit_url"]
    console.print("[green]Draft created![/green]")

    # Step 6: Set Rank Math SEO fields
    rankmath_ok = set_rankmath_meta(draft["id"], metadata, config)
    summary["rankmath_set"] = rankmath_ok
    if not rankmath_ok:
        console.print(
            "[yellow]Could not set Rank Math fields automatically. "
            "Enter these manually:[/yellow]"
        )
        console.print(f"  [dim]Title:[/dim]       {metadata.get('title', 'N/A')}")
        console.print(f"  [dim]Description:[/dim] {metadata.get('meta_description', 'N/A')}")
        console.print(f"  [dim]Keyword:[/dim]     {metadata.get('keyword', 'N/A')}")

    # Step 7: Set featured image (Image 1 = banner)
    if media_list:
        try:
            set_featured_image(draft["id"], media_list[0]["id"], config)
        except WordPressError as e:
            console.print(f"[yellow]Could not set featured image: {e}[/yellow]")

    return summary


def upload_images_command(slug: str):
    """Standalone command: upload images for an existing draft and update the post."""
    config = load_config()

    console.print(f"\n[cyan]Looking for images in ~/Desktop/BlogDrafts/images/{slug}/...[/cyan]")
    images = find_local_images(slug)
    if not images:
        console.print(
            f"[red]No images found in {get_output_dir() / 'images' / slug}/[/red]"
        )
        console.print("Place your images there and try again.")
        return

    console.print(f"[green]Found {len(images)} images.[/green]")

    # Find the existing draft by slug
    console.print("[cyan]Finding WordPress draft...[/cyan]")
    wp_url = _wp_url(config)
    headers = _get_auth_headers(config)
    headers["Content-Type"] = "application/json"

    resp = requests.get(
        f"{wp_url}/wp-json/wp/v2/posts",
        headers=headers,
        params={"slug": slug, "status": "draft"},
        timeout=15,
    )
    if resp.status_code != 200 or not resp.json():
        console.print(f"[red]No draft found with slug '{slug}'.[/red]")
        console.print("Make sure the draft exists on WordPress before uploading images.")
        return

    post = resp.json()[0]
    post_id = post["id"]
    html_content = post["content"]["rendered"]
    console.print(f"[green]Found draft: {post['title']['rendered']} (ID: {post_id})[/green]")

    # Parse alt texts from existing HTML
    alt_map = _parse_image_alt_texts(html_content)

    # Upload images
    media_list = []
    for idx, img_path in enumerate(images, start=1):
        alt = alt_map.get(idx, f"{slug.replace('-', ' ')} image {idx}")
        try:
            info = upload_image(img_path, slug, idx, alt, config)
            media_list.append(info)
            console.print(f"  [green]Uploaded:[/green] {img_path.name}")
        except WordPressError as e:
            console.print(f"  [red]Failed: {img_path.name} — {e}[/red]")

    if not media_list:
        console.print("[red]No images were uploaded successfully.[/red]")
        return

    # Replace placeholders in post content
    updated_html = replace_image_placeholders(html_content, media_list)

    # Update the post
    console.print("[cyan]Updating post content with images...[/cyan]")
    resp = requests.post(
        f"{wp_url}/wp-json/wp/v2/posts/{post_id}",
        headers=headers,
        json={"content": updated_html},
        timeout=30,
    )
    if resp.status_code not in (200, 201):
        console.print(f"[red]Failed to update post: {resp.text[:200]}[/red]")
        return

    # Set featured image (first image = banner)
    try:
        set_featured_image(post_id, media_list[0]["id"], config)
        console.print("[green]Featured image set.[/green]")
    except WordPressError as e:
        console.print(f"[yellow]Could not set featured image: {e}[/yellow]")

    edit_url = f"{wp_url}/wp-admin/post.php?post={post_id}&action=edit"
    console.print(f"\n[green]Done! {len(media_list)} images uploaded and inserted.[/green]")
    console.print(f"[cyan]Edit:[/cyan] {edit_url}")
