from app.tools.text_utils import redact_sensitive_text, sha256_text


def test_sha256_text_is_stable() -> None:
    text = "backend interview coach"

    assert sha256_text(text) == sha256_text(text)
    assert len(sha256_text(text)) == 64


def test_redact_sensitive_text_redacts_email_and_phone() -> None:
    text = "Call 13800138000 or email user@example.com for details."

    redacted = redact_sensitive_text(text)

    assert "13800138000" not in redacted
    assert "user@example.com" not in redacted
    assert "[REDACTED_PHONE]" in redacted
    assert "[REDACTED_EMAIL]" in redacted


def test_redact_sensitive_text_keeps_non_sensitive_text() -> None:
    text = "FastAPI project with PostgreSQL"

    assert redact_sensitive_text(text) == text

