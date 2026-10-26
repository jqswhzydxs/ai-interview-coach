"""Strictly offline finalizer for the Phase 2.4C independent metadata review."""

from __future__ import annotations

from collections import Counter
from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from typing import Any, Iterable
from uuid import uuid4


REVIEW_VERSION = "phase-2.4c-independent-metadata-review-v1"
REPORT_VERSION = "phase-2.4c-metadata-review-final-report-v1"
GATE_POLICY_VERSION = "phase-2.4c-metadata-gates-v1"
REPLAY_V2_MIN_MEAN = 3.5
HOLDOUT_V2_MIN_MEAN = 3.5
EXPECTED_SUBMISSIONS = 38
EXPECTED_SCORES_PER_SUBMISSION = 25
EXPECTED_TOTAL_SCORES = 950
FIELD_NAMES = ("purpose", "source", "framework", "anchors", "follow_up", "advice")
PARTITION_NAMES = {
    "frozen_run2": "replay_candidate",
    "authored_holdout": "holdout",
}


class MetadataReviewFinalizerError(RuntimeError):
    """Base class for finalizer failures."""


class MetadataReviewValidationError(MetadataReviewFinalizerError):
    """The review or frozen replay inputs do not satisfy the contract."""


class MetadataReviewInputChangedError(MetadataReviewFinalizerError):
    """At least one input changed while finalization was in progress."""


@dataclass(frozen=True)
class InputSnapshot:
    path: Path
    payload: bytes
    sha256: str


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _snapshot(path: Path) -> InputSnapshot:
    resolved = path.resolve()
    payload = resolved.read_bytes()
    return InputSnapshot(path=resolved, payload=payload, sha256=_sha256(payload))


def _strict_json(snapshot: InputSnapshot) -> Any:
    def reject_constant(value: str) -> None:
        raise MetadataReviewValidationError(
            f"{snapshot.path.name} contains forbidden JSON constant {value}"
        )

    try:
        return json.loads(snapshot.payload.decode("utf-8"), parse_constant=reject_constant)
    except MetadataReviewValidationError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise MetadataReviewValidationError(
            f"{snapshot.path.name} is not valid UTF-8 JSON"
        ) from exc


def _assert_unchanged(snapshots: Iterable[InputSnapshot]) -> None:
    for snapshot in snapshots:
        try:
            current = snapshot.path.read_bytes()
        except OSError as exc:
            raise MetadataReviewInputChangedError(
                f"Input changed or disappeared during finalization: {snapshot.path.name}"
            ) from exc
        if _sha256(current) != snapshot.sha256:
            raise MetadataReviewInputChangedError(
                f"Input changed during finalization: {snapshot.path.name}"
            )


def _resolved_audit_path(value: Any) -> Path | None:
    if not isinstance(value, (str, bytes, os.PathLike)):
        return None
    try:
        return Path(value).resolve()
    except (OSError, TypeError, ValueError):
        return None


@contextmanager
def offline_finalizer_guard(protected_inputs: Iterable[Path]):
    """Block networking, subprocesses, and writes to the four finalizer inputs."""

    protected = {path.resolve() for path in protected_inputs}
    state = {
        "active": True,
        "network_attempts": 0,
        "subprocess_attempts": 0,
        "protected_input_write_attempts": 0,
    }

    def touches_protected(*values: Any) -> bool:
        return any(
            resolved in protected
            for resolved in (_resolved_audit_path(value) for value in values)
            if resolved is not None
        )

    def audit(event: str, args: tuple[Any, ...]) -> None:
        if not state["active"]:
            return
        if event.startswith("socket."):
            state["network_attempts"] += 1
            raise MetadataReviewFinalizerError(
                "Network access is forbidden during metadata review finalization"
            )
        if event in {"subprocess.Popen", "os.system", "os.posix_spawn", "os.spawn"}:
            state["subprocess_attempts"] += 1
            raise MetadataReviewFinalizerError(
                "Subprocesses are forbidden during metadata review finalization"
            )
        if event == "open" and args:
            mode = args[1] if len(args) > 1 else "r"
            writing = (
                isinstance(mode, str)
                and any(flag in mode for flag in ("w", "a", "x", "+"))
            ) or (
                isinstance(mode, int)
                and bool(
                    mode
                    & (
                        os.O_WRONLY
                        | os.O_RDWR
                        | os.O_APPEND
                        | os.O_CREAT
                        | os.O_TRUNC
                    )
                )
            )
            if writing and touches_protected(args[0]):
                state["protected_input_write_attempts"] += 1
                raise MetadataReviewFinalizerError(
                    "Finalizer inputs are read-only"
                )
        if event in {"os.remove", "os.unlink", "os.rmdir"} and args:
            if touches_protected(args[0]):
                state["protected_input_write_attempts"] += 1
                raise MetadataReviewFinalizerError(
                    "Finalizer inputs are read-only"
                )
        if event in {"os.rename", "os.replace"} and touches_protected(*args[:2]):
            state["protected_input_write_attempts"] += 1
            raise MetadataReviewFinalizerError(
                "Finalizer inputs are read-only"
            )

    sys.addaudithook(audit)
    try:
        yield state
    finally:
        state["active"] = False


def _require_dict(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise MetadataReviewValidationError(f"{label} must be an object")
    return value


def _require_nonempty_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise MetadataReviewValidationError(f"{label} must be a non-empty string")
    return value.strip()


def _validate_template(template: Any) -> tuple[list[str], dict[str, Any]]:
    root = _require_dict(template, "review template")
    if root.get("review_version") != REVIEW_VERSION:
        raise MetadataReviewValidationError("Template review_version is not supported")
    if root.get("scale") != "1-5":
        raise MetadataReviewValidationError("Template scale must be 1-5")
    submissions = root.get("submissions")
    if not isinstance(submissions, list) or len(submissions) != EXPECTED_SUBMISSIONS:
        raise MetadataReviewValidationError(
            f"Template must contain exactly {EXPECTED_SUBMISSIONS} submissions"
        )
    ids: list[str] = []
    for index, raw in enumerate(submissions):
        submission = _require_dict(raw, f"template submission {index + 1}")
        submission_id = _require_nonempty_string(
            submission.get("submission_id"),
            f"template submission {index + 1}.submission_id",
        )
        scores = submission.get("metadata_fit_scores")
        if (
            not isinstance(scores, list)
            or len(scores) != EXPECTED_SCORES_PER_SUBMISSION
            or any(score is not None for score in scores)
        ):
            raise MetadataReviewValidationError(
                "The frozen template must retain 25 null score slots per submission"
            )
        notes = _require_dict(
            submission.get("field_notes"),
            f"template submission {submission_id}.field_notes",
        )
        if set(notes) != set(FIELD_NAMES) or any(
            not isinstance(notes[field], str) for field in FIELD_NAMES
        ):
            raise MetadataReviewValidationError(
                "Template field_notes must contain exactly the six frozen fields"
            )
        ids.append(submission_id)
    if len(set(ids)) != EXPECTED_SUBMISSIONS:
        raise MetadataReviewValidationError("Template submission IDs must be unique")
    return ids, root


def validate_completed_review(
    template: Any,
    completed: Any,
) -> dict[str, Any]:
    """Validate every public review field before private mapping is read."""

    template_ids, _ = _validate_template(template)
    root = _require_dict(completed, "completed review")
    if root.get("review_version") != REVIEW_VERSION:
        raise MetadataReviewValidationError("Completed review_version is not supported")
    evaluator = _require_dict(root.get("evaluator"), "evaluator")
    evaluator_type = _require_nonempty_string(
        evaluator.get("type"), "evaluator.type"
    )
    identifier = _require_nonempty_string(
        evaluator.get("identifier"), "evaluator.identifier"
    )
    if evaluator.get("independence_confirmed") is not True:
        raise MetadataReviewValidationError(
            "evaluator.independence_confirmed must be true"
        )
    submissions = root.get("submissions")
    if not isinstance(submissions, list):
        raise MetadataReviewValidationError("Completed submissions must be a list")
    if len(submissions) != EXPECTED_SUBMISSIONS:
        raise MetadataReviewValidationError(
            f"Completed review must contain exactly {EXPECTED_SUBMISSIONS} submissions"
        )
    completed_ids: list[str] = []
    normalized: list[dict[str, Any]] = []
    score_count = 0
    for index, raw in enumerate(submissions):
        submission = _require_dict(raw, f"completed submission {index + 1}")
        submission_id = _require_nonempty_string(
            submission.get("submission_id"),
            f"completed submission {index + 1}.submission_id",
        )
        scores = submission.get("metadata_fit_scores")
        if not isinstance(scores, list) or len(scores) != EXPECTED_SCORES_PER_SUBMISSION:
            raise MetadataReviewValidationError(
                f"{submission_id} must contain exactly 25 metadata_fit_scores"
            )
        for position, score in enumerate(scores, 1):
            if type(score) is not int or not 1 <= score <= 5:
                raise MetadataReviewValidationError(
                    f"{submission_id} score {position} must be an integer from 1 to 5"
                )
        notes = _require_dict(
            submission.get("field_notes"),
            f"completed submission {submission_id}.field_notes",
        )
        if set(notes) != set(FIELD_NAMES):
            raise MetadataReviewValidationError(
                f"{submission_id}.field_notes must contain exactly the six fields"
            )
        normalized_notes: dict[str, str] = {}
        for field in FIELD_NAMES:
            if not isinstance(notes[field], str):
                raise MetadataReviewValidationError(
                    f"{submission_id}.field_notes.{field} must be a string"
                )
            normalized_notes[field] = notes[field].strip()
        completed_ids.append(submission_id)
        score_count += len(scores)
        normalized.append(
            {
                "submission_id": submission_id,
                "metadata_fit_scores": list(scores),
                "field_notes": normalized_notes,
            }
        )
    if completed_ids != template_ids:
        if set(completed_ids) != set(template_ids):
            raise MetadataReviewValidationError(
                "Completed submission IDs do not exactly match the template"
            )
        raise MetadataReviewValidationError(
            "Completed submission order differs from the template"
        )
    if len(set(completed_ids)) != EXPECTED_SUBMISSIONS:
        raise MetadataReviewValidationError(
            "Completed review contains duplicate or extra submission IDs"
        )
    if score_count != EXPECTED_TOTAL_SCORES:
        raise MetadataReviewValidationError(
            f"Completed review must contain exactly {EXPECTED_TOTAL_SCORES} scores"
        )
    return {
        "review_version": REVIEW_VERSION,
        "evaluator": {
            "type": evaluator_type,
            "identifier": identifier,
            "independence_confirmed": True,
        },
        "submissions": normalized,
        "submission_count": len(normalized),
        "score_count": score_count,
    }


def _flatten_questions(bank: dict[str, Any]) -> list[dict[str, Any]]:
    questions: list[dict[str, Any]] = []
    for key in (
        "self_intro_questions",
        "professional_questions",
        "behavior_project_questions",
    ):
        values = bank.get(key)
        if not isinstance(values, list):
            raise MetadataReviewValidationError(f"Replay bank is missing {key}")
        questions.extend(values)
    if len(questions) != EXPECTED_SCORES_PER_SUBMISSION:
        raise MetadataReviewValidationError(
            "Every replayed question bank must contain exactly 25 questions"
        )
    if any(
        not isinstance(question, dict)
        or not isinstance(question.get("question_text"), str)
        or not question["question_text"].strip()
        for question in questions
    ):
        raise MetadataReviewValidationError(
            "Every replayed question must contain non-empty question_text"
        )
    return questions


_STACK_RULES = (
    (
        "Rust/Axum",
        re.compile(r"\bRust\b|\bAxum\b|\bTokio\b"),
    ),
    (
        "TypeScript/Node.js",
        re.compile(r"\bTypeScript\b|\bNode(?:\.js)?\b|\bExpress\b|\bNestJS\b", re.I),
    ),
    (
        "Java/Spring",
        re.compile(r"\bJava\b|\bJVM\b|\bSpring(?:\s*Boot)?\b", re.I),
    ),
    (
        "Python/FastAPI",
        re.compile(r"\bPython\b|\bFastAPI\b|\bDjango\b|\bFlask\b", re.I),
    ),
    (
        "Go",
        re.compile(r"\bGo\b|\bGolang\b|\bgoroutine(?:s)?\b|\bGin\b|\bGORM\b"),
    ),
)


def infer_technology_stack(question_texts: Iterable[str]) -> str:
    """Infer only from paired frozen question text, never generated metadata."""

    text = "\n".join(question_texts)
    matches = [label for label, pattern in _STACK_RULES if pattern.search(text)]
    return " + ".join(matches) if matches else "Unclassified"


def _validate_private_inputs(
    mapping_payload: Any,
    banks_payload: Any,
    template_ids: list[str],
) -> tuple[dict[str, dict[str, Any]], dict[tuple[str, str], list[dict[str, Any]]]]:
    mapping_root = _require_dict(mapping_payload, "private mapping")
    mapping = mapping_root.get("mapping")
    if not isinstance(mapping, list) or len(mapping) != EXPECTED_SUBMISSIONS:
        raise MetadataReviewValidationError(
            "Private mapping must contain exactly 38 entries"
        )
    mapping_by_id: dict[str, dict[str, Any]] = {}
    pair_keys: set[tuple[str, str]] = set()
    for index, raw in enumerate(mapping):
        row = _require_dict(raw, f"private mapping row {index + 1}")
        submission_id = _require_nonempty_string(
            row.get("submission_id"), "private mapping submission_id"
        )
        version = row.get("version")
        partition = row.get("partition")
        corpus_id = _require_nonempty_string(
            row.get("corpus_id"), "private mapping corpus_id"
        )
        if version not in {"v1", "v2"}:
            raise MetadataReviewValidationError("Mapping version must be v1 or v2")
        if partition not in PARTITION_NAMES:
            raise MetadataReviewValidationError("Mapping partition is not supported")
        if submission_id in mapping_by_id:
            raise MetadataReviewValidationError("Private mapping IDs must be unique")
        pair_key = (corpus_id, version)
        if pair_key in pair_keys:
            raise MetadataReviewValidationError(
                "Private mapping contains a duplicate corpus/version pair"
            )
        mapping_by_id[submission_id] = {
            "submission_id": submission_id,
            "version": version,
            "partition": partition,
            "corpus_id": corpus_id,
        }
        pair_keys.add(pair_key)
    if set(mapping_by_id) != set(template_ids):
        raise MetadataReviewValidationError(
            "Private mapping IDs do not exactly match the review template"
        )

    corpus_versions: dict[str, set[str]] = {}
    corpus_partitions: dict[str, set[str]] = {}
    for row in mapping_by_id.values():
        corpus_versions.setdefault(row["corpus_id"], set()).add(row["version"])
        corpus_partitions.setdefault(row["corpus_id"], set()).add(row["partition"])
    if len(corpus_versions) != 19 or any(
        versions != {"v1", "v2"} for versions in corpus_versions.values()
    ):
        raise MetadataReviewValidationError(
            "Private mapping must describe 19 complete v1/v2 pairs"
        )
    if any(len(partitions) != 1 for partitions in corpus_partitions.values()):
        raise MetadataReviewValidationError(
            "A corpus pair cannot span multiple partitions"
        )
    partition_corpus_counts = Counter(
        next(iter(corpus_partitions[corpus_id])) for corpus_id in corpus_versions
    )
    if partition_corpus_counts != Counter(
        {"frozen_run2": 15, "authored_holdout": 4}
    ):
        raise MetadataReviewValidationError(
            "Expected 15 replay corpora and 4 holdout corpora"
        )

    banks_root = _require_dict(banks_payload, "replayed question banks")
    banks = banks_root.get("banks")
    if not isinstance(banks, list) or len(banks) != EXPECTED_SUBMISSIONS:
        raise MetadataReviewValidationError(
            "Replayed question banks must contain exactly 38 entries"
        )
    questions_by_pair: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for index, raw in enumerate(banks):
        row = _require_dict(raw, f"replayed bank row {index + 1}")
        corpus_id = _require_nonempty_string(
            row.get("corpus_id"), "replayed bank corpus_id"
        )
        version = row.get("version")
        if version not in {"v1", "v2"}:
            raise MetadataReviewValidationError(
                "Replayed bank version must be v1 or v2"
            )
        pair_key = (corpus_id, version)
        if pair_key in questions_by_pair:
            raise MetadataReviewValidationError(
                "Replayed banks contain a duplicate corpus/version pair"
            )
        bank = _require_dict(row.get("bank"), "replayed question bank")
        questions_by_pair[pair_key] = _flatten_questions(bank)
    if set(questions_by_pair) != pair_keys:
        raise MetadataReviewValidationError(
            "Replayed banks do not exactly match the private mapping"
        )
    for corpus_id in corpus_versions:
        v1_text = [
            question["question_text"]
            for question in questions_by_pair[(corpus_id, "v1")]
        ]
        v2_text = [
            question["question_text"]
            for question in questions_by_pair[(corpus_id, "v2")]
        ]
        if v1_text != v2_text:
            raise MetadataReviewValidationError(
                f"Paired question text differs for corpus {corpus_id}"
            )
    return mapping_by_id, questions_by_pair


def _score_stats(values: list[int], submission_count: int) -> dict[str, Any]:
    if not values:
        raise MetadataReviewValidationError("Cannot summarize an empty score group")
    return {
        "mean": round(sum(values) / len(values), 4),
        "score_count": len(values),
        "submission_count": submission_count,
        "distribution": {
            str(score): values.count(score) for score in range(1, 6)
        },
    }


def _paired_stats(
    corpus_ids: list[str],
    corpus_scores: dict[str, dict[str, list[int]]],
) -> dict[str, Any]:
    v1_values: list[int] = []
    v2_values: list[int] = []
    bank_wtl = Counter()
    question_wtl = Counter()
    for corpus_id in corpus_ids:
        v1 = corpus_scores[corpus_id]["v1"]
        v2 = corpus_scores[corpus_id]["v2"]
        v1_values.extend(v1)
        v2_values.extend(v2)
        v1_total, v2_total = sum(v1), sum(v2)
        bank_wtl["win" if v2_total > v1_total else "loss" if v2_total < v1_total else "tie"] += 1
        for old, new in zip(v1, v2):
            question_wtl["win" if new > old else "loss" if new < old else "tie"] += 1
    return {
        "v2_minus_v1_mean": round(
            sum(v2_values) / len(v2_values) - sum(v1_values) / len(v1_values),
            4,
        ),
        "bank_level_win_tie_loss": {
            "win": bank_wtl["win"],
            "tie": bank_wtl["tie"],
            "loss": bank_wtl["loss"],
        },
        "question_level_win_tie_loss": {
            "win": question_wtl["win"],
            "tie": question_wtl["tie"],
            "loss": question_wtl["loss"],
        },
    }


def _group_metrics(
    corpus_ids: list[str],
    corpus_scores: dict[str, dict[str, list[int]]],
) -> dict[str, Any]:
    versions: dict[str, Any] = {}
    for version in ("v1", "v2"):
        values = [
            score
            for corpus_id in corpus_ids
            for score in corpus_scores[corpus_id][version]
        ]
        versions[version] = _score_stats(values, len(corpus_ids))
    return {
        "corpus_count": len(corpus_ids),
        "versions": versions,
        "paired": _paired_stats(corpus_ids, corpus_scores),
    }


def _field_issues(
    reviewed: dict[str, dict[str, Any]],
    mapping_by_id: dict[str, dict[str, Any]],
    stacks: dict[str, str],
) -> dict[str, Any]:
    by_field: dict[str, Any] = {}
    for field in FIELD_NAMES:
        items = []
        counts_by_version = Counter()
        counts_by_partition = Counter()
        for submission_id, submission in reviewed.items():
            note = submission["field_notes"][field]
            if not note:
                continue
            mapping = mapping_by_id[submission_id]
            item = {
                "version": mapping["version"],
                "partition": PARTITION_NAMES[mapping["partition"]],
                "technology_stack": stacks[mapping["corpus_id"]],
                "corpus_id": mapping["corpus_id"],
                "note": note,
            }
            items.append(item)
            counts_by_version[mapping["version"]] += 1
            counts_by_partition[PARTITION_NAMES[mapping["partition"]]] += 1
        by_field[field] = {
            "note_count": len(items),
            "counts_by_version": {
                version: counts_by_version[version] for version in ("v1", "v2")
            },
            "counts_by_partition": {
                partition: counts_by_partition[partition]
                for partition in ("replay_candidate", "holdout")
            },
            "issues": items,
        }
    return {
        "numeric_scope": (
            "The review supplies one metadata_fit score per question, not one "
            "numeric score per metadata field. Field findings below are qualitative "
            "evaluator notes and are not converted into invented field scores."
        ),
        "by_field": by_field,
    }


def _build_report(
    validated_review: dict[str, Any],
    mapping_by_id: dict[str, dict[str, Any]],
    questions_by_pair: dict[tuple[str, str], list[dict[str, Any]]],
    snapshots: list[InputSnapshot],
    guard: dict[str, Any],
) -> dict[str, Any]:
    reviewed = {
        submission["submission_id"]: submission
        for submission in validated_review["submissions"]
    }
    corpus_scores: dict[str, dict[str, list[int]]] = {}
    corpus_partition: dict[str, str] = {}
    for submission_id, mapping in mapping_by_id.items():
        corpus_scores.setdefault(mapping["corpus_id"], {})[mapping["version"]] = (
            reviewed[submission_id]["metadata_fit_scores"]
        )
        corpus_partition[mapping["corpus_id"]] = mapping["partition"]
    stacks = {
        corpus_id: infer_technology_stack(
            question["question_text"]
            for question in questions_by_pair[(corpus_id, "v1")]
        )
        for corpus_id in corpus_scores
    }
    all_corpora = sorted(corpus_scores)
    replay_corpora = [
        corpus_id
        for corpus_id in all_corpora
        if corpus_partition[corpus_id] == "frozen_run2"
    ]
    holdout_corpora = [
        corpus_id
        for corpus_id in all_corpora
        if corpus_partition[corpus_id] == "authored_holdout"
    ]
    corpora_by_stack: dict[str, list[str]] = {}
    for corpus_id in all_corpora:
        corpora_by_stack.setdefault(stacks[corpus_id], []).append(corpus_id)

    overall = _group_metrics(all_corpora, corpus_scores)
    replay = _group_metrics(replay_corpora, corpus_scores)
    holdout = _group_metrics(holdout_corpora, corpus_scores)
    by_stack = {
        stack: _group_metrics(corpus_ids, corpus_scores)
        for stack, corpus_ids in sorted(corpora_by_stack.items())
    }
    replay_actual = replay["versions"]["v2"]["mean"]
    holdout_actual = holdout["versions"]["v2"]["mean"]
    replay_passed = replay_actual >= REPLAY_V2_MIN_MEAN
    holdout_passed = holdout_actual >= HOLDOUT_V2_MIN_MEAN
    gates_passed = replay_passed and holdout_passed

    report = {
        "report_version": REPORT_VERSION,
        "review_version": REVIEW_VERSION,
        "phase": "2.4C",
        "status": "passed" if gates_passed else "failed",
        "evaluator": validated_review["evaluator"],
        "validation": {
            "passed": True,
            "submission_count": validated_review["submission_count"],
            "scores_per_submission": EXPECTED_SCORES_PER_SUBMISSION,
            "total_score_count": validated_review["score_count"],
            "score_range": [1, 5],
            "submission_ids_and_order_match_template": True,
            "private_mapping_read_after_completed_validation": True,
        },
        "gate_policy": {
            "version": GATE_POLICY_VERSION,
            "required_gates": {
                "replay_candidate_metadata_v2_mean": {
                    "operator": ">=",
                    "threshold": REPLAY_V2_MIN_MEAN,
                    "actual": replay_actual,
                    "passed": replay_passed,
                },
                "holdout_metadata_v2_mean": {
                    "operator": ">=",
                    "threshold": HOLDOUT_V2_MIN_MEAN,
                    "actual": holdout_actual,
                    "passed": holdout_passed,
                },
            },
            "all_required_gates_passed": gates_passed,
        },
        "decision": {
            "metadata_v2_quality_gate": "passed" if gates_passed else "failed",
            "eligible_for_separate_production_integration_decision": gates_passed,
            "production_integration_performed": False,
            "production_default_agent_changed": False,
            "rule": (
                "A failed required gate forbids metadata v2 production integration. "
                "A pass does not perform or authorize an automatic production switch."
            ),
        },
        "score_summary": {
            "overall": overall,
            "partitions": {
                "replay_candidate": replay,
                "holdout": holdout,
            },
            "technology_stacks": by_stack,
        },
        "paired_improvement": {
            "overall": overall["paired"],
            "partitions": {
                "replay_candidate": replay["paired"],
                "holdout": holdout["paired"],
            },
            "technology_stacks": {
                stack: metrics["paired"] for stack, metrics in by_stack.items()
            },
        },
        "field_issues": _field_issues(reviewed, mapping_by_id, stacks),
        "corpus_classification": {
            "method": (
                "Deterministic matching against paired frozen question_text only; "
                "generated metadata is excluded to prevent v1/v2 classification drift."
            ),
            "technology_stack_by_corpus": {
                corpus_id: stacks[corpus_id] for corpus_id in all_corpora
            },
        },
        "input_integrity": {
            "unchanged_during_finalize": True,
            "sha256": {
                snapshot.path.name: snapshot.sha256 for snapshot in snapshots
            },
        },
        "safety": {
            "provider_calls": 0,
            "network_attempts": guard["network_attempts"],
            "subprocess_attempts": guard["subprocess_attempts"],
            "protected_input_write_attempts": guard[
                "protected_input_write_attempts"
            ],
            "production_files_modified": False,
            "automatic_production_switch": False,
        },
    }
    return report


def _md_cell(value: Any) -> str:
    return str(value).replace("\r", " ").replace("\n", " ").replace("|", "\\|")


def render_markdown(report: dict[str, Any]) -> str:
    evaluator = report["evaluator"]
    gates = report["gate_policy"]["required_gates"]
    lines = [
        "# Phase 2.4C metadata review final report",
        "",
        f"- Report status: `{report['status']}`",
        f"- Evaluator type (exact): `{_md_cell(evaluator['type'])}`",
        f"- Evaluator identifier: `{_md_cell(evaluator['identifier'])}`",
        f"- Independence confirmed: `{str(evaluator['independence_confirmed']).lower()}`",
        "- Production integration performed: `false`",
        "- Production default Agent changed: `false`",
        "",
        "## Frozen gates",
        "",
        "| Gate | Threshold | Actual | Result |",
        "| --- | ---: | ---: | --- |",
    ]
    for name, gate in gates.items():
        lines.append(
            f"| {_md_cell(name)} | {gate['operator']} {gate['threshold']:.4f} "
            f"| {gate['actual']:.4f} | {'passed' if gate['passed'] else 'failed'} |"
        )
    lines.extend(
        [
            "",
            report["decision"]["rule"],
            "",
            "## Score summary",
            "",
            "| Scope | v1 mean | v2 mean | Delta | Bank W/T/L | Question W/T/L |",
            "| --- | ---: | ---: | ---: | --- | --- |",
        ]
    )

    def add_metric_row(label: str, metrics: dict[str, Any]) -> None:
        paired = metrics["paired"]
        bank = paired["bank_level_win_tie_loss"]
        question = paired["question_level_win_tie_loss"]
        lines.append(
            f"| {_md_cell(label)} | {metrics['versions']['v1']['mean']:.4f} "
            f"| {metrics['versions']['v2']['mean']:.4f} "
            f"| {paired['v2_minus_v1_mean']:.4f} "
            f"| {bank['win']}/{bank['tie']}/{bank['loss']} "
            f"| {question['win']}/{question['tie']}/{question['loss']} |"
        )

    add_metric_row("overall", report["score_summary"]["overall"])
    for name, metrics in report["score_summary"]["partitions"].items():
        add_metric_row(name, metrics)
    for name, metrics in report["score_summary"]["technology_stacks"].items():
        add_metric_row(f"stack: {name}", metrics)

    lines.extend(
        [
            "",
            "## Field issues",
            "",
            report["field_issues"]["numeric_scope"],
            "",
        ]
    )
    for field, summary in report["field_issues"]["by_field"].items():
        lines.append(f"### {field}")
        lines.append("")
        lines.append(
            f"Recorded notes: {summary['note_count']} "
            f"(v1={summary['counts_by_version']['v1']}, "
            f"v2={summary['counts_by_version']['v2']})."
        )
        if not summary["issues"]:
            lines.append("")
            lines.append("No qualitative issue note was recorded.")
        else:
            for issue in summary["issues"]:
                note = _md_cell(issue["note"]).replace("`", "'")
                lines.append(
                    f"- {issue['version']} / {issue['partition']} / "
                    f"{_md_cell(issue['technology_stack'])} / "
                    f"{_md_cell(issue['corpus_id'])}: {note}"
                )
        lines.append("")
    lines.extend(
        [
            "## Safety",
            "",
            "- Provider calls: 0",
            f"- Network attempts: {report['safety']['network_attempts']}",
            f"- Subprocess attempts: {report['safety']['subprocess_attempts']}",
            "- Input assets remained unchanged.",
            "- This finalizer does not perform a production switch.",
            "",
        ]
    )
    return "\n".join(lines)


def _write_reports_atomically(
    json_path: Path,
    markdown_path: Path,
    report: dict[str, Any],
) -> None:
    json_path = json_path.resolve()
    markdown_path = markdown_path.resolve()
    if json_path == markdown_path:
        raise MetadataReviewFinalizerError("JSON and Markdown outputs must differ")
    if json_path.exists() or markdown_path.exists():
        raise MetadataReviewFinalizerError(
            "Final reports already exist; refusing to overwrite them"
        )
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_tmp = json_path.with_name(f".{json_path.name}.{uuid4().hex}.tmp")
    md_tmp = markdown_path.with_name(f".{markdown_path.name}.{uuid4().hex}.tmp")
    committed: list[Path] = []
    try:
        json_tmp.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        md_tmp.write_text(render_markdown(report), encoding="utf-8")
        os.replace(json_tmp, json_path)
        committed.append(json_path)
        os.replace(md_tmp, markdown_path)
        committed.append(markdown_path)
    except Exception:
        for path in (json_tmp, md_tmp, *committed):
            path.unlink(missing_ok=True)
        raise


def finalize_metadata_review(
    *,
    template_path: Path,
    mapping_path: Path,
    replayed_banks_path: Path,
    completed_review_path: Path,
    output_json_path: Path,
    output_markdown_path: Path,
) -> dict[str, Any]:
    """Validate, unblind, calculate gates, and emit two offline-only reports."""

    input_paths = [
        template_path,
        mapping_path,
        replayed_banks_path,
        completed_review_path,
    ]
    resolved_inputs = {path.resolve() for path in input_paths}
    if (
        output_json_path.resolve() in resolved_inputs
        or output_markdown_path.resolve() in resolved_inputs
    ):
        raise MetadataReviewFinalizerError("An output path cannot replace an input")

    with offline_finalizer_guard(input_paths) as guard:
        # Public artifacts are read and fully validated before the private map is touched.
        template_snapshot = _snapshot(template_path)
        completed_snapshot = _snapshot(completed_review_path)
        template = _strict_json(template_snapshot)
        completed = _strict_json(completed_snapshot)
        validated_review = validate_completed_review(template, completed)
        template_ids, _ = _validate_template(template)
        _assert_unchanged([template_snapshot, completed_snapshot])

        mapping_snapshot = _snapshot(mapping_path)
        banks_snapshot = _snapshot(replayed_banks_path)
        mapping_payload = _strict_json(mapping_snapshot)
        banks_payload = _strict_json(banks_snapshot)
        mapping_by_id, questions_by_pair = _validate_private_inputs(
            mapping_payload, banks_payload, template_ids
        )
        snapshots = [
            template_snapshot,
            completed_snapshot,
            mapping_snapshot,
            banks_snapshot,
        ]
        report = _build_report(
            validated_review,
            mapping_by_id,
            questions_by_pair,
            snapshots,
            guard,
        )
        _assert_unchanged(snapshots)
        _write_reports_atomically(output_json_path, output_markdown_path, report)
        try:
            _assert_unchanged(snapshots)
        except MetadataReviewInputChangedError:
            output_json_path.resolve().unlink(missing_ok=True)
            output_markdown_path.resolve().unlink(missing_ok=True)
            raise
        return report
