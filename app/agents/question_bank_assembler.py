from difflib import SequenceMatcher
import re
import unicodedata

from app.agents.base import AgentOutputValidationError
from app.agents.question_bank_agent import QuestionBankAgent
from app.schemas.question import QuestionBank
from app.schemas.question_draft import QuestionDraftBank


class QuestionBankAssembler:
    def __init__(self, metadata_agent: QuestionBankAgent) -> None:
        self.metadata_agent = metadata_agent

    def assemble(self, draft: QuestionDraftBank, input_data: dict) -> dict:
        context = self.metadata_agent._context(input_data)
        groups = (
            ("self_intro", draft.self_intro_questions, 8),
            ("professional", draft.professional_questions, 8),
            ("behavior_project", draft.behavior_project_questions, 9),
        )
        texts = [item.question_text for _, questions, _ in groups for item in questions]

        self._validate_counts(groups, len(texts))
        self._validate_text_uniqueness(texts)
        self._validate_evidence(context["source_refs"])
        self._validate_technology_boundary(texts, context["technologies"])

        assembled: dict[str, list[dict]] = {
            "self_intro_questions": [],
            "professional_questions": [],
            "behavior_project_questions": [],
        }
        output_keys = {
            "self_intro": "self_intro_questions",
            "professional": "professional_questions",
            "behavior_project": "behavior_project_questions",
        }
        for module, questions, _ in groups:
            for index, draft_question in enumerate(questions):
                question = self.metadata_agent._question(index, module, context)
                question["question_text"] = draft_question.question_text
                assembled[output_keys[module]].append(question)

        payload = {**assembled, "total_count": 25}
        bank = QuestionBank.model_validate(payload)
        self._validate_final_bank(bank)
        return bank.model_dump(mode="json")

    @staticmethod
    def _validate_counts(groups, total: int) -> None:
        for module, questions, expected in groups:
            if len(questions) != expected:
                raise AgentOutputValidationError(
                    f"{module} must contain exactly {expected} questions"
                )
        if total != 25:
            raise AgentOutputValidationError("draft must contain exactly 25 questions")

    @staticmethod
    def _validate_text_uniqueness(texts: list[str]) -> None:
        normalized = [normalize_question_text(text) for text in texts]
        if any(not text for text in normalized):
            raise AgentOutputValidationError("question text is empty after normalization")
        if len(normalized) != len(set(normalized)):
            raise AgentOutputValidationError("question texts must be normalized-unique")
        for left_index, left in enumerate(normalized):
            for right in normalized[left_index + 1 :]:
                if SequenceMatcher(None, left, right).ratio() >= 0.94:
                    raise AgentOutputValidationError(
                        "question texts must be substantively different"
                    )

    @staticmethod
    def _validate_technology_boundary(texts: list[str], allowed_terms: list[str]) -> None:
        allowed = _mentioned_technologies(" ".join(allowed_terms))
        mentioned = _mentioned_technologies(" ".join(texts))
        forbidden = sorted(mentioned - allowed)
        if forbidden:
            raise AgentOutputValidationError(
                f"question draft contains out-of-context technologies: {', '.join(forbidden)}"
            )

    @staticmethod
    def _validate_evidence(source_refs: list[dict]) -> None:
        supported = [
            item
            for item in source_refs
            if isinstance(item, dict)
            and item.get("source_type") in {"resume", "jd", "experience"}
            and str(item.get("summary") or "").strip()
        ]
        if not supported:
            raise AgentOutputValidationError(
                "candidate assembly requires resume, jd, or experience evidence"
            )

    @staticmethod
    def _validate_final_bank(bank: QuestionBank) -> None:
        groups = {
            "self_intro": bank.self_intro_questions,
            "professional": bank.professional_questions,
            "behavior_project": bank.behavior_project_questions,
        }
        if [len(items) for items in groups.values()] != [8, 8, 9]:
            raise AgentOutputValidationError("assembled bank must be exactly 8/8/9")
        for module, questions in groups.items():
            expected_prefix = {
                "self_intro": "self",
                "professional": "pro",
                "behavior_project": "beh",
            }[module]
            for index, question in enumerate(questions, start=1):
                if question.module != module:
                    raise AgentOutputValidationError("assembled module mismatch")
                if question.question_id != f"{expected_prefix}-{index:02d}":
                    raise AgentOutputValidationError("assembled question_id mismatch")
                if question.sort_order != index:
                    raise AgentOutputValidationError("assembled sort_order mismatch")
                if not question.source_refs:
                    raise AgentOutputValidationError("assembled source_refs cannot be empty")
        QuestionBankAssembler._validate_text_uniqueness(
            [
                question.question_text
                for questions in groups.values()
                for question in questions
            ]
        )


def normalize_question_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold().strip()
    normalized = re.sub(r"^[\s\W_]*\d+[\s\W_]+", "", normalized)
    normalized = re.sub(r"[（(\[]\s*\d+\s*[）)\]]\s*$", "", normalized)
    normalized = re.sub(r"\d+\s*$", "", normalized)
    return "".join(character for character in normalized if character.isalnum())


_TECHNOLOGY_PATTERNS = {
    "python": r"(?<![\w])python(?![\w])",
    "fastapi": r"(?<![\w])fastapi(?![\w])",
    "django": r"(?<![\w])django(?![\w])",
    "flask": r"(?<![\w])flask(?![\w])",
    "sqlalchemy": r"(?<![\w])sqlalchemy(?![\w])",
    "go": r"(?<![\w])go(?![\w])",
    "gin": r"(?<![\w])gin(?![\w])",
    "grpc": r"(?<![\w])grpc(?![\w])",
    "java": r"(?<![\w])java(?![\w])",
    "spring": r"(?<![\w])spring(?:\s+boot)?(?![\w])",
    "postgresql": r"(?<![\w])(?:postgresql|postgres)(?![\w])",
    "mysql": r"(?<![\w])mysql(?![\w])",
    "redis": r"(?<![\w])redis(?![\w])",
    "mongodb": r"(?<![\w])mongodb(?![\w])",
    "kafka": r"(?<![\w])kafka(?![\w])",
    "rabbitmq": r"(?<![\w])rabbitmq(?![\w])",
    "docker": r"(?<![\w])docker(?![\w])",
    "kubernetes": r"(?<![\w])kubernetes(?![\w])",
}


def _mentioned_technologies(value: str) -> set[str]:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return {
        canonical
        for canonical, pattern in _TECHNOLOGY_PATTERNS.items()
        if re.search(pattern, normalized, flags=re.IGNORECASE)
    }
