"""Input node for loading prompt, file, and personas."""

import os

import yaml
from pocketflow import Node

from council.console import print_council_header, print_error, print_warning
from council.models import Persona, ProviderConfig

# File size limits
WARN_SIZE_BYTES = 1 * 1024 * 1024  # 1 MB
MAX_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB


def load_personas(personas_path: str) -> list[Persona]:
    """Load personas from a YAML file.

    Supports per-persona provider configuration and a default_provider
    that applies to all personas without explicit provider config.

    Args:
        personas_path: Path to the personas YAML file

    Returns:
        List of Persona objects with provider configurations
    """
    with open(personas_path, "r") as f:
        data = yaml.safe_load(f)

    # Load default provider config (used when persona doesn't specify one)
    default_provider_data = data.get("default_provider", {})
    default_provider = ProviderConfig(
        api_key=default_provider_data.get("api_key", "$OPENAI_API_KEY"),
        base_url=default_provider_data.get(
            "base_url", "https://api.openai.com/v1"
        ),
        model=default_provider_data.get("model", "gpt-4o"),
    )

    personas = []
    for p in data.get("personas", []):
        # Load persona-specific provider or use default
        provider_data = p.get("provider", {})
        if provider_data:
            provider = ProviderConfig(
                api_key=provider_data.get("api_key", default_provider.api_key),
                base_url=provider_data.get(
                    "base_url", default_provider.base_url
                ),
                model=provider_data.get("model", default_provider.model),
            )
        else:
            provider = default_provider

        personas.append(
            Persona(
                name=p["name"],
                role=p["role"],
                focus=p["focus"],
                style=p["style"],
                temperature=p.get("temperature", 0.7),
                provider=provider,
            )
        )

    return personas


def load_file_content(file_path: str) -> str:
    """Load and validate file content.

    Args:
        file_path: Path to the file to load

    Returns:
        File content as string

    Raises:
        ValueError: If file is too large
        FileNotFoundError: If file doesn't exist
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    file_size = os.path.getsize(file_path)

    if file_size > MAX_SIZE_BYTES:
        raise ValueError(
            f"File is too large ({file_size / 1024 / 1024:.1f} MB). "
            f"Maximum allowed size is {MAX_SIZE_BYTES / 1024 / 1024:.0f} MB."
        )

    if file_size > WARN_SIZE_BYTES:
        print_warning(
            f"File is large ({file_size / 1024 / 1024:.1f} MB). "
            "Processing may be slow."
        )

    with open(file_path, "r") as f:
        return f.read()


class InputNode(Node):
    """Node for loading and validating inputs.

    Reads CLI arguments from shared store (set by main.py),
    loads file content and personas, and initializes discussion state.
    """

    def prep(self, shared):
        """Read CLI arguments from shared store."""
        return {
            "prompt": shared.get("prompt"),
            "file_path": shared.get("file_path"),
            "personas_path": shared.get("personas_path"),
            "max_turns": shared.get("max_turns", 3),
            "show_stream": shared.get("show_stream", False),
            "output_dir": shared.get("output_dir", "."),
        }

    def exec(self, prep_res):
        """Load file content and personas."""
        result = {
            "prompt": prep_res["prompt"],
            "file_content": None,
            "file_path": prep_res["file_path"],
            "personas": [],
            "config": {
                "max_turns": prep_res["max_turns"],
                "show_stream": prep_res["show_stream"],
                "output_dir": prep_res["output_dir"],
            },
        }

        # Load file content if provided
        if prep_res["file_path"]:
            result["file_content"] = load_file_content(prep_res["file_path"])

        # Load personas
        personas_path = prep_res["personas_path"]
        if not personas_path:
            # Use default personas
            default_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "config",
                "default_personas.yaml",
            )
            personas_path = default_path

        result["personas"] = load_personas(personas_path)

        return result

    def exec_fallback(self, prep_res, exc):
        """Handle errors gracefully."""
        print_error(f"Loading inputs: {exc}")
        return None

    def post(self, shared, prep_res, exec_res):
        """Initialize shared state for the discussion."""
        if exec_res is None:
            return "error"

        # Set up shared state
        shared["prompt"] = exec_res["prompt"]
        shared["file_content"] = exec_res["file_content"]
        shared["file_path"] = exec_res["file_path"]
        shared["personas"] = exec_res["personas"]
        shared["config"] = exec_res["config"]

        # Initialize discussion tracking
        shared["proposals"] = []
        shared["debate_messages"] = []
        shared["current_turn"] = 0
        shared["consensus_reached"] = False

        if exec_res["config"]["show_stream"]:
            print_council_header(
                prompt=exec_res["prompt"],
                file_path=exec_res["file_path"],
                personas=exec_res["personas"],
                max_turns=exec_res["config"]["max_turns"],
            )

        return "default"
