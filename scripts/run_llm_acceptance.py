import argparse
import asyncio
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.agents.llm_client import get_llm_client
from app.agents.mock_client import MockLLMClient
from app.core.config import get_settings
from app.db.base import Base, import_models
from app.db.models.user import User
from app.services.llm_acceptance_service import LLMAcceptanceRunner


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the three synthetic LLM acceptance cases and write safe JSON/Markdown reports."
    )
    parser.add_argument(
        "--sample-dir",
        type=Path,
        default=PROJECT_ROOT / "tests" / "fixtures" / "sample_cases",
    )
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Use the local mock path; never contacts a provider.",
    )
    return parser.parse_args()


async def async_main() -> int:
    args = parse_args()
    settings = get_settings()
    if args.dry_run:
        client = MockLLMClient(model_name="mock-acceptance-dry-run")
    else:
        if not settings.run_real_llm_acceptance:
            raise SystemExit(
                "Real acceptance is disabled. Set RUN_REAL_LLM_ACCEPTANCE=true explicitly."
            )
        if settings.llm_provider.lower() not in {"deepseek", "kimi"}:
            raise SystemExit("LLM_PROVIDER must be deepseek or kimi for real acceptance.")
        if settings.llm_provider.lower() == "deepseek" and not settings.deepseek_api_key:
            raise SystemExit("The configured DeepSeek credential is missing.")
        if settings.llm_provider.lower() == "kimi" and not settings.kimi_api_key:
            raise SystemExit("The configured Kimi credential is missing.")
        client = get_llm_client(settings)

    import_models()
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    with SessionLocal() as db:
        db.add(
            User(
                id=settings.default_user_id,
                display_name="LLM Acceptance Runner",
                role="candidate",
            )
        )
        db.commit()
        artifacts = await LLMAcceptanceRunner(
            llm_client=client,
            report_dir=args.output_dir or settings.report_dir,
            input_cost_per_million=settings.llm_input_cost_per_million,
            output_cost_per_million=settings.llm_output_cost_per_million,
            cost_currency=settings.llm_cost_currency,
        ).run(
            db=db,
            user_id=settings.default_user_id,
            sample_dir=args.sample_dir,
        )

    print(f"JSON report: {artifacts.json_path}")
    print(f"Markdown report: {artifacts.markdown_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(async_main()))
