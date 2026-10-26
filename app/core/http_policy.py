"""Environment-owned CORS and upload limits kept outside frozen agent config."""

from __future__ import annotations

import os
from urllib.parse import urlsplit

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class HttpPolicySettings(BaseSettings):
    upload_max_bytes: int = Field(
        default=10 * 1024 * 1024,
        alias="UPLOAD_MAX_BYTES",
        gt=0,
    )
    cors_allowed_origins: str = Field(default="", alias="CORS_ALLOWED_ORIGINS")
    cors_allow_credentials: bool = Field(
        default=False,
        alias="CORS_ALLOW_CREDENTIALS",
    )

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    def parsed_cors_origins(self) -> list[str]:
        origins = [
            origin.strip().rstrip("/")
            for origin in self.cors_allowed_origins.split(",")
            if origin.strip()
        ]
        if "*" in origins:
            raise ValueError("CORS_ALLOWED_ORIGINS must not contain wildcard origins")
        for origin in origins:
            parsed = urlsplit(origin)
            if (
                "*" in origin
                or parsed.scheme not in {"http", "https"}
                or not parsed.netloc
                or parsed.path not in {"", "/"}
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError("CORS_ALLOWED_ORIGINS must contain exact HTTP origins")
        return list(dict.fromkeys(origins))


def get_http_policy_settings() -> HttpPolicySettings:
    env_file = None if os.getenv("APP_ENV", "").lower() == "test" else ".env"
    return HttpPolicySettings(_env_file=env_file)
