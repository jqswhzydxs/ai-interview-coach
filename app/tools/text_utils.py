import hashlib
import re


PHONE_PATTERN = re.compile(r"(?<!\d)(?:\+?86[-\s]?)?1[3-9]\d{9}(?!\d)")
EMAIL_PATTERN = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def redact_sensitive_text(text: str) -> str:
    redacted = PHONE_PATTERN.sub("[REDACTED_PHONE]", text)
    return EMAIL_PATTERN.sub("[REDACTED_EMAIL]", redacted)

