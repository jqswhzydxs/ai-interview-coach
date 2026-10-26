"""Create Phase 2.4D-E-B offline Pilot futility artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.question_draft_reasoning_effort_futility_analysis import (  # noqa: E402
    analyze_v4_pilot,
    file_sha256,
    write_analysis_artifacts,
)


DEFAULT_RUN_DIR = (
    PROJECT_ROOT
    / "storage/reports/question-bank-token-phase-2-4d-e-v4-20261024-ab1"
)
DEFAULT_OUTPUT_DIR = (
    PROJECT_ROOT
    / "storage/reports/question-bank-token-phase-2-4d-e-b-offline-20261024"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    run_dir = args.run_dir.resolve()
    output_dir = args.output_dir.resolve()
    if output_dir == run_dir or run_dir in output_dir.parents:
        raise SystemExit("Offline analysis output must be outside the frozen A/B directory")
    report_path = run_dir / "question-draft-reasoning-effort-v4-report.json"
    audit_path = run_dir / "audit/executions.json"
    before = {str(path): file_sha256(path) for path in (report_path, audit_path)}
    artifacts = analyze_v4_pilot(report_path, audit_path)
    written = write_analysis_artifacts(artifacts, output_dir)
    after = {str(path): file_sha256(path) for path in (report_path, audit_path)}
    if before != after:
        raise SystemExit("Frozen v4 source assets changed during offline analysis")
    print(
        json.dumps(
            {
                "status": artifacts.decision["status"],
                "formal_token_gate": artifacts.decision["formal_token_gate"],
                "source_assets_unchanged": True,
                "provider_calls": 0,
                "outputs": {key: str(value) for key, value in written.items()},
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

