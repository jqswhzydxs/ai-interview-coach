"""Finalize a completed Phase 2.4C metadata review without provider access."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.question_bank_metadata_finalizer import finalize_metadata_review


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate and finalize a Phase 2.4C metadata review offline"
    )
    parser.add_argument("--template", type=Path, required=True)
    parser.add_argument("--mapping", type=Path, required=True)
    parser.add_argument("--replayed-banks", type=Path, required=True)
    parser.add_argument("--completed-review", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-markdown", type=Path, required=True)
    args = parser.parse_args()
    report = finalize_metadata_review(
        template_path=args.template,
        mapping_path=args.mapping,
        replayed_banks_path=args.replayed_banks,
        completed_review_path=args.completed_review,
        output_json_path=args.output_json,
        output_markdown_path=args.output_markdown,
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "metadata_v2_quality_gate": report["decision"][
                    "metadata_v2_quality_gate"
                ],
                "production_integration_performed": False,
                "provider_calls": 0,
                "network_attempts": report["safety"]["network_attempts"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
