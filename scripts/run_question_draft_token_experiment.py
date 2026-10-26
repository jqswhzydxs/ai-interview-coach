"""Phase 2.4D prompt-only runner CLI.

Phase 2.4D-A authorizes only prepare/status. Real phases remain doubly gated for
a later explicit Phase 2.4D-B authorization.
"""

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
from app.services.question_draft_token_experiment import (
    QuestionDraftTokenExperimentConfig,
    QuestionDraftTokenExperimentRunner,
)


class _IdentityOnlyClient:
    def __init__(self, provider: str, model_name: str) -> None:
        self.provider = provider
        self.model_name = model_name

    async def generate_json(self, request):
        raise AssertionError("Offline prepare/status/finalize must not contact a Provider")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("prepare", "status", "smoke", "pilot", "full", "finalize"))
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument(
        "--input-file", type=Path,
        default=PROJECT_ROOT / "tests/fixtures/question_bank_ab_inputs_v1.json",
    )
    parser.add_argument("--deadline-seconds", type=float, default=120.0)
    parser.add_argument("--max-provider-calls", type=int, default=62)
    parser.add_argument("--max-total-tokens", type=int, default=250_000)
    parser.add_argument("--review-file", type=Path)
    parser.add_argument("--provider-label", default="phase-2.4d-b-unconfigured")
    parser.add_argument("--model-label", default="phase-2.4d-b-unconfigured")
    parser.add_argument("--authorize-phase-2-4d-b-real", action="store_true")
    return parser.parse_args()


def _read_manifest(run_dir: Path) -> dict:
    path = run_dir / "manifest.json"
    if not path.exists():
        raise SystemExit(f"Manifest does not exist: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _status(run_dir: Path) -> int:
    report_path = run_dir / "question-draft-token-report.json"
    if not report_path.exists():
        raise SystemExit(f"Report does not exist: {report_path}")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    print(json.dumps({
        "experiment_id": report["experiment_id"],
        "status": report["status"],
        "completion_status": report["completion_status"],
        "runs": report["summary"]["run_count"],
        "provider_calls": report["budget"]["provider_calls_used"],
        "token_gate": report["summary"]["token_comparison"]["status"],
        "verdict": report["thresholds"]["verdict"],
    }, ensure_ascii=False))
    return 0


def _require_real_authorization(args, settings) -> None:
    if not args.authorize_phase_2_4d_b_real:
        raise SystemExit(
            "Real execution is not authorized in Phase 2.4D-A. "
            "A later 2.4D-B run must pass --authorize-phase-2-4d-b-real explicitly."
        )
    if not settings.run_real_llm_acceptance:
        raise SystemExit("RUN_REAL_LLM_ACCEPTANCE=true is also required for a real run.")
    if settings.save_full_llm_logs:
        raise SystemExit("SAVE_FULL_LLM_LOGS must remain false.")
    provider = settings.llm_provider.lower()
    if provider not in {"deepseek", "kimi"}:
        raise SystemExit("A real Phase 2.4D-B run requires deepseek or kimi.")
    credential = settings.deepseek_api_key if provider == "deepseek" else settings.kimi_api_key
    if not credential:
        raise SystemExit("The configured Provider credential is missing.")


def _config(args) -> QuestionDraftTokenExperimentConfig:
    return QuestionDraftTokenExperimentConfig(
        input_path=args.input_file,
        run_dir=args.run_dir,
        execution_deadline_seconds=args.deadline_seconds,
        max_provider_calls=args.max_provider_calls,
        max_total_tokens=args.max_total_tokens,
    )


async def async_main() -> int:
    args = parse_args()
    if args.phase == "status":
        return _status(args.run_dir)
    if args.phase == "prepare":
        client = _IdentityOnlyClient(args.provider_label, args.model_label)
    elif args.phase == "finalize":
        manifest = _read_manifest(args.run_dir)
        client = _IdentityOnlyClient(manifest["provider"], manifest["model"])
    else:
        settings = get_settings()
        _require_real_authorization(args, settings)
        client = get_llm_client(settings)
    runner = QuestionDraftTokenExperimentRunner(llm_client=client, config=_config(args))
    if args.phase == "prepare":
        artifacts = runner.prepare()
    elif args.phase == "smoke":
        artifacts = await runner.run_smoke()
    elif args.phase == "pilot":
        artifacts = await runner.run_pilot()
    elif args.phase == "full":
        artifacts = await runner.run_full()
    else:
        if args.review_file is None:
            raise SystemExit("--review-file is required for finalize")
        artifacts = runner.apply_blind_review(args.review_file)
    print(json.dumps({
        "status": artifacts.report["status"],
        "completion_status": artifacts.report["completion_status"],
        "manifest": str(artifacts.manifest_path),
        "report": str(artifacts.report_path),
        "provider_calls": artifacts.report["budget"]["provider_calls_used"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(async_main()))
