"""Phase 2.4D-D-A single-ledger Provider readiness CLI.

``prepare`` and ``status`` are offline.  ``attempt`` is disabled unless both the
environment gate and the explicit command-line authorization are present.
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

from app.agents.deepseek_thinking_experiment_client import (  # noqa: E402
    DeepSeekThinkingExperimentClient,
)
from app.core.config import get_settings  # noqa: E402
from app.services.question_draft_provider_readiness_v3 import (  # noqa: E402
    DEFAULT_FIXTURE_PATH,
    QuestionDraftProviderReadinessV3Config,
    QuestionDraftProviderReadinessV3Runner,
    readiness_status_from_path,
)


class _IdentityOnlyClient:
    def __init__(self, provider: str, model_name: str) -> None:
        self.provider = provider
        self.model_name = model_name
        self.thinking_type = "disabled"

    async def generate_json(self, request):
        raise AssertionError("Offline readiness prepare must not call a Provider")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("prepare", "attempt", "status"))
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE_PATH)
    parser.add_argument("--provider-label")
    parser.add_argument("--model-label")
    parser.add_argument(
        "--authorize-phase-2-4d-d-a-readiness",
        action="store_true",
    )
    return parser.parse_args()


def require_real_readiness_authorization(args, settings) -> None:
    if not args.authorize_phase_2_4d_d_a_readiness:
        raise SystemExit(
            "Readiness attempt requires --authorize-phase-2-4d-d-a-readiness."
        )
    if not settings.run_real_llm_acceptance:
        raise SystemExit("RUN_REAL_LLM_ACCEPTANCE=true is required.")
    if settings.save_full_llm_logs:
        raise SystemExit("SAVE_FULL_LLM_LOGS must remain false.")
    provider = settings.llm_provider.lower()
    if provider != "deepseek":
        raise SystemExit("Protocol v3 readiness requires Provider deepseek.")
    credential = settings.deepseek_api_key
    if not credential:
        raise SystemExit("The configured Provider credential is missing.")
    if settings.llm_model != "deepseek-v4-pro":
        raise SystemExit("Protocol v3 readiness requires LLM_MODEL=deepseek-v4-pro.")


async def async_main() -> int:
    args = parse_args()
    if args.phase == "status":
        print(json.dumps(readiness_status_from_path(args.ledger), ensure_ascii=False))
        return 0
    if args.phase == "prepare":
        if not args.provider_label or not args.model_label:
            raise SystemExit(
                "prepare requires explicit --provider-label and --model-label."
            )
        client = _IdentityOnlyClient(args.provider_label, args.model_label)
    else:
        settings = get_settings()
        require_real_readiness_authorization(args, settings)
        client = DeepSeekThinkingExperimentClient(
            api_key=settings.deepseek_api_key,
            model_name=settings.llm_model,
            thinking_type="disabled",
        )
    runner = QuestionDraftProviderReadinessV3Runner(
        llm_client=client,
        config=QuestionDraftProviderReadinessV3Config(
            ledger_path=args.ledger,
            fixture_path=args.fixture,
        ),
    )
    artifacts = runner.prepare() if args.phase == "prepare" else await runner.attempt()
    print(
        json.dumps(
            {
                "status": artifacts.ledger["status"],
                "attempts_used": len(artifacts.ledger["attempts"]),
                "attempts_limit": artifacts.ledger["max_attempts"],
                "ledger": str(artifacts.ledger_path),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(async_main()))
