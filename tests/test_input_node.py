from pathlib import Path

from council.nodes.input_node import load_personas


def test_load_personas_defaults_prompt_cache_fields_from_default_config():
    config_path = (
        Path(__file__).parents[1]
        / "src"
        / "council"
        / "config"
        / "default_personas.yaml"
    )

    personas = load_personas(str(config_path))

    assert personas
    assert all(persona.provider.prompt_cache is False for persona in personas)
    assert all(
        persona.provider.prompt_cache_strategy == "none"
        for persona in personas
    )


def test_load_personas_inherits_prompt_cache_fields_from_default_provider(
    tmp_path,
):
    config_path = tmp_path / "personas.yaml"
    config_path.write_text(
        """
default_provider:
  api_key: test-key
  base_url: https://example.test/v1
  model: test-model
  prompt_cache: true
  prompt_cache_strategy: openai_compatible_auto
personas:
  - name: Agent
    role: Reviewer
    focus: Testing
    style: Concise
""".strip()
    )

    personas = load_personas(str(config_path))

    assert len(personas) == 1
    assert personas[0].provider.prompt_cache is True
    assert personas[0].provider.prompt_cache_strategy == "openai_compatible_auto"


def test_load_personas_allows_persona_prompt_cache_override(tmp_path):
    config_path = tmp_path / "personas.yaml"
    config_path.write_text(
        """
default_provider:
  api_key: test-key
  base_url: https://example.test/v1
  model: test-model
  prompt_cache: true
  prompt_cache_strategy: openai_compatible_auto
personas:
  - name: Agent
    role: Reviewer
    focus: Testing
    style: Concise
    provider:
      prompt_cache: false
      prompt_cache_strategy: none
""".strip()
    )

    personas = load_personas(str(config_path))

    assert personas[0].provider.api_key == "test-key"
    assert personas[0].provider.base_url == "https://example.test/v1"
    assert personas[0].provider.model == "test-model"
    assert personas[0].provider.prompt_cache is False
    assert personas[0].provider.prompt_cache_strategy == "none"
