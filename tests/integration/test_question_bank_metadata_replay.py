import hashlib
import json
from pathlib import Path
import sys

import pytest

from app.agents.mock_client import MockLLMClient
from app.agents.question_bank_agent import QuestionBankAgent
from app.agents.question_bank_assembler import QuestionBankAssembler
from app.agents.question_bank_metadata_v2 import QuestionBankMetadataAssemblerV2
from app.schemas.question_draft import QuestionDraftBank
from app.services.question_bank_metadata_replay import (
    ReplaySafetyError, _curated_questions, _draft, offline_readonly_guard,
    run_metadata_replay, tree_hashes, validate_evidence_quotes,
)
from tests.unit.test_question_bank_draft_protocol import _valid_draft


INPUT = Path("tests/fixtures/question_bank_ab_inputs_v1.json")
HOLDOUT = Path("tests/fixtures/question_bank_metadata_holdout_v1.json")


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


@pytest.fixture
def synthetic_archive(tmp_path):
    source = tmp_path / "original-experiment"
    cases = json.loads(INPUT.read_text(encoding="utf-8"))["cases"]
    runs, text_subs, meta_subs = [], [], []
    assembler = QuestionBankAssembler(QuestionBankAgent(MockLLMClient()))
    for i in range(15):
        case = cases[i % 3]
        technology = {"backend_go_case": "Go", "backend_java_case": "Java", "backend_python_case": "Python"}[case["case_id"]]
        bank = assembler.assemble(QuestionDraftBank.model_validate(_valid_draft(technology)), case["input"])
        sid = f"synthetic-archive-{i:02d}"
        curated = _curated_questions(bank)
        runs.append({"variant": "candidate", "execution_mode": "real", "submission_id": sid, "case_id": case["case_id"]})
        text_subs.append({"submission_id": sid, "case_id": case["case_id"], "questions": [{key: q[key] for key in ("position", "module", "question_text")} for q in curated]})
        meta_subs.append({"submission_id": sid, "case_id": case["case_id"], "questions": curated})
    write_json(source / "question-bank-ab-report.json", {"runs": runs, "input_sha256": hashlib.sha256(INPUT.read_bytes()).hexdigest()})
    write_json(source / "blind-question-review-packet.json", {"submissions": text_subs})
    write_json(source / "blind-metadata-review-packet.json", {"submissions": meta_subs})
    return source


def test_offline_paired_replay_preserves_archive_and_outputs_fresh_blind_materials(synthetic_archive, tmp_path, monkeypatch):
    from app.agents.llm_client import get_llm_client
    from sqlalchemy.engine import Engine

    def forbidden(*args, **kwargs):
        raise AssertionError("offline metadata replay must not generate or connect to a database")

    monkeypatch.setattr(Engine, "connect", forbidden)
    monkeypatch.setattr(MockLLMClient, "generate_json", forbidden)
    before = tree_hashes(synthetic_archive)
    out = tmp_path / "calibration"
    report = run_metadata_replay(source_dir=synthetic_archive, output_dir=out, input_file=INPUT, holdout_file=HOLDOUT)
    assert tree_hashes(synthetic_archive) == before
    assert report["status"] == "awaiting_independent_metadata_review"
    assert report["frozen_candidate_questions"] == 375
    assert report["authored_holdout_questions"] == 100
    assert report["comparison_banks"] == report["blind_submission_count"] == 38
    assert report["provider_calls"] == report["network_attempts"] == report["source_write_attempts"] == 0
    assert report["new_metadata_fit"] is None
    assert report["historical_scores_used_for_new_acceptance"] is False
    assert all(c["deterministic"] and c["schema"] == c["strict_count"] == c["duplicate"] == c["stack_boundary"] == "passed" for c in report["comparisons"])
    packet = json.loads((out / "blind-review/metadata-review-packet.json").read_text(encoding="utf-8"))
    template = json.loads((out / "blind-review/metadata-review-template.json").read_text(encoding="utf-8"))
    mapping = json.loads((out / "audit/private-blinding-map.json").read_text(encoding="utf-8"))["mapping"]
    assert len({s["submission_id"] for s in packet["submissions"]}) == 38
    assert [s["submission_id"] for s in packet["submissions"]] == [s["submission_id"] for s in template["submissions"]]
    assert all(len(s["questions"]) == 25 and s["evidence_context"] for s in packet["submissions"])
    assert all(s["metadata_fit_scores"] == [None] * 25 for s in template["submissions"])
    assert template["evaluator"]["type"] is None
    assert {row["version"] for row in mapping} == {"v1", "v2"}
    assert len(list((out / "blind-review").glob("*.json"))) == 2
    banned = {"version", "variant", "case_id", "pair", "source_submission_id", "corpus_id", "partition", "bank_sha256"}

    def inspect(value):
        if isinstance(value, dict):
            assert not (set(value) & banned)
            for item in value.values():
                inspect(item)
        elif isinstance(value, list):
            for item in value:
                inspect(item)

    inspect(packet)
    assert "synthetic-archive-" not in json.dumps(packet)
    with pytest.raises(ReplaySafetyError, match="silently regenerated"):
        run_metadata_replay(source_dir=synthetic_archive, output_dir=out, input_file=INPUT, holdout_file=HOLDOUT)


def test_original_directory_write_and_mutation_are_blocked(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    path = source / "manifest.json"
    path.write_text("original", encoding="utf-8")
    with offline_readonly_guard(source) as state:
        assert path.read_text(encoding="utf-8") == "original"
        with pytest.raises(ReplaySafetyError, match="read-only"):
            path.write_text("changed", encoding="utf-8")
        with pytest.raises(ReplaySafetyError, match="read-only"):
            path.unlink()
        assert state["source_write_attempts"] == 2
    assert path.read_text(encoding="utf-8") == "original"


def test_network_guard_responds_to_a_synthetic_audit_event_without_opening_a_socket(tmp_path):
    with offline_readonly_guard(tmp_path / "source") as state:
        with pytest.raises(ReplaySafetyError, match="network"):
            sys.audit("socket.connect", None, ("offline.invalid", 443))
        assert state["network_attempts"] == 1


def test_output_under_original_experiment_is_rejected_before_any_io(tmp_path):
    with pytest.raises(ReplaySafetyError, match="separate"):
        run_metadata_replay(source_dir=tmp_path, output_dir=tmp_path / "forbidden", input_file=INPUT, holdout_file=HOLDOUT)


def test_evidence_validator_rejects_invented_project_quote():
    case = json.loads(HOLDOUT.read_text(encoding="utf-8"))["cases"][0]
    bank = QuestionBankMetadataAssemblerV2().assemble(QuestionDraftBank.model_validate(case["draft"]), case["input"])
    bank["self_intro_questions"][0]["source_refs"] = [{"source_type": "resume", "quote": "Invented billion-user project", "summary": "resume_profile.projects[0].name"}]
    with pytest.raises(ReplaySafetyError, match="traceable"):
        validate_evidence_quotes(bank, case["input"])


def test_frozen_text_whitespace_is_not_silently_normalized():
    payload = _valid_draft()
    questions = []
    for module in ("self_intro", "professional", "behavior_project"):
        for question in payload[f"{module}_questions"]:
            questions.append({"position": len(questions) + 1, "module": module, **question})
    questions[0]["question_text"] = "  " + questions[0]["question_text"]
    with pytest.raises(ReplaySafetyError, match="normalization"):
        _draft({"questions": questions})
