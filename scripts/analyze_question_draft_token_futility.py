"""Generate the offline-only Phase 2.4D-C Pilot futility analysis."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.question_draft_token_futility_analysis import (  # noqa: E402
    DEFAULT_AB1_DIR,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_READINESS_LEDGER,
    write_analysis_artifacts,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ab1-dir", type=Path, default=DEFAULT_AB1_DIR)
    parser.add_argument(
        "--readiness-ledger", type=Path, default=DEFAULT_READINESS_LEDGER
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    artifacts = write_analysis_artifacts(
        args.output_dir,
        ab1_dir=args.ab1_dir,
        readiness_ledger=args.readiness_ledger,
    )
    decision = json.loads(
        artifacts["early-stop-decision.json"].read_text(encoding="utf-8")
    )
    print(
        json.dumps(
            {
                "status": decision["decision_status"],
                "formal_final_gate_status": decision["formal_final_gate_status"],
                "prompt_v0_2_promoted": decision["prompt_v0_2_promoted"],
                "network_accessed": False,
                "artifacts": {key: str(value) for key, value in artifacts.items()},
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
