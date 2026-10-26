"""Frozen, offline-only integration validation. Does not generate review assets."""

from contextlib import ExitStack
import json
from pathlib import Path

from app.agents.question_bank_candidate_agent import (
    PROJECT_ROOT, QuestionBankCandidateAgent, candidate_asset_hashes, payload_sha256,
)
from app.agents.question_bank_assembler import QuestionBankAssembler
from app.agents.question_bank_metadata_v2 import QuestionBankMetadataAssemblerV2
from app.schemas.question import QuestionBank
from app.schemas.question_draft import QuestionDraftBank
from app.services.question_bank_metadata_replay import (
    ReplaySafetyError, _NoProvider, _draft, _flat, file_sha256,
    offline_readonly_guard, tree_hashes, validate_evidence_quotes,
)


RUN2 = PROJECT_ROOT / "storage/reports/question-bank-ab-phase-2-4b-v2-20261019-run2"
REVIEW = PROJECT_ROOT / "storage/reports/question-bank-metadata-phase-2-4c-offline-20261020"
REPLAY = PROJECT_ROOT / "tests/fixtures/question_bank_metadata_replay_corpus_v1.json"
HOLDOUT = PROJECT_ROOT / "tests/fixtures/question_bank_metadata_holdout_v1.json"
INPUTS = PROJECT_ROOT / "tests/fixtures/question_bank_ab_inputs_v1.json"
PROTECTED = (RUN2, REVIEW, PROJECT_ROOT / "app", PROJECT_ROOT / "tests/fixtures", PROJECT_ROOT / "docs")


def _read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ReplaySafetyError(message)


def _identity(bank: dict) -> list[dict]:
    return [{key: q[key] for key in ("question_text", "question_id", "module", "sort_order")} for q in _flat(bank)]


def validate_candidate_integration(*, output_dir: Path) -> dict:
    output_dir = output_dir.resolve()
    _require(not any(output_dir.is_relative_to(p) or p.is_relative_to(output_dir) for p in PROTECTED), "Output must be separate from protected inputs")
    # No existing experiment directory may be reused as the destination.
    old_report_dirs = [p for p in (PROJECT_ROOT / "storage/reports").iterdir() if p.is_dir() and p.resolve() != output_dir]
    _require(not any(output_dir.is_relative_to(p.resolve()) for p in old_report_dirs), "Output cannot reuse an existing experiment")
    names = ("integration-validation.json", "candidate-run-records.json")
    _require(not any((output_dir / name).exists() for name in names), "Integration outputs already exist")
    before = {str(p.relative_to(PROJECT_ROOT)): tree_hashes(p) for p in PROTECTED}
    with ExitStack() as stack:
        guards = [stack.enter_context(offline_readonly_guard(p)) for p in PROTECTED]
        inputs = _read(INPUTS)
        replay = _read(REPLAY)
        frozen_replay = _read(REVIEW / "offline-replay-report.json")
        _require(file_sha256(INPUTS) == replay["source_input_sha256"] == frozen_replay["input_sha256"], "Frozen input hash mismatch")
        _require(file_sha256(HOLDOUT) == frozen_replay["holdout_sha256"], "Frozen holdout hash mismatch")
        packet_path = RUN2 / "blind-question-review-packet.json"
        _require(file_sha256(packet_path) == replay["source_question_packet_sha256"], "Frozen question packet hash mismatch")
        for path in ("app/agents/question_bank_assembler.py", "app/agents/question_bank_metadata_v2.py", "app/agents/question_metadata_rules.py"):
            _require(file_sha256(PROJECT_ROOT / path) == frozen_replay["implementation_hashes"][path], "Reviewed assembler assets changed")
        input_map = {c["case_id"]: c["input"] for c in inputs["cases"]}
        packet = {s["submission_id"]: s for s in _read(packet_path)["submissions"]}
        records = [{**r, "partition": "replay", "input": input_map[r["case_id"]]} for r in replay["records"]]
        for r in records:
            _require(_draft(packet[r["source_submission_id"]]).model_dump(mode="json") == r["draft"], "Replay fixture differs from run2")
        records += [{**r, "corpus_id": r["case_id"], "partition": "holdout"} for r in _read(HOLDOUT)["cases"]]
        _require(len(records) == 19 and len(replay["records"]) == 15, "Expected 15 replay and 4 holdout banks")
        frozen = {(r["corpus_id"], r["version"]): r["bank"] for r in _read(REVIEW / "audit/replayed-question-banks.json")["banks"]}
        client = _NoProvider()
        agents = {version: QuestionBankCandidateAgent(client, metadata_version=version) for version in ("v1", "v2")}
        results, run_records = [], []
        for r in records:
            draft = QuestionDraftBank.model_validate(r["draft"])
            original_texts = [q["question_text"] for key in ("self_intro_questions", "professional_questions", "behavior_project_questions") for q in r["draft"][key]]
            for version, agent in agents.items():
                bank = agent.replay_draft(draft, r["input"])
                run_record = agent.last_candidate_record
                repeated = agent.replay_draft(draft, r["input"])
                _require(bank == repeated and run_record == agent.last_candidate_record, "Candidate replay is not deterministic")
                _require(bank == frozen[(r["corpus_id"], version)], "Integrated bank differs from reviewed frozen bank")
                _require(_identity(bank) == _identity(frozen[(r["corpus_id"], "v1")]), "Question identity or order changed")
                _require([q["question_text"] for q in _flat(bank)] == original_texts, "Frozen question text changed")
                parsed = QuestionBank.model_validate(bank)
                QuestionBankAssembler._validate_final_bank(parsed)
                QuestionBankAssembler._validate_text_uniqueness(original_texts)
                if version == "v2":
                    validate_evidence_quotes(bank, r["input"])
                    # The assembler itself enforces technology and evidence safety.
                    _require(type(agent.assembler) is QuestionBankMetadataAssemblerV2, "Version selection drift")
                results.append({"corpus_id": r["corpus_id"], "partition": r["partition"], "version": version, "question_count": 25, "deterministic": True, "frozen_bank_equal": True, "identity_equal": True, "api_contract": "passed", "bank_sha256": payload_sha256(bank)})
                run_records.append({"corpus_id": r["corpus_id"], "partition": r["partition"], **run_record})
        _require(client.calls == 0, "Offline integration requested a Provider")
        after = {str(p.relative_to(PROJECT_ROOT)): tree_hashes(p) for p in PROTECTED}
        _require(before == after, "Protected inputs changed")
        report = {
            "phase": "2.4C Candidate Integration", "status": "passed",
            "replay_banks": 15, "holdout_banks": 4, "questions_per_version": 475,
            "versions": ["v1", "v2"], "comparisons": results,
            "assembly_executions": 76, "provider_calls": client.calls,
            "network_attempts": sum(g["network_attempts"] for g in guards),
            "protected_write_attempts": sum(g["source_write_attempts"] for g in guards),
            "protected_inputs_unchanged": before == after,
            "production_default_changed": False, "token_experiment_started": False,
            "source_sha256": {p.relative_to(PROJECT_ROOT).as_posix(): file_sha256(p) for p in (REPLAY, HOLDOUT, INPUTS, packet_path, REVIEW / "audit/replayed-question-banks.json", REVIEW / "metadata-review-final-report.json")},
            "asset_sha256": candidate_asset_hashes(),
            "schema_sha256": {"QuestionDraftBank": payload_sha256(QuestionDraftBank.model_json_schema()), "QuestionBank": payload_sha256(QuestionBank.model_json_schema())},
        }
        output_dir.mkdir(parents=True, exist_ok=True)
        for name, value in zip(names, (report, {"runs": run_records})):
            with (output_dir / name).open("x", encoding="utf-8") as handle:
                handle.write(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
        _require(before == {str(p.relative_to(PROJECT_ROOT)): tree_hashes(p) for p in PROTECTED}, "Protected inputs changed during output")
    return report
