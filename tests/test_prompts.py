from council.prompts import Prompt, PromptPart


def test_prompt_to_text_preserves_part_order():
    prompt = Prompt(
        parts=[
            PromptPart(name="first", content="First section"),
            PromptPart(name="second", content="Second section"),
            PromptPart(name="third", content="Third section"),
        ]
    )

    assert prompt.to_text() == "First section\n\nSecond section\n\nThird section"


def test_prompt_to_text_skips_empty_content():
    prompt = Prompt(
        parts=[
            PromptPart(name="empty", content=""),
            PromptPart(name="stable", content="Stable section", cacheable=True),
            PromptPart(name="also_empty", content=""),
            PromptPart(name="volatile", content="Current turn"),
        ]
    )

    assert prompt.to_text() == "Stable section\n\nCurrent turn"


def test_prompt_to_text_is_deterministic():
    prompt = Prompt(
        parts=[
            PromptPart(name="instructions", content="Use this format."),
            PromptPart(name="question", content="What should we build?"),
        ]
    )

    assert prompt.to_text() == prompt.to_text()
