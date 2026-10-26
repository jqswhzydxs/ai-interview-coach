"""Phase 2.4C offline replay. No real-acceptance or provider configuration options."""

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.question_bank_metadata_replay import run_metadata_replay


def main():
    parser = argparse.ArgumentParser(description="Offline deterministic metadata comparison and blind-review preparation")
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--input-file", type=Path, default=PROJECT_ROOT / "tests/fixtures/question_bank_ab_inputs_v1.json")
    parser.add_argument("--holdout-file", type=Path, default=PROJECT_ROOT / "tests/fixtures/question_bank_metadata_holdout_v1.json")
    args = parser.parse_args()
    summary = run_metadata_replay(source_dir=args.source_dir, output_dir=args.output_dir, input_file=args.input_file, holdout_file=args.holdout_file)
    print(json.dumps({key: summary[key] for key in ("status", "frozen_candidate_questions", "authored_holdout_questions", "blind_submission_count", "provider_calls", "network_attempts", "source_files_unchanged")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
