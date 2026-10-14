from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError, ErrorCode
from app.db.models.prep_package import InterviewPrepPackage
from app.db.models.question import InterviewQuestion, RecommendedQuestion


class QuestionService:
    def get_prep_package_detail(self, db: Session, prep_package_id: UUID) -> dict:
        package = db.get(InterviewPrepPackage, prep_package_id)
        if package is None:
            raise AppError(ErrorCode.NOT_FOUND, "Prep package not found", status_code=404)

        question_count = db.scalar(
            select(func.count(InterviewQuestion.id)).where(
                InterviewQuestion.prep_package_id == prep_package_id
            )
        )
        recommended_count = db.scalar(
            select(func.count(RecommendedQuestion.id)).where(
                RecommendedQuestion.prep_package_id == prep_package_id
            )
        )
        return {
            "prep_package_id": package.id,
            "title": package.title,
            "status": package.status,
            "overview": package.overview_json,
            "question_count": question_count or 0,
            "recommended_count": recommended_count or 0,
            "created_at": package.created_at,
        }

    def list_questions(
        self,
        db: Session,
        *,
        prep_package_id: UUID,
        module: str | None = None,
        difficulty: str | None = None,
    ) -> dict:
        package = db.get(InterviewPrepPackage, prep_package_id)
        if package is None:
            raise AppError(ErrorCode.NOT_FOUND, "Prep package not found", status_code=404)

        query = select(InterviewQuestion).where(
            InterviewQuestion.prep_package_id == prep_package_id
        )
        if module is not None:
            query = query.where(InterviewQuestion.module == module)
        if difficulty is not None:
            query = query.where(InterviewQuestion.difficulty == difficulty)

        questions = db.scalars(
            query.order_by(InterviewQuestion.sort_order, InterviewQuestion.question_id)
        ).all()
        return {
            "total": len(questions),
            "items": [self._serialize_question(question) for question in questions],
        }

    def _serialize_question(self, question: InterviewQuestion) -> dict:
        return {
            "question_db_id": question.id,
            "question_id": question.question_id,
            "module": question.module,
            "question_text": question.question_text,
            "purpose": question.purpose,
            "difficulty": question.difficulty,
            "source_type": question.source_type,
            "source_refs": question.source_refs_json,
            "jd_keywords": question.jd_keywords_json,
            "answer_framework": question.answer_framework,
            "star_template": question.star_template,
            "scoring_anchors": question.scoring_anchors_json,
            "follow_up_questions": question.follow_up_questions_json,
            "preparation_advice": question.preparation_advice,
            "sort_order": question.sort_order,
        }
