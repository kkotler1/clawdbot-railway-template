"""Configuration management for Blog CLI."""

import json
from pathlib import Path

import click
from rich.console import Console

CONFIG_DIR = Path.home() / ".blog-cli"
CONFIG_FILE = CONFIG_DIR / "config.json"
TEMPLATES_DIR = CONFIG_DIR / "templates"

DEFAULT_CONFIG = {
    "anthropic_api_key": "",
    "openai_api_key": "",
    "gemini_api_key": "",
    "default_model": "claude",
    "default_tone": "motivational",
    "image_provider": "auto",
    "output_dir": "~/Desktop/BlogDrafts/",
    "wordpress_url": "https://blazevending.com",
    "wordpress_username": "",
    "wordpress_app_password": "",
    "auto_publish_draft": True,
}

PLACEHOLDER_TEMPLATE = "# Paste your template prompt here\n"

MOTIVATIONAL_TEMPLATE = """\
You are an expert blog writer for Blaze Vending (blazevending.com), a vending machine business resource site. \
Write in a friendly, encouraging, and supportive guide tone. You help vending operators feel confident and capable.

## TOPIC
{{TOPIC}}

## ARTICLE TYPE
{{ARTICLE_TYPE}}

## CORE MESSAGE
{{CORE_MESSAGE}}

## FOCUS KEYWORD
{{FOCUS_KEYWORD}}

{{EXTRA_NOTES}}

## VOICE & STYLE
- Warm, motivational, and practical
- Use "you" language — speak directly to the operator
- Include real-world examples and actionable advice
- Avoid jargon unless you explain it
- Sound like a mentor who's been in the vending business, not a corporate blogger
- Use short paragraphs and conversational flow

## STRUCTURE REQUIREMENTS
- SEO Title (H1): Must include the focus keyword within the first 60 characters
- Meta Description: 150-160 characters, must include the exact focus keyword
- URL Slug: Lowercase, hyphenated, keyword-rich
- Word Count: 1,500-2,000 words for the blog body
- Use H2 and H3 subheadings throughout — at least 2 should contain the focus keyword or a close variation
- Include the focus keyword in the first 150 words of the blog body
- Keyword density: 1-2% (use exact match and natural variations)
- At least 40% of keyword instances should be exact match

## IMAGE PROMPTS
Generate 3 image prompts:
1. **Image 1: Banner/Hero Image** — Landscape (16:9), suitable for blog banner. Describe a vivid, professional scene related to the topic.
2. **Image 2: Mid-Article Concept Visualization** — Square or landscape, insertable mid-article. Visualize a key concept from the article.
3. **Image 3: Actionable Step Support** — Landscape, inline placement. Illustrate a practical step or tip from the article.

Each image prompt should:
- Be 80-200 characters
- Include the character count
- Include a one-sentence purpose statement

## HTML OUTPUT
Divide the blog post into 3 roughly equal HTML sections (Section 1 of 3, Section 2 of 3, Section 3 of 3). \
Use proper HTML tags (h2, h3, p, ul, li, strong, em). Include image placement markers like \
`<!-- IMAGE 1: Banner/Hero -->` at appropriate locations.

## SOURCES
Include a "Sources" section at the end with at least 3 relevant, real URLs that support the content. \
Use markdown link format.

## INTERNAL LINKS
Include a placeholder section titled "Related Articles" or "Further Reading" where internal links can be inserted.

## OUTPUT FORMAT
You MUST output the blog in this EXACT structure:

```
# BLOG POST METADATA

**SEO Title (H1):** [title with focus keyword in first 60 chars]
**Focus Keyword:** [exact focus keyword]
**Meta Description:** [150-160 chars, includes exact focus keyword]
**URL Slug:** [lowercase-hyphenated-slug]
**Word Count Target:** 1,500-2,000 words
**Article Type:** [article type]

---

# IMAGE PROMPTS

## Image 1: Banner/Hero Image
**Placement:** Top of article, hero banner
**Format:** Landscape (16:9), suitable for blog banner placement

[image prompt in a code block]

**Character Count:** [count]
**Purpose:** [one sentence]

## Image 2: Mid-Article Concept Visualization
**Placement:** After the first major section
**Format:** Square or landscape, insertable mid-article

[image prompt in a code block]

**Character Count:** [count]
**Purpose:** [one sentence]

## Image 3: Actionable Step Support
**Placement:** Alongside action steps section
**Format:** Landscape, optimized for inline placement

[image prompt in a code block]

**Character Count:** [count]
**Purpose:** [one sentence]

---

# VISUAL FORMAT: FULL BLOG POST

[The complete blog post in Markdown format with image placement markers like <!-- IMAGE 1 -->, <!-- IMAGE 2 -->, <!-- IMAGE 3 -->]

---

# HTML FORMAT: SECTION 1 OF 3

[HTML code block for section 1]

---

# HTML FORMAT: SECTION 2 OF 3

[HTML code block for section 2]

---

# HTML FORMAT: SECTION 3 OF 3

[HTML code block for section 3]

---

# SEO CHECKLIST: VERIFIED

| Check | Status |
|-------|--------|
| Focus keyword in title (first 60 chars) | ✅ |
| Focus keyword in meta description | ✅ |
| Meta description 150-160 chars | ✅ |
| Focus keyword in first paragraph | ✅ |
| Focus keyword in URL slug | ✅ |
| Keyword density 1-2% | ✅ |
| 40%+ exact match ratio | ✅ |
| Keyword in 2+ subheadings | ✅ |
| Image alt text with keyword | ✅ |
| Word count 1,200-2,000 | ✅ |
| 3+ source links | ✅ |
| Internal link section present | ✅ |
```

Write the complete blog post now. Do not include any commentary outside the output structure above.
"""


def ensure_dirs():
    """Create all required directories if they don't exist."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)

    output_dir = get_output_dir()
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "completed").mkdir(exist_ok=True)


def get_output_dir() -> Path:
    """Get the output directory from config or default."""
    config = load_config()
    raw = config.get("output_dir", DEFAULT_CONFIG["output_dir"])
    return Path(raw).expanduser()


def load_config() -> dict:
    """Load config from file, returning defaults if not found."""
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return dict(DEFAULT_CONFIG)


def save_config(config: dict):
    """Save config to file."""
    ensure_dirs()
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


def ensure_templates():
    """Create placeholder template files if they don't exist."""
    ensure_dirs()

    motivational_path = TEMPLATES_DIR / "motivational.txt"
    if not motivational_path.exists():
        with open(motivational_path, "w") as f:
            f.write(MOTIVATIONAL_TEMPLATE)

    for name in ("analytical.txt", "direct.txt"):
        path = TEMPLATES_DIR / name
        if not path.exists():
            with open(path, "w") as f:
                f.write(PLACEHOLDER_TEMPLATE)


def run_setup():
    """Interactive setup flow for first run."""
    console = Console()
    console.print("\n[bold cyan]Blog CLI Setup[/bold cyan]\n")
    console.print("This will configure your API keys and preferences.\n")

    config = load_config()

    # Anthropic key
    anthropic_key = click.prompt(
        "Anthropic API key (leave blank to skip)",
        default=config.get("anthropic_api_key", ""),
        show_default=False,
    )
    config["anthropic_api_key"] = anthropic_key.strip()

    # OpenAI key
    openai_key = click.prompt(
        "OpenAI API key (leave blank to skip)",
        default=config.get("openai_api_key", ""),
        show_default=False,
    )
    config["openai_api_key"] = openai_key.strip()

    # Gemini key (for Imagen 3 image generation)
    console.print("\n[bold cyan]Image Generation (Imagen 3)[/bold cyan]\n")
    console.print(
        "To auto-generate images for blog posts, enter your Google Gemini API key.\n"
        "Get one at: https://aistudio.google.com/apikey\n"
    )
    gemini_key = click.prompt(
        "Gemini API key (leave blank to skip)",
        default=config.get("gemini_api_key", ""),
        show_default=False,
    )
    config["gemini_api_key"] = gemini_key.strip()

    # Image provider
    console.print(
        "\n[bold cyan]Image Provider[/bold cyan]\n"
    )
    console.print(
        "Choose which service generates blog images:\n"
        "  [cyan]auto[/cyan]   — try Gemini first, fall back to OpenAI DALL-E 3\n"
        "  [cyan]gemini[/cyan] — Google Imagen only\n"
        "  [cyan]openai[/cyan] — OpenAI DALL-E 3 only\n"
        "  [cyan]none[/cyan]   — skip image generation (save prompts to file)\n"
    )
    image_provider = click.prompt(
        "Image provider",
        type=click.Choice(["auto", "gemini", "openai", "none"]),
        default=config.get("image_provider", "auto"),
    )
    config["image_provider"] = image_provider

    # Default model
    default_model = click.prompt(
        "Default model",
        type=click.Choice(["claude", "openai"]),
        default=config.get("default_model", "claude"),
    )
    config["default_model"] = default_model

    # Default tone
    default_tone = click.prompt(
        "Default tone",
        type=click.Choice(["motivational", "analytical", "direct"]),
        default=config.get("default_tone", "motivational"),
    )
    config["default_tone"] = default_tone

    # Output directory
    output_dir = click.prompt(
        "Output directory",
        default=config.get("output_dir", DEFAULT_CONFIG["output_dir"]),
    )
    config["output_dir"] = output_dir

    # WordPress settings
    console.print("\n[bold cyan]WordPress Integration[/bold cyan]\n")
    console.print(
        "To enable automatic draft creation, enter your WordPress credentials.\n"
        "Generate an Application Password at: Users > Profile > Application Passwords.\n"
    )

    wp_url = click.prompt(
        "WordPress site URL",
        default=config.get("wordpress_url", DEFAULT_CONFIG["wordpress_url"]),
    )
    config["wordpress_url"] = wp_url.rstrip("/")

    wp_username = click.prompt(
        "WordPress username (leave blank to skip)",
        default=config.get("wordpress_username", ""),
        show_default=False,
    )
    config["wordpress_username"] = wp_username.strip()

    wp_app_password = click.prompt(
        "WordPress Application Password (leave blank to skip)",
        default=config.get("wordpress_app_password", ""),
        show_default=False,
    )
    config["wordpress_app_password"] = wp_app_password.strip()

    config["auto_publish_draft"] = True

    save_config(config)
    ensure_templates()

    console.print(f"\n[green]Config saved to {CONFIG_FILE}[/green]")
    console.print(f"[green]Templates created in {TEMPLATES_DIR}/[/green]")
    console.print("[green]Setup complete![/green]\n")

    # Validate keys
    if config["anthropic_api_key"]:
        try:
            import anthropic

            client = anthropic.Anthropic(api_key=config["anthropic_api_key"])
            client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=10,
                messages=[{"role": "user", "content": "Hi"}],
            )
            console.print("[green]✓ Anthropic API key validated[/green]")
        except Exception as e:
            console.print(f"[yellow]⚠ Anthropic API key validation failed: {e}[/yellow]")

    if config["openai_api_key"]:
        try:
            import openai

            client = openai.OpenAI(api_key=config["openai_api_key"])
            client.chat.completions.create(
                model="gpt-4o",
                max_tokens=10,
                messages=[{"role": "user", "content": "Hi"}],
            )
            console.print("[green]✓ OpenAI API key validated[/green]")
        except Exception as e:
            console.print(f"[yellow]⚠ OpenAI API key validation failed: {e}[/yellow]")

    if config.get("gemini_api_key"):
        try:
            from google import genai
        except ImportError:
            console.print(
                "[yellow]⚠ Gemini validation skipped: 'google-genai' package not installed.\n"
                "  Install with: pip install google-genai[/yellow]"
            )
            genai = None

        if genai is not None:
            try:
                client = genai.Client(api_key=config["gemini_api_key"])
                # Try to discover available imagen models
                found_model = None
                try:
                    for m in client.models.list():
                        if "imagen" in m.name.lower():
                            found_model = m.name
                            break
                except Exception:
                    pass
                if not found_model:
                    for candidate in ("imagen-3.0-generate-002", "imagen-3.0-generate-001"):
                        try:
                            client.models.get(model=candidate)
                            found_model = candidate
                            break
                        except Exception:
                            continue
                if found_model:
                    console.print(f"[green]✓ Gemini API key validated (model: {found_model})[/green]")
                else:
                    console.print(
                        "[yellow]⚠ Gemini key works but no Imagen model found on your plan.\n"
                        "  Consider setting image_provider to 'openai' or 'none'.[/yellow]"
                    )
            except Exception as e:
                console.print(f"[yellow]⚠ Gemini API key validation failed: {e}[/yellow]")

    if config.get("wordpress_username") and config.get("wordpress_app_password"):
        try:
            from .wordpress import validate_credentials
            validate_credentials(config)
            console.print("[green]✓ WordPress credentials validated[/green]")
        except Exception as e:
            console.print(f"[yellow]⚠ WordPress validation failed: {e}[/yellow]")

    console.print()


def first_run_check():
    """Check if this is a first run and set up if needed."""
    needs_setup = False

    if not CONFIG_DIR.exists():
        needs_setup = True
    elif not CONFIG_FILE.exists():
        needs_setup = True
    else:
        config = load_config()
        if not config.get("anthropic_api_key") and not config.get("openai_api_key"):
            needs_setup = True

    if needs_setup:
        console = Console()
        console.print("\n[bold cyan]Welcome to Blog CLI for Blaze Vending![/bold cyan]")
        console.print("─" * 50)
        console.print(
            "\nThis tool generates SEO-optimized blog posts for blazevending.com."
        )
        console.print("\n[bold]Basic usage:[/bold]")
        console.print('  blog "your topic here" --tone motivational')
        console.print("\n[bold]Full options:[/bold]")
        console.print('  blog "topic" --tone motivational --model claude \\')
        console.print('    --type "operational guide" --keyword "focus keyword" \\')
        console.print('    --notes "extra instructions"')
        console.print("\nLet's set up your configuration first.\n")
        run_setup()
        return True

    # Ensure dirs and templates exist even if config is present
    ensure_dirs()
    ensure_templates()
    return False
