import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas.evaluation import AnswerEvaluation
from app.schemas.question import QuestionBank
from tests.unit.test_evaluation_schemas import valid_evaluation_payload
from tests.unit.test_question_bank_schemas import make_question_bank


def test_sample_cases_are_loadable() -> None:
    fixture_dir = Path("tests/fixtures/sample_cases")
    cases = sorted(fixture_dir.glob("backend_*_case.json"))

    assert len(cases) == 3
    for case_path in cases:
        data = json.loads(case_path.read_text(encoding="utf-8"))
        assert data["resume_text"]
        assert data["jd_text"]
        assert data["preparation_goal"]
        assert data["user_answer"]


def test_question_bank_constraints_reject_too_few_questions() -> None:
    with pytest.raises(ValidationError):
        make_question_bank(total_count=24)


def test_evaluation_constraints_reject_dimension_over_max_score() -> None:
    payload = valid_evaluation_payload()
    payload["dimension_scores"][0]["score"] = 30
    payload["dimension_scores"][0]["max_score"] = 20

    with pytest.raises(ValidationError):
        AnswerEvaluation(**payload)


def test_question_bank_constraints_accept_valid_bank() -> None:
    bank = QuestionBank.model_validate(make_question_bank().model_dump())

    assert bank.total_count == 25
