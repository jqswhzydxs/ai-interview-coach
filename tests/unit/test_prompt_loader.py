import pytest

from app.agents.prompt_loader import PromptNotFoundError, load_prompt


def test_loads_versioned_prompt() -> None:
    prompt = load_prompt("resume_analyzer", "v0.1")

    assert prompt.name == "resume_analyzer"
    assert prompt.version == "v0.1"
    assert "不要编造" in prompt.content
    assert "不自动联网搜索" in prompt.content


def test_missing_prompt_returns_clear_error() -> None:
    with pytest.raises(PromptNotFoundError, match="Prompt not found"):
        load_prompt("missing_agent", "v0.1")


def test_all_mvp_prompts_are_loadable() -> None:
    prompt_names = [
        "resume_analyzer",
        "jd_analyzer",
        "experience_analyzer",
        "matching_agent",
        "question_bank_agent",
        "answer_evaluator",
        "memory_agent",
    ]

    for prompt_name in prompt_names:
        prompt = load_prompt(prompt_name, "v0.1")
        assert prompt.content
        assert prompt.path.name == f"{prompt_name}_v0.1.md"
