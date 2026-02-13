"""LLM API integration for Anthropic and OpenAI."""

from rich.console import Console

from .config import load_config


def call_llm(prompt: str, model_choice: str) -> str:
    """Send the assembled prompt to the selected LLM and return the response."""
    config = load_config()

    if model_choice == "claude":
        return _call_anthropic(prompt, config)
    elif model_choice == "openai":
        return _call_openai(prompt, config)
    else:
        raise ValueError(f"Unknown model choice: {model_choice}")


def _call_anthropic(prompt: str, config: dict) -> str:
    """Call the Anthropic API."""
    import anthropic

    api_key = config.get("anthropic_api_key", "")
    if not api_key:
        raise ValueError(
            "Anthropic API key not configured. Run: blog --setup"
        )

    client = anthropic.Anthropic(api_key=api_key)

    message = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=8192,
        temperature=0.7,
        messages=[{"role": "user", "content": prompt}],
    )

    return message.content[0].text


def _call_openai(prompt: str, config: dict) -> str:
    """Call the OpenAI API."""
    import openai

    api_key = config.get("openai_api_key", "")
    if not api_key:
        raise ValueError(
            "OpenAI API key not configured. Run: blog --setup"
        )

    client = openai.OpenAI(api_key=api_key)

    response = client.chat.completions.create(
        model="gpt-4o",
        max_tokens=8192,
        temperature=0.7,
        messages=[{"role": "user", "content": prompt}],
    )

    return response.choices[0].message.content
