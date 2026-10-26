from collections import Counter
import hashlib
import json
from pathlib import Path

import pytest

from app.agents.question_bank_agent import QuestionBankAgent
from app.agents.question_bank_assembler import QuestionBankAssembler
from app.agents.question_bank_metadata_v2 import QuestionBankMetadataAssemblerV2
from app.schemas.question import QuestionBank
from app.schemas.question_draft import QuestionDraftBank
from app.services.question_bank_metadata_replay import _NoProvider, validate_evidence_quotes


CORPUS = Path("tests/fixtures/question_bank_metadata_replay_corpus_v1.json")
INPUT = Path("tests/fixtures/question_bank_ab_inputs_v1.json")


def flat(bank):
    return [q for key in ("self_intro_questions", "professional_questions", "behavior_project_questions") for q in bank[key]]


def test_frozen_replay_has_exactly_fifteen_banks_and_no_historical_grades():
    raw = CORPUS.read_text(encoding="utf-8")
    corpus = json.loads(raw)
    assert len(corpus["records"]) == 15
    assert Counter(record["case_id"] for record in corpus["records"]) == {"backend_go_case": 5, "backend_java_case": 5, "backend_python_case": 5}
    assert sum(sum(len(g) for g in record["draft"].values()) for record in corpus["records"]) == 375
    assert corpus["source_input_sha256"] == hashlib.sha256(INPUT.read_bytes()).hexdigest()
    assert "metadata_fit_scores" not in raw
    assert "text_scores" not in raw
    assert "answer_framework" not in raw


@pytest.mark.parametrize("case_id", ["backend_go_case", "backend_java_case", "backend_python_case"])
def test_all_frozen_candidate_text_replays_preserve_contract_and_determinism(case_id):
    corpus = json.loads(CORPUS.read_text(encoding="utf-8"))
    inputs = {case["case_id"]: case["input"] for case in json.loads(INPUT.read_text(encoding="utf-8"))["cases"]}
    provider = _NoProvider()
    assemblers = (QuestionBankAssembler(QuestionBankAgent(provider)), QuestionBankMetadataAssemblerV2())
    records = [record for record in corpus["records"] if record["case_id"] == case_id]
    for record in records:
        draft = QuestionDraftBank.model_validate(record["draft"])
        original = [q["question_text"] for group in record["draft"].values() for q in group]
        outputs = []
        for assembler in assemblers:
            bank = assembler.assemble(draft, inputs[case_id])
            assert bank == assembler.assemble(draft, inputs[case_id])
            assert QuestionBank.model_validate(bank).total_count == 25
            assert [q["question_text"] for q in flat(bank)] == original
            QuestionBankAssembler._validate_final_bank(QuestionBank.model_validate(bank))
            outputs.append(bank)
        validate_evidence_quotes(outputs[1], inputs[case_id])
        assert [q["question_id"] for q in flat(outputs[0])] == [q["question_id"] for q in flat(outputs[1])]
        assert outputs[0] != outputs[1]
    assert provider.calls == 0
