"""Generate Phase 2.4D-B protocol-v2 review artifacts without Provider access."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.phase_2_4d_b_protocol_review import (  # noqa: E402
    DEFAULT_REVIEW_DIR,
    write_review_artifacts,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Read run1/run2/run3 as immutable evidence and emit an offline-only "
            "Phase 2.4D-B protocol-v2 review."
        )
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_REVIEW_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    artifacts = write_review_artifacts(args.output_dir)
    print(
        json.dumps(
            {name: str(path) for name, path in artifacts.items()},
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
