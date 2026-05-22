"""LLM utility functions for The Council.

Supports any OpenAI-compatible API provider (OpenAI, Anthropic, Ollama,
Azure OpenAI, Together AI, Groq, etc.) via configurable base_url and api_key.
"""

import json
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from council.models import ProviderConfig


def call_llm(
    prompt: str,
    temperature: float = 0.7,
    provider: Optional["ProviderConfig"] = None,
) -> str:
    """Call LLM with prompt and return text response.

    Supports any OpenAI-compatible API via the provider parameter.
    Always uses JSON mode to guarantee valid structured output.

    Args:
        prompt: The prompt to send to the LLM
        temperature: Controls randomness (0.0-1.0). Higher = more creative.
        provider: LLM provider configuration. Uses defaults if not provided.

    Returns:
        The LLM's text response (guaranteed valid JSON when prompt requests it).
    """
    # Import here to avoid circular imports
    from council.models import ProviderConfig
    from openai import BadRequestError, OpenAI

    if provider is None:
        provider = ProviderConfig()

    client = OpenAI(api_key=provider.get_api_key(), base_url=provider.base_url)

    request_kwargs = {
        "model": provider.model,
        "temperature": temperature,
        "messages": [{"role": "user", "content": prompt}],
        "response_format": {"type": "json_object"},
    }

    try:
        response = client.chat.completions.create(
            **request_kwargs,
            max_completion_tokens=10000,
        )
    except BadRequestError as exc:
        if "max_completion_tokens" not in str(exc):
            raise

        response = client.chat.completions.create(
            **request_kwargs,
            max_tokens=10000,
        )

    return response.choices[0].message.content or ""


def parse_json_response(response: str) -> dict:
    """Parse JSON from an LLM response.

    Args:
        response: The raw JSON response from the LLM

    Returns:
        Parsed dictionary from the JSON content

    Raises:
        ValueError: If JSON cannot be parsed
    """
    try:
        return json.loads(response)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse JSON from response: {e}")


if __name__ == "__main__":
    print("## Testing call_llm with default config")
    prompt = "In a few words, what is the meaning of life?"
    print(f"## Prompt: {prompt}")

    try:
        response = call_llm(prompt)
        print(f"## Response: {response}")
    except Exception as e:
        print(f"## Error: {e}")
        print(
            "## Make sure OPENAI_API_KEY is set or configure a different provider"
        )
