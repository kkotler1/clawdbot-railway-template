"""Image generation with multi-provider support (Gemini, OpenAI DALL-E 3, fallback)."""

import re
from pathlib import Path

from rich.console import Console

from .config import get_output_dir, load_config

console = Console()

# Aspect ratios per image position
IMAGE_ASPECT_RATIOS = {
    1: "16:9",   # Banner/Hero — landscape
    2: "16:9",   # Mid-Article — landscape
    3: "16:9",   # Actionable Step — landscape
}

# Map aspect ratios to DALL-E 3 sizes
DALLE_SIZE_MAP = {
    "16:9": "1792x1024",   # landscape
    "1:1":  "1024x1024",   # square
    "9:16": "1024x1792",   # portrait
}


def parse_image_prompts(content: str) -> list[dict]:
    """Extract image prompts from the LLM-generated blog content.

    Looks for the structured IMAGE PROMPTS section with code-fenced prompts.
    Returns a list of dicts with keys: number, title, prompt.
    """
    prompts = []

    # Match each "## Image N: Title" followed by a fenced code block containing the prompt
    pattern = re.compile(
        r"##\s*Image\s*(\d+):\s*(.+?)\n"
        r".*?"
        r"```[^\n]*\n(.+?)```",
        re.DOTALL,
    )

    for match in pattern.finditer(content):
        num = int(match.group(1))
        title = match.group(2).strip()
        prompt = match.group(3).strip()
        prompts.append({
            "number": num,
            "title": title,
            "prompt": prompt,
        })

    return prompts


def _generate_gemini(prompts: list[dict], slug: str, config: dict) -> list[Path]:
    """Generate images using Google Gemini Imagen API."""
    api_key = config.get("gemini_api_key", "")
    if not api_key:
        raise ValueError("Gemini API key not configured. Run: blog --setup")

    try:
        from google import genai
    except ImportError:
        raise ImportError(
            "The 'google-genai' package is required for Gemini image generation.\n"
            "Install it with: pip install google-genai"
        )

    client = genai.Client(api_key=api_key)

    # Discover available imagen models
    available_model = None
    try:
        for m in client.models.list():
            if "imagen" in m.name.lower() and "generate" in str(getattr(m, "supported_generation_methods", [])).lower():
                available_model = m.name
                break
        # Also try common model names directly
        if not available_model:
            for candidate in ("imagen-3.0-generate-002", "imagen-3.0-generate-001", "imagen-3.0-generate"):
                try:
                    client.models.get(model=candidate)
                    available_model = candidate
                    break
                except Exception:
                    continue
    except Exception as e:
        console.print(f"  [yellow]Could not list Gemini models: {e}[/yellow]")
        # Try the default model name — will fail at generation time if unavailable
        available_model = "imagen-3.0-generate-002"

    if not available_model:
        raise RuntimeError(
            "No Imagen model found on your Gemini API plan.\n"
            "Set image_provider to 'openai' or 'none' in ~/.blog-cli/config.json"
        )

    console.print(f"  [dim]Using Gemini model: {available_model}[/dim]")

    output_dir = get_output_dir()
    images_dir = output_dir / "images" / slug
    images_dir.mkdir(parents=True, exist_ok=True)

    generated_paths = []

    for prompt_info in prompts:
        num = prompt_info["number"]
        prompt_text = prompt_info["prompt"]
        aspect_ratio = IMAGE_ASPECT_RATIOS.get(num, "16:9")

        console.print(
            f"  [cyan]Generating image {num}:[/cyan] {prompt_text[:80]}..."
        )

        try:
            result = client.models.generate_images(
                model=available_model,
                prompt=prompt_text,
                config=genai.types.GenerateImagesConfig(
                    number_of_images=1,
                    aspect_ratio=aspect_ratio,
                ),
            )

            if result.generated_images:
                image_bytes = result.generated_images[0].image.image_bytes
                filepath = images_dir / f"image-{num}.png"
                filepath.write_bytes(image_bytes)
                generated_paths.append(filepath)
                console.print(
                    f"  [green]\u2713 Image {num} saved:[/green] {filepath}"
                )
            else:
                console.print(
                    f"  [yellow]\u26a0 No image generated for prompt {num}[/yellow]"
                )

        except Exception as e:
            console.print(f"  [red]\u2717 Image {num} failed: {e}[/red]")

    return generated_paths


def _generate_openai(prompts: list[dict], slug: str, config: dict) -> list[Path]:
    """Generate images using OpenAI DALL-E 3 API."""
    api_key = config.get("openai_api_key", "")
    if not api_key:
        raise ValueError("OpenAI API key not configured. Run: blog --setup")

    try:
        import openai
    except ImportError:
        raise ImportError(
            "The 'openai' package is required for DALL-E image generation.\n"
            "Install it with: pip install openai"
        )

    client = openai.OpenAI(api_key=api_key)

    output_dir = get_output_dir()
    images_dir = output_dir / "images" / slug
    images_dir.mkdir(parents=True, exist_ok=True)

    generated_paths = []

    for prompt_info in prompts:
        num = prompt_info["number"]
        prompt_text = prompt_info["prompt"]
        aspect_ratio = IMAGE_ASPECT_RATIOS.get(num, "16:9")
        dalle_size = DALLE_SIZE_MAP.get(aspect_ratio, "1792x1024")

        console.print(
            f"  [cyan]Generating image {num} (DALL-E 3, {dalle_size}):[/cyan] {prompt_text[:80]}..."
        )

        try:
            response = client.images.generate(
                model="dall-e-3",
                prompt=prompt_text,
                size=dalle_size,
                quality="standard",
                n=1,
            )

            image_url = response.data[0].url

            # Download the image
            import urllib.request
            filepath = images_dir / f"image-{num}.png"
            urllib.request.urlretrieve(image_url, str(filepath))

            generated_paths.append(filepath)
            console.print(
                f"  [green]\u2713 Image {num} saved:[/green] {filepath}"
            )

        except Exception as e:
            console.print(f"  [red]\u2717 Image {num} failed: {e}[/red]")

    return generated_paths


def _save_prompts_fallback(prompts: list[dict], slug: str) -> list[Path]:
    """Save image prompts to a text file when no image provider is available."""
    output_dir = get_output_dir()
    images_dir = output_dir / "images" / slug
    images_dir.mkdir(parents=True, exist_ok=True)

    prompts_file = images_dir / "prompts.txt"
    lines = ["IMAGE PROMPTS — generate these manually\n", f"Blog slug: {slug}\n", ""]

    for prompt_info in prompts:
        num = prompt_info["number"]
        title = prompt_info["title"]
        prompt_text = prompt_info["prompt"]
        aspect = IMAGE_ASPECT_RATIOS.get(num, "16:9")
        lines.append(f"Image {num}: {title}")
        lines.append(f"Aspect ratio: {aspect}")
        lines.append(f"Prompt: {prompt_text}")
        lines.append("")

    prompts_file.write_text("\n".join(lines))

    console.print(f"  [yellow]Image prompts saved to: {prompts_file}[/yellow]")
    console.print(
        "  [yellow]Generate these images manually using your preferred tool,[/yellow]"
    )
    console.print(
        f"  [yellow]then save them as image-1.png, image-2.png, etc. in {images_dir}/[/yellow]"
    )

    return []


def generate_images(prompts: list[dict], slug: str, provider: str | None = None) -> list[Path]:
    """Generate images using the configured provider.

    Provider priority:
    1. Explicit provider argument
    2. image_provider from config
    3. Auto-detect: try gemini -> openai -> fallback

    Returns list of file paths for successfully generated images.
    """
    config = load_config()

    if provider is None:
        provider = config.get("image_provider", "auto")

    provider = provider.lower().strip()

    if provider == "none":
        console.print("  [dim]Image generation skipped (image_provider = none).[/dim]")
        _save_prompts_fallback(prompts, slug)
        return []

    if provider == "gemini":
        paths = _generate_gemini(prompts, slug, config)
        if not paths and config.get("openai_api_key"):
            console.print(
                "  [yellow]All Gemini images failed. Falling back to OpenAI DALL-E 3...[/yellow]"
            )
            paths = _generate_openai(prompts, slug, config)
        if not paths:
            console.print(
                "  [yellow]Tip: Set image_provider to 'openai' in config if Imagen "
                "isn't available on your plan.[/yellow]"
            )
        return paths

    if provider == "openai":
        return _generate_openai(prompts, slug, config)

    # Auto mode: try gemini first, then openai, then fallback
    if provider == "auto":
        # Try Gemini if key is configured
        if config.get("gemini_api_key"):
            try:
                console.print("  [dim]Trying Gemini Imagen...[/dim]")
                paths = _generate_gemini(prompts, slug, config)
                if paths:
                    return paths
            except Exception as e:
                console.print(f"  [yellow]Gemini failed: {e}[/yellow]")

        # Try OpenAI DALL-E if key is configured
        if config.get("openai_api_key"):
            try:
                console.print("  [dim]Trying OpenAI DALL-E 3...[/dim]")
                return _generate_openai(prompts, slug, config)
            except Exception as e:
                console.print(f"  [yellow]OpenAI DALL-E failed: {e}[/yellow]")

        # Fallback: save prompts to file
        console.print(
            "  [yellow]No image provider available. Saving prompts for manual generation.[/yellow]"
        )
        return _save_prompts_fallback(prompts, slug)

    raise ValueError(
        f"Unknown image_provider '{provider}'. "
        "Valid values: gemini, openai, none, auto"
    )


def embed_images_in_markdown(content: str, image_paths: list[Path], slug: str) -> str:
    """Insert markdown image references after <!-- IMAGE N --> placeholders.

    Also adds image references in the IMAGE PROMPTS section next to each prompt.
    """
    for path in image_paths:
        num_match = re.search(r"image-(\d+)", path.name)
        if not num_match:
            continue
        num = int(num_match.group(1))

        relative_path = f"images/{slug}/{path.name}"
        img_md = f"\n\n![Image {num}]({relative_path})\n"

        # Insert after <!-- IMAGE N --> or <!-- IMAGE N: ... --> in the markdown body
        placeholder_pattern = re.compile(
            rf"(<!--\s*IMAGE\s*{num}\b[^>]*-->)",
            re.IGNORECASE,
        )
        content = placeholder_pattern.sub(rf"\1{img_md}", content, count=1)

    return content
