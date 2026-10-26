"""Generate the offline Phase 2.4D-F-B final protocol v5 analysis."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.question_draft_prompt_recovery_final_analysis import (  # noqa: E402
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
        artifacts["final-decision-record.json"].read_text(encoding="utf-8")
    )
    print(
        json.dumps(
            {
                "status": "complete",
                "protocol_v5_verdict": decision["final_decision"],
                "candidate_promotion": decision["candidate_promotion"],
                "provider_calls": 0,
                "network_accessed": False,
                "artifacts": {name: str(path) for name, path in artifacts.items()},
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


