"""Image generation using Google Imagen 3 via the Gemini API."""

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


def generate_images(prompts: list[dict], slug: str) -> list[Path]:
    """Generate images using Imagen 3 and save them to the images directory.

    Returns list of file paths for successfully generated images.
    """
    config = load_config()
    api_key = config.get("gemini_api_key", "")
    if not api_key:
        raise ValueError("Gemini API key not configured. Run: blog --setup")

    try:
        from google import genai
    except ImportError:
        raise ImportError(
            "The 'google-genai' package is required for image generation.\n"
            "Install it with: pip install google-genai\n"
            "Note: 'google-generativeai' is a different (deprecated) package."
        )

    client = genai.Client(api_key=api_key)

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
                model="imagen-3.0-generate-002",
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
