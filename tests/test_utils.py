import unittest
from types import SimpleNamespace
from unittest.mock import patch

from council.models import ProviderConfig
from council.prompts import Prompt, PromptPart
from council.utils import call_llm, parse_json_response, render_prompt


def _response(content: str = "{}"):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
    )


class TestPromptRendering(unittest.TestCase):
    def test_render_prompt_returns_plain_string_unchanged(self):
        prompt = "plain prompt"

        self.assertEqual(render_prompt(prompt), prompt)

    def test_render_prompt_flattens_prompt_object(self):
        prompt = Prompt(
            parts=[
                PromptPart(name="one", content="One"),
                PromptPart(name="two", content="Two"),
            ]
        )

        self.assertEqual(render_prompt(prompt), "One\n\nTwo")


class TestPromptCachingRequests(unittest.TestCase):
    def test_default_provider_sends_unchanged_openai_compatible_payload(self):
        provider = ProviderConfig(api_key="test-key")

        with patch("openai.OpenAI") as openai:
            create = openai.return_value.chat.completions.create
            create.return_value = _response()

            call_llm("plain prompt", provider=provider)

        kwargs = create.call_args.kwargs
        self.assertEqual(
            kwargs,
            {
                "model": "gpt-4o",
                "temperature": 0.7,
                "messages": [{"role": "user", "content": "plain prompt"}],
                "response_format": {"type": "json_object"},
                "max_completion_tokens": 10000,
            },
        )
        self.assertNotIn("cache_control", str(kwargs))
        self.assertNotIn("prompt_cache", kwargs)

    def test_openai_compatible_auto_flattens_without_cache_control_fields(self):
        provider = ProviderConfig(
            api_key="test-key",
            prompt_cache=True,
            prompt_cache_strategy="openai_compatible_auto",
        )
        prompt = Prompt(
            parts=[
                PromptPart(name="stable", content="Stable", cacheable=True),
                PromptPart(name="volatile", content="Current"),
            ]
        )

        with patch("openai.OpenAI") as openai:
            create = openai.return_value.chat.completions.create
            create.return_value = _response()

            call_llm(prompt, provider=provider)

        kwargs = create.call_args.kwargs
        self.assertEqual(
            kwargs["messages"],
            [{"role": "user", "content": "Stable\n\nCurrent"}],
        )
        self.assertNotIn("cache_control", str(kwargs))
        self.assertNotIn("prompt_cache", kwargs)

    def test_unsupported_prompt_cache_strategy_raises(self):
        provider = ProviderConfig(
            api_key="test-key",
            prompt_cache=True,
            prompt_cache_strategy="anthropic_cache_control",
        )

        with self.assertRaises(ValueError):
            call_llm("plain prompt", provider=provider)


class TestJsonParsing(unittest.TestCase):
    def test_parses_valid_json_object(self):
        response = '{"action": "revise", "reasoning": "I made a mistake"}'
        expected = {"action": "revise", "reasoning": "I made a mistake"}
        self.assertEqual(parse_json_response(response), expected)

    def test_parses_json_with_whitespace(self):
        response = """

  {
    "name": "Agent",
    "role": "Tester"
  }

"""
        expected = {"name": "Agent", "role": "Tester"}
        self.assertEqual(parse_json_response(response), expected)

    def test_parses_nested_json(self):
        response = '{"list": ["item1", "item2"], "meta": {"count": 2}}'
        expected = {"list": ["item1", "item2"], "meta": {"count": 2}}
        self.assertEqual(parse_json_response(response), expected)

    def test_invalid_json_raises_value_error(self):
        response = "This is just text with no JSON structure."
        with self.assertRaises(ValueError):
            parse_json_response(response)

    def test_markdown_wrapped_json_raises_value_error(self):
        response = """
```json
{"key": "value"}
```
"""
        with self.assertRaises(ValueError):
            parse_json_response(response)


if __name__ == "__main__":
    unittest.main()
