from pydantic import Field, field_validator, model_validator

from app.schemas.common import StrictBaseModel


class QuestionDraft(StrictBaseModel):
    question_text: str = Field(min_length=4, max_length=500)

    @field_validator("question_text")
    @classmethod
    def strip_question_text(cls, value: str) -> str:
        stripped = value.strip()
        if len(stripped) < 4:
            raise ValueError("question_text must contain meaningful content")
        return stripped


class QuestionDraftBank(StrictBaseModel):
    self_intro_questions: list[QuestionDraft] = Field(min_length=8, max_length=8)
    professional_questions: list[QuestionDraft] = Field(min_length=8, max_length=8)
    behavior_project_questions: list[QuestionDraft] = Field(min_length=9, max_length=9)

    @model_validator(mode="after")
    def validate_total_count(self) -> "QuestionDraftBank":
        total = (
            len(self.self_intro_questions)
            + len(self.professional_questions)
            + len(self.behavior_project_questions)
        )
        if total != 25:
            raise ValueError("QuestionDraftBank must contain exactly 25 questions")
        return self
