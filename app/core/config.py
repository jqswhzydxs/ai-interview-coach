from functools import lru_cache
import os
from pathlib import Path
from decimal import Decimal
from uuid import UUID

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = Field(default="local", alias="APP_ENV")
    app_name: str = Field(default="ai-interview-coach", alias="APP_NAME")
    database_url: str = Field(
        default="postgresql+psycopg://postgres:postgres@localhost:5432/interview_coach",
        alias="DATABASE_URL",
    )
    upload_dir: Path = Field(default=Path("storage/uploads"), alias="UPLOAD_DIR")
    report_dir: Path = Field(default=Path("storage/reports"), alias="REPORT_DIR")
    default_user_id: UUID = Field(
        default=UUID("00000000-0000-0000-0000-000000000001"),
        alias="DEFAULT_USER_ID",
    )
    llm_provider: str = Field(default="mock", alias="LLM_PROVIDER")
    llm_model: str = Field(default="", alias="LLM_MODEL")
    deepseek_api_key: str = Field(default="", alias="DEEPSEEK_API_KEY")
    kimi_api_key: str = Field(default="", alias="KIMI_API_KEY")
    save_full_llm_logs: bool = Field(default=False, alias="SAVE_FULL_LLM_LOGS")
    run_real_llm_acceptance: bool = Field(default=False, alias="RUN_REAL_LLM_ACCEPTANCE")
    llm_input_cost_per_million: Decimal | None = Field(
        default=None,
        alias="LLM_INPUT_COST_PER_MILLION",
        ge=0,
    )
    llm_output_cost_per_million: Decimal | None = Field(
        default=None,
        alias="LLM_OUTPUT_COST_PER_MILLION",
        ge=0,
    )
    llm_cost_currency: str = Field(default="USD", alias="LLM_COST_CURRENCY")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    # Tests must be hermetic: APP_ENV=test means process environment only.
    # Real smoke tests can still pass explicit environment variables, but pytest
    # never imports the developer .env implicitly.
    env_file = None if os.getenv("APP_ENV", "").lower() == "test" else ".env"
    return Settings(_env_file=env_file)
