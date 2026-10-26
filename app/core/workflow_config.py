"""Environment-owned settings for the persistent workflow queue."""

from __future__ import annotations

import os

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class WorkflowSettings(BaseSettings):
    idempotency_secret: str | None = Field(default=None, alias="WORKFLOW_IDEMPOTENCY_SECRET")
    lease_seconds: int = Field(default=60, alias="WORKFLOW_LEASE_SECONDS", ge=10, le=3600)
    absolute_deadline_seconds: int = Field(
        default=600, alias="WORKFLOW_ABSOLUTE_DEADLINE_SECONDS", ge=30, le=7200
    )
    retry_after_seconds: int = Field(default=2, alias="WORKFLOW_RETRY_AFTER_SECONDS", ge=1, le=30)
    max_attempts: int = Field(default=3, alias="WORKFLOW_MAX_ATTEMPTS", ge=1, le=10)

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    def effective_idempotency_secret(self) -> str:
        if self.idempotency_secret:
            return self.idempotency_secret
        if os.getenv("APP_ENV", "").lower() == "test":
            return "phase-2-5d-b-test-only-secret"
        raise RuntimeError("WORKFLOW_IDEMPOTENCY_SECRET is required for asynchronous writes")


def get_workflow_settings() -> WorkflowSettings:
    env_file = None if os.getenv("APP_ENV", "").lower() == "test" else ".env"
    return WorkflowSettings(_env_file=env_file)
