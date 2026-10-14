import pytest
from pydantic import ValidationError

from app.schemas.question import InterviewQuestion, QuestionBank


def make_question(question_id: str, module: str) -> InterviewQuestion:
    return InterviewQuestion(
        question_id=question_id,
        module=module,
        question_text=f"Question {question_id}?",
        purpose="Assess job fit",
        difficulty="medium",
        source_type="mixed",
        source_refs=[{"source_type": "resume", "summary": "Resume evidence"}],
        jd_keywords=["api"],
        answer_framework="Use STAR",
        star_template="Situation, Task, Action, Result",
        scoring_anchors=[{"name": "relevance", "score": 8, "max_score": 10, "reason": "clear"}],
        follow_up_questions=["Can you expand on tradeoffs?"],
        preparation_advice="Prepare concrete metrics",
        sort_order=1,
    )


def make_question_bank(total_count: int = 25) -> QuestionBank:
    self_intro = [make_question(f"self-{index}", "self_intro") for index in range(8)]
    professional = [make_question(f"pro-{index}", "professional") for index in range(8)]
    behavior = [
        make_question(f"beh-{index}", "behavior_project")
        for index in range(total_count - len(self_intro) - len(professional))
    ]
    return QuestionBank(
        self_intro_questions=self_intro,
        professional_questions=professional,
        behavior_project_questions=behavior,
        total_count=total_count,
    )


def test_question_bank_accepts_at_least_25_questions() -> None:
    bank = make_question_bank()

    assert bank.total_count == 25
    assert len(bank.behavior_project_questions) == 9


def test_question_bank_rejects_24_questions() -> None:
    with pytest.raises(ValidationError):
        make_question_bank(total_count=24)


def test_question_bank_rejects_duplicate_question_id() -> None:
    bank_payload = make_question_bank().model_dump()
    bank_payload["behavior_project_questions"][0]["question_id"] = "self-0"

    with pytest.raises(ValidationError):
        QuestionBank(**bank_payload)


def test_interview_question_requires_source_refs_and_scoring_anchors() -> None:
    payload = make_question("q-empty", "professional").model_dump()
    payload["source_refs"] = []
    payload["scoring_anchors"] = []

    with pytest.raises(ValidationError):
        InterviewQuestion(**payload)
