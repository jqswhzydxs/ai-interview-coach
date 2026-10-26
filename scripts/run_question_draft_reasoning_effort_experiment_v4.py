"""Readiness-gated Phase 2.4D-E-A reasoning-effort protocol v4 A/B CLI.

The CLI is independent from the protocol v1 command.  Real smoke/pilot/full
phases remain disabled unless both environment and explicit CLI gates pass.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.agents.deepseek_reasoning_effort_experiment_client import (  # noqa: E402
    DeepSeekReasoningEffortExperimentClient,
)
from app.core.config import get_settings  # noqa: E402
from app.services.question_draft_provider_readiness_v4 import (  # noqa: E402
    DEFAULT_FIXTURE_PATH,
)
from app.services.question_draft_reasoning_effort_experiment_v4 import (  # noqa: E402
    QuestionDraftReasoningExperimentV4Config,
    QuestionDraftReasoningExperimentV4Runner,
)


class _IdentityOnlyClient:
    def __init__(self, provider: str, model_name: str, reasoning_effort: str) -> None:
        self.provider = provider
        self.model_name = model_name
        self.thinking_type = "enabled"
        self.reasoning_effort = reasoning_effort

    async def generate_json(self, request):
        raise AssertionError("Offline protocol v4 phase must not call a Provider")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "phase", choices=("prepare", "status", "smoke", "pilot", "full", "finalize")
    )
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--readiness-ledger", type=Path, required=True)
    parser.add_argument("--input-file", type=Path, default=DEFAULT_FIXTURE_PATH)
    parser.add_argument("--provider-label")
    parser.add_argument("--model-label")
    parser.add_argument("--review-file", type=Path)
    parser.add_argument("--authorize-phase-2-4d-e-a-smoke", action="store_true")
    parser.add_argument("--authorize-phase-2-4d-e-a-pilot", action="store_true")
    parser.add_argument("--authorize-phase-2-4d-e-a-full", action="store_true")
    return parser.parse_args()


def _read_manifest(run_dir: Path) -> dict:
    path = run_dir / "manifest.json"
    if not path.exists():
        raise SystemExit(f"Manifest does not exist: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _status(run_dir: Path) -> int:
    path = run_dir / "question-draft-reasoning-effort-v4-report.json"
    if not path.exists():
        raise SystemExit(f"Protocol v4 report does not exist: {path}")
    report = json.loads(path.read_text(encoding="utf-8"))
    print(
        json.dumps(
            {
                "protocol_version": report["protocol_version"],
                "experiment_id": report["experiment_id"],
                "status": report["status"],
                "completion_status": report["completion_status"],
                "readiness_ledger_sha256": report["readiness"]["sha256"],
                "runs": report["summary"]["run_count"],
                "provider_calls": report["budget"]["provider_call_budget"]["used"],
                "token_gate": report["summary"]["token_comparison"]["status"],
                "verdict": report["thresholds"]["verdict"],
            },
            ensure_ascii=False,
        )
    )
    return 0


def require_real_ab_authorization(args, settings, phase: str) -> None:
    flag = f"authorize_phase_2_4d_e_a_{phase}"
    if phase not in {"smoke", "pilot", "full"} or not getattr(args, flag, False):
        raise SystemExit(
            f"Real {phase} requires --authorize-phase-2-4d-e-a-{phase}."
        )
    if not settings.run_real_llm_acceptance:
        raise SystemExit("RUN_REAL_LLM_ACCEPTANCE=true is required.")
    if settings.save_full_llm_logs:
        raise SystemExit("SAVE_FULL_LLM_LOGS must remain false.")
    provider = settings.llm_provider.lower()
    if provider != "deepseek":
        raise SystemExit("Protocol v4 requires Provider deepseek.")
    credential = settings.deepseek_api_key
    if not credential:
        raise SystemExit("The configured Provider credential is missing.")
    if settings.llm_model != "deepseek-v4-pro":
        raise SystemExit("Protocol v4 requires LLM_MODEL=deepseek-v4-pro.")


def _identity_clients(provider: str, model: str) -> dict[str, _IdentityOnlyClient]:
    return {
        "baseline": _IdentityOnlyClient(provider, model, "high"),
        "candidate": _IdentityOnlyClient(provider, model, "low"),
    }


def _real_clients(settings) -> dict[str, DeepSeekReasoningEffortExperimentClient]:
    return {
        "baseline": DeepSeekReasoningEffortExperimentClient(
            api_key=settings.deepseek_api_key,
            model_name=settings.llm_model,
            reasoning_effort="high",
        ),
        "candidate": DeepSeekReasoningEffortExperimentClient(
            api_key=settings.deepseek_api_key,
            model_name=settings.llm_model,
            reasoning_effort="low",
        ),
    }


def _config(args) -> QuestionDraftReasoningExperimentV4Config:
    return QuestionDraftReasoningExperimentV4Config(
        run_dir=args.run_dir,
        readiness_ledger_path=args.readiness_ledger,
        input_path=args.input_file,
    )


async def async_main() -> int:
    args = parse_args()
    if args.phase == "status":
        return _status(args.run_dir)
    if args.phase == "prepare":
        if not args.provider_label or not args.model_label:
            raise SystemExit(
                "prepare requires explicit --provider-label and --model-label."
            )
        clients = _identity_clients(args.provider_label, args.model_label)
    elif args.phase == "finalize":
        manifest = _read_manifest(args.run_dir)
        clients = _identity_clients(manifest["provider"], manifest["model"])
    else:
        settings = get_settings()
        require_real_ab_authorization(args, settings, args.phase)
        clients = _real_clients(settings)
    runner = QuestionDraftReasoningExperimentV4Runner(
        llm_clients=clients,
        config=_config(args),
    )
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
    print(
        json.dumps(
            {
                "status": artifacts.report["status"],
                "completion_status": artifacts.report["completion_status"],
                "manifest": str(artifacts.manifest_path),
                "report": str(artifacts.report_path),
                "readiness_ledger_sha256": artifacts.report["readiness"]["sha256"],
                "provider_calls": artifacts.report["budget"]["provider_call_budget"]["used"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(async_main()))
