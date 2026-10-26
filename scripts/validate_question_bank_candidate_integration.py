"""Offline-only Candidate validation: no Provider configuration or invocation."""

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.services.question_bank_candidate_validation import validate_candidate_integration


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    report = validate_candidate_integration(output_dir=args.output_dir)
    print(json.dumps({k: report[k] for k in ("status", "replay_banks", "holdout_banks", "assembly_executions", "provider_calls", "network_attempts", "protected_write_attempts", "protected_inputs_unchanged")}))


if __name__ == "__main__":
    main()
