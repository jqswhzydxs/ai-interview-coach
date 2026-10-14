from typing import Literal

from pydantic import Field, model_validator

from app.schemas.common import EvidenceRef, ScoreItem, StrictBaseModel


QuestionModule = Literal["self_intro", "professional", "behavior_project"]
QuestionDifficulty = Literal["basic", "medium", "hard"]
QuestionSourceType = Literal["resume", "jd", "experience", "inferred", "mixed"]


class InterviewQuestion(StrictBaseModel):
    question_id: str
    module: QuestionModule
    question_text: str
    purpose: str
    difficulty: QuestionDifficulty
    source_type: QuestionSourceType
    source_refs: list[EvidenceRef] = Field(min_length=1)
    jd_keywords: list[str]
    answer_framework: str
    star_template: str
    scoring_anchors: list[ScoreItem] = Field(min_length=1)
    follow_up_questions: list[str]
    preparation_advice: str
    sort_order: int = Field(ge=1)


class QuestionBank(StrictBaseModel):
    self_intro_questions: list[InterviewQuestion] = Field(min_length=8)
    professional_questions: list[InterviewQuestion] = Field(min_length=8)
    behavior_project_questions: list[InterviewQuestion] = Field(min_length=8)
    total_count: int = Field(ge=25)

    @model_validator(mode="after")
    def validate_question_bank(self) -> "QuestionBank":
        all_questions = [
            *self.self_intro_questions,
            *self.professional_questions,
            *self.behavior_project_questions,
        ]
        if self.total_count != len(all_questions):
            raise ValueError("total_count must equal the number of questions")

        question_ids = [question.question_id for question in all_questions]
        if len(question_ids) != len(set(question_ids)):
            raise ValueError("question_id must be unique within a question bank")

        module_groups = {
            "self_intro": self.self_intro_questions,
            "professional": self.professional_questions,
            "behavior_project": self.behavior_project_questions,
        }
        for expected_module, questions in module_groups.items():
            if any(question.module != expected_module for question in questions):
                raise ValueError(f"{expected_module} list contains another module")

        return self
