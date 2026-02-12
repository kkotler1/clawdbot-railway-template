"""Blog Generator CLI entry point."""

import sys

import click
from rich.console import Console

from .api import call_llm
from .config import first_run_check, load_config, run_setup
from .output import save_blog
from .seo import display_results, run_seo_checks
from .templates import load_template, render_template

console = Console()

ARTICLE_TYPES = [
    "research analysis",
    "operational guide",
    "strategic framework",
    "lesser-known facts",
    "industry comparison",
]


@click.command()
@click.argument("topic", required=False)
@click.option(
    "--tone",
    type=click.Choice(["motivational", "analytical", "direct"]),
    default=None,
    help="Blog tone/style template to use.",
)
@click.option(
    "--model",
    type=click.Choice(["claude", "openai"]),
    default=None,
    help="LLM model to use.",
)
@click.option(
    "--type",
    "article_type",
    type=click.Choice(ARTICLE_TYPES),
    default="operational guide",
    help="Type of article to generate.",
)
@click.option(
    "--core-message",
    default=None,
    help="Core message for the blog post.",
)
@click.option(
    "--notes",
    default=None,
    help="Extra instructions to append to the prompt.",
)
@click.option(
    "--keyword",
    default=None,
    help="Exact focus keyword to use.",
)
@click.option(
    "--no-save",
    is_flag=True,
    default=False,
    help="Print output to terminal instead of saving to file.",
)
@click.option(
    "--setup",
    is_flag=True,
    default=False,
    help="Run interactive setup to configure API keys.",
)
def main(topic, tone, model, article_type, core_message, notes, keyword, no_save, setup):
    """Generate SEO-optimized blog posts for Blaze Vending.

    TOPIC is the blog post topic (required unless using --setup).

    \b
    Examples:
      blog "vibe coding for vending operators" --tone motivational
      blog "smart vending technology" --model openai --type "research analysis"
      blog --setup
    """
    # Handle --setup flag
    if setup:
        run_setup()
        return

    # First-run check
    first_run_check()

    # Topic is required for blog generation
    if not topic:
        console.print("[red]Error: Missing required argument 'TOPIC'.[/red]")
        console.print("Usage: blog \"your topic here\" [OPTIONS]")
        console.print("Run 'blog --help' for all options.")
        sys.exit(1)

    # Load defaults from config
    config = load_config()
    if tone is None:
        tone = config.get("default_tone", "motivational")
    if model is None:
        model = config.get("default_model", "claude")

    # Step 1: Load template
    model_display = (
        f"Claude (claude-sonnet-4-5-20250514)" if model == "claude" else "OpenAI (gpt-4o)"
    )

    try:
        template = load_template(tone)
        console.print(f"\n[cyan]Loading template:[/cyan] {tone}")
    except (FileNotFoundError, ValueError) as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)

    # Step 2: Render template with variables
    rendered_prompt, resolved_keyword = render_template(
        template=template,
        topic=topic,
        article_type=article_type,
        core_message=core_message,
        notes=notes,
        keyword=keyword,
    )

    # Step 3: Call LLM
    console.print(f"[cyan]Generating blog with {model_display}...[/cyan]")

    try:
        blog_content = call_llm(rendered_prompt, model)
    except Exception as e:
        console.print(f"\n[red]API Error: {e}[/red]")
        sys.exit(1)

    # Count words in the blog body for display
    word_count = len(blog_content.split())
    console.print(f"[green]Blog generated ({word_count:,} words)[/green]")

    # Step 4: Run SEO checks
    seo_results = run_seo_checks(blog_content, resolved_keyword)
    has_failures = display_results(seo_results, console)

    # Step 5: Handle output
    if no_save:
        console.print("\n[bold]--- BLOG OUTPUT ---[/bold]\n")
        console.print(blog_content)
        return

    if has_failures:
        console.print()
        if not click.confirm("There are SEO failures. Save anyway?"):
            console.print("[yellow]File not saved.[/yellow]")
            sys.exit(0)

    filepath = save_blog(blog_content, resolved_keyword)
    console.print(f"\n[green]Saved to: {filepath}[/green]")
    console.print("[dim]Cowork will pick this up and create your WordPress draft.[/dim]")


if __name__ == "__main__":
    main()
