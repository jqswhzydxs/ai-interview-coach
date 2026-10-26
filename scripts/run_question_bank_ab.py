import argparse
import asyncio
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.agents.llm_client import get_llm_client
from app.core.config import get_settings
from app.services.question_bank_ab_service import (
    QuestionBankABConfig,
    QuestionBankABRunner,
)


class _ManifestIdentityClient:
    def __init__(self, provider: str, model_name: str) -> None:
        self.provider = provider
        self.model_name = model_name

    async def generate_json(self, request):
        raise AssertionError("Finalize must not contact a provider")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run the Phase 2.4B paired QuestionBank-only real A/B. "
            "Use smoke, pilot, and full as separate gated phases."
        )
    )
    parser.add_argument(
        "phase",
        choices=("smoke", "pilot", "full", "finalize", "status"),
    )
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument(
        "--input-file",
        type=Path,
        default=PROJECT_ROOT / "tests/fixtures/question_bank_ab_inputs_v1.json",
    )
    parser.add_argument("--max-provider-calls", type=int, default=61)
    parser.add_argument("--max-total-tokens", type=int, default=250_000)
    parser.add_argument("--deadline-seconds", type=float, default=120.0)
    parser.add_argument("--review-file", type=Path, default=None)
    return parser.parse_args()


def _print_status(run_dir: Path) -> int:
    report_path = run_dir / "question-bank-ab-report.json"
    if not report_path.exists():
        raise SystemExit(f"A/B report does not exist: {report_path}")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    print(
        json.dumps(
            {
                "experiment_id": report["experiment_id"],
                "status": report["status"],
                "completion_status": report["completion_status"],
                "stop_reason": report.get("stop_reason"),
                "executions": report["summary"]["run_count"],
                "provider_calls_used": report["budget"]["provider_calls_used"],
                "total_tokens_used": report["budget"]["total_tokens_used"],
                "threshold_verdict": report["thresholds"]["verdict"],
            },
            ensure_ascii=False,
        )
    )
    return 0


def _require_real_acceptance_settings(settings) -> None:
    if not settings.run_real_llm_acceptance:
        raise SystemExit(
            "Real A/B is disabled. Set RUN_REAL_LLM_ACCEPTANCE=true explicitly."
        )
    if settings.save_full_llm_logs:
        raise SystemExit("SAVE_FULL_LLM_LOGS must remain false for Phase 2.4B.")
    provider = settings.llm_provider.lower()
    if provider not in {"deepseek", "kimi"}:
        raise SystemExit("LLM_PROVIDER must be deepseek or kimi for real A/B.")
    if provider == "deepseek" and not settings.deepseek_api_key:
        raise SystemExit("The configured DeepSeek credential is missing.")
    if provider == "kimi" and not settings.kimi_api_key:
        raise SystemExit("The configured Kimi credential is missing.")


async def async_main() -> int:
    args = parse_args()
    if args.phase == "status":
        return _print_status(args.run_dir)

    if args.phase == "finalize":
        manifest_path = args.run_dir / "manifest.json"
        if not manifest_path.exists():
            raise SystemExit(f"A/B manifest does not exist: {manifest_path}")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        client = _ManifestIdentityClient(manifest["provider"], manifest["model"])
    else:
        settings = get_settings()
        _require_real_acceptance_settings(settings)
        client = get_llm_client(settings)
    runner = QuestionBankABRunner(
        llm_client=client,
        config=QuestionBankABConfig(
            input_path=args.input_file,
            run_dir=args.run_dir,
            max_provider_calls=args.max_provider_calls,
            max_total_tokens=args.max_total_tokens,
            execution_deadline_seconds=args.deadline_seconds,
        ),
    )
    if args.phase == "smoke":
        artifacts = await runner.run_smoke()
    elif args.phase == "pilot":
        artifacts = await runner.run_pilot()
    elif args.phase == "full":
        artifacts = await runner.run_full()
    else:
        if args.review_file is None:
            raise SystemExit("--review-file is required for finalize")
        artifacts = runner.apply_blind_reviews(args.review_file)

    print(f"Status: {artifacts.report['status']}")
    print(f"Completion: {artifacts.report['completion_status']}")
    print(f"Manifest: {artifacts.manifest_path}")
    print(f"JSON report: {artifacts.report_json_path}")
    print(f"Markdown report: {artifacts.report_markdown_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(async_main()))
