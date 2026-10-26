from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from app.services.question_bank_metadata_finalizer import (
    MetadataReviewInputChangedError,
    MetadataReviewValidationError,
    REVIEW_VERSION,
    finalize_metadata_review,
)


FIELDS = ("purpose", "source", "framework", "anchors", "follow_up", "advice")
STACK_TEXTS = (
    "How would you design this service in Go using goroutines safely?",
    "How would you implement this service with Java and Spring Boot?",
    "How would you test this Python FastAPI service?",
    "How does Rust ownership affect an Axum handler?",
    "How would TypeScript and Node.js structure this Express service?",
)


def write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def synthetic_inputs(tmp_path: Path, *, replay_v2=4, holdout_v2=4):
    root = tmp_path / "metadata-finalizer"
    mapping = []
    banks = []
    template_submissions = []
    completed_submissions = []
    corpus_specs = [
        (
            f"replay-{index:02d}",
            "frozen_run2",
            STACK_TEXTS[(index - 1) % 3],
        )
        for index in range(1, 16)
    ] + [
        ("holdout-rust", "authored_holdout", STACK_TEXTS[3]),
        (
            "holdout-transition",
            "authored_holdout",
            "How would you transfer Python experience to a Go service?",
        ),
        (
            "holdout-java",
            "authored_holdout",
            "请说明 Java Spring 服务的事务边界。",
        ),
        ("holdout-typescript", "authored_holdout", STACK_TEXTS[4]),
    ]
    for corpus_index, (corpus_id, partition, question_text) in enumerate(
        corpus_specs,
        1,
    ):
        for version in ("v1", "v2"):
            submission_id = f"metadata-{corpus_index:02d}-{version}"
            mapping.append(
                {
                    "submission_id": submission_id,
                    "version": version,
                    "corpus_id": corpus_id,
                    "partition": partition,
                }
            )
            questions = [
                {
                    "question_text": f"{question_text} Position {position}.",
                }
                for position in range(1, 26)
            ]
            banks.append(
                {
                    "corpus_id": corpus_id,
                    "version": version,
                    "bank": {
                        "self_intro_questions": questions[:8],
                        "professional_questions": questions[8:16],
                        "behavior_project_questions": questions[16:],
                        "total_count": 25,
                    },
                }
            )
            template_submissions.append(
                {
                    "submission_id": submission_id,
                    "metadata_fit_scores": [None] * 25,
                    "field_notes": {field: "" for field in FIELDS},
                }
            )
            if version == "v1":
                score = 3
            elif partition == "frozen_run2":
                score = replay_v2
            else:
                score = holdout_v2
            completed_submissions.append(
                {
                    "submission_id": submission_id,
                    "metadata_fit_scores": [score] * 25,
                    "field_notes": {
                        field: (
                            f"Synthetic {field} issue"
                            if field == "framework" and version == "v1"
                            else ""
                        )
                        for field in FIELDS
                    },
                }
            )

    template = {
        "review_version": REVIEW_VERSION,
        "scale": "1-5",
        "evaluator": {
            "type": None,
            "identifier": None,
            "independence_confirmed": None,
        },
        "instructions": "synthetic",
        "submissions": template_submissions,
    }
    completed = {
        "review_version": REVIEW_VERSION,
        "scale": "1-5",
        "evaluator": {
            "type": "ai",
            "identifier": "synthetic-independent-reviewer",
            "independence_confirmed": True,
        },
        "instructions": "synthetic",
        "submissions": completed_submissions,
    }
    paths = {
        "template": root / "blind-review" / "metadata-review-template.json",
        "mapping": root / "audit" / "private-blinding-map.json",
        "banks": root / "audit" / "replayed-question-banks.json",
        "completed": root / "blind-review" / "metadata-review-completed.json",
        "output_json": root / "metadata-review-final-report.json",
        "output_md": root / "metadata-review-final-report.md",
    }
    write_json(paths["template"], template)
    write_json(
        paths["mapping"],
        {"do_not_distribute_to_reviewers": True, "mapping": mapping},
    )
    write_json(paths["banks"], {"banks": banks})
    write_json(paths["completed"], completed)
    return paths


def finalize(paths):
    return finalize_metadata_review(
        template_path=paths["template"],
        mapping_path=paths["mapping"],
        replayed_banks_path=paths["banks"],
        completed_review_path=paths["completed"],
        output_json_path=paths["output_json"],
        output_markdown_path=paths["output_md"],
    )


def test_full_synthetic_review_passes_both_frozen_gates_and_writes_two_reports(
    tmp_path,
):
    paths = synthetic_inputs(tmp_path)
    before = {
        key: path.read_bytes()
        for key, path in paths.items()
        if key in {"template", "mapping", "banks", "completed"}
    }

    report = finalize(paths)

    assert report["status"] == "passed"
    assert report["gate_policy"]["all_required_gates_passed"] is True
    assert report["score_summary"]["partitions"]["replay_candidate"]["versions"][
        "v2"
    ]["mean"] == 4
    assert report["score_summary"]["partitions"]["holdout"]["versions"]["v2"][
        "mean"
    ] == 4
    assert report["score_summary"]["overall"]["versions"]["v1"]["mean"] == 3
    assert report["paired_improvement"]["overall"][
        "bank_level_win_tie_loss"
    ] == {"win": 19, "tie": 0, "loss": 0}
    assert report["validation"]["total_score_count"] == 950
    assert report["evaluator"]["type"] == "ai"
    assert report["decision"]["eligible_for_separate_production_integration_decision"] is True
    assert report["decision"]["production_integration_performed"] is False
    assert report["safety"]["provider_calls"] == 0
    assert report["safety"]["network_attempts"] == 0
    assert paths["output_json"].is_file()
    assert paths["output_md"].is_file()
    assert "Evaluator type (exact): `ai`" in paths["output_md"].read_text(
        encoding="utf-8"
    )
    assert {
        key: path.read_bytes()
        for key, path in paths.items()
        if key in {"template", "mapping", "banks", "completed"}
    } == before


def test_failed_replay_gate_forbids_production_eligibility(tmp_path):
    paths = synthetic_inputs(tmp_path, replay_v2=3, holdout_v2=4)

    report = finalize(paths)

    assert report["status"] == "failed"
    assert report["gate_policy"]["required_gates"][
        "replay_candidate_metadata_v2_mean"
    ]["passed"] is False
    assert report["gate_policy"]["required_gates"][
        "holdout_metadata_v2_mean"
    ]["passed"] is True
    assert report["decision"]["eligible_for_separate_production_integration_decision"] is False
    assert report["decision"]["production_integration_performed"] is False


def test_failed_holdout_gate_forbids_production_eligibility(tmp_path):
    paths = synthetic_inputs(tmp_path, replay_v2=4, holdout_v2=3)

    report = finalize(paths)

    assert report["status"] == "failed"
    assert report["gate_policy"]["required_gates"][
        "replay_candidate_metadata_v2_mean"
    ]["passed"] is True
    assert report["gate_policy"]["required_gates"][
        "holdout_metadata_v2_mean"
    ]["passed"] is False
    assert report["decision"][
        "eligible_for_separate_production_integration_decision"
    ] is False


def test_invalid_completed_review_is_rejected_before_private_mapping_is_read(
    tmp_path,
    monkeypatch,
):
    paths = synthetic_inputs(tmp_path)
    completed = json.loads(paths["completed"].read_text(encoding="utf-8"))
    completed["evaluator"]["identifier"] = ""
    write_json(paths["completed"], completed)
    original_read_bytes = Path.read_bytes
    mapping_path = paths["mapping"].resolve()

    def guarded_read_bytes(self):
        if self.resolve() == mapping_path:
            raise AssertionError("private mapping was read before public validation")
        return original_read_bytes(self)

    monkeypatch.setattr(Path, "read_bytes", guarded_read_bytes)
    with pytest.raises(MetadataReviewValidationError, match="evaluator.identifier"):
        finalize(paths)
    assert not paths["output_json"].exists()
    assert not paths["output_md"].exists()


def test_input_change_during_finalize_is_detected_without_reports(
    tmp_path,
    monkeypatch,
):
    paths = synthetic_inputs(tmp_path)
    original_read_bytes = Path.read_bytes
    completed_path = paths["completed"].resolve()
    changed_payload = paths["completed"].read_bytes().replace(
        b"synthetic-independent-reviewer",
        b"changed-independent-reviewer",
    )
    reads = 0

    def unstable_read_bytes(self):
        nonlocal reads
        if self.resolve() == completed_path:
            reads += 1
            if reads >= 3:
                return changed_payload
        return original_read_bytes(self)

    monkeypatch.setattr(Path, "read_bytes", unstable_read_bytes)
    with pytest.raises(MetadataReviewInputChangedError, match="changed"):
        finalize(paths)
    assert not paths["output_json"].exists()
    assert not paths["output_md"].exists()


def test_completed_review_with_nan_is_rejected_before_unblinding(tmp_path):
    paths = synthetic_inputs(tmp_path)
    text = paths["completed"].read_text(encoding="utf-8")
    paths["completed"].write_text(
        text.replace('"metadata_fit_scores": [\n        3,', '"metadata_fit_scores": [\n        NaN,', 1),
        encoding="utf-8",
    )

    with pytest.raises(MetadataReviewValidationError, match="forbidden JSON constant"):
        finalize(paths)
    assert not paths["output_json"].exists()
