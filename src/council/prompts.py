"""Small prompt representation helpers."""

from dataclasses import dataclass


@dataclass(frozen=True)
class PromptPart:
    """A named prompt section kept separate for future rendering strategies."""

    name: str
    content: str
    cacheable: bool = False


@dataclass(frozen=True)
class Prompt:
    """Ordered prompt parts that render to plain text deterministically."""

    parts: list[PromptPart]

    def to_text(self) -> str:
        """Join non-empty part content in order, separated by blank lines."""
        return "\n\n".join(part.content for part in self.parts if part.content)
