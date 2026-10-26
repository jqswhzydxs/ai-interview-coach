from app.core.config import get_settings
from app.services.agent_run_service import summarize_payload


def test_default_llm_logging_is_safe_and_mock_remains_default(monkeypatch) -> None:
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("SAVE_FULL_LLM_LOGS", raising=False)
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.llm_provider == "mock"
    assert settings.save_full_llm_logs is False
    assert summarize_payload(
        {"raw_text": "complete resume", "user_answer": "complete answer"}
    ) == {"keys": ["raw_text", "user_answer"]}


def test_opt_in_full_logging_still_redacts_sensitive_content(monkeypatch) -> None:
    monkeypatch.setenv("SAVE_FULL_LLM_LOGS", "true")
    get_settings.cache_clear()

    summary = summarize_payload(
        {
            "raw_text": "complete resume",
            "jd_profile": {"company": "sensitive company", "requirements": ["secret"]},
            "api_key": "never-store-this",
            "preparation_goal": "backend interview",
        }
    )
    rendered = str(summary)

    assert "complete resume" not in rendered
    assert "sensitive company" not in rendered
    assert "never-store-this" not in rendered
    assert summary["payload"]["preparation_goal"] == "backend interview"
    assert summary["payload"]["raw_text"]["redacted"] is True

    get_settings.cache_clear()
