from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.agents.answer_evaluator import AnswerEvaluatorAgent
from app.agents.harness import AgentHarness
from app.agents.llm_client import get_llm_client
from app.core.config import get_settings
from app.core.errors import AppError, ErrorCode
from app.db.models.evaluation import AnswerEvaluation
from app.db.models.question import InterviewQuestion
from app.schemas.evaluation import AnswerEvaluation as AnswerEvaluationSchema
from app.services.memory_service import MemoryService


class EvaluationService:
    async def create_evaluation(
        self,
        db: Session,
        *,
        user_id: UUID,
        user_answer: str,
        question_db_id: UUID | None = None,
        custom_question_text: str | None = None,
    ) -> tuple[AnswerEvaluation, UUID]:
        question: InterviewQuestion | None = None
        prep_package_id: UUID | None = None
        if question_db_id is not None:
            question = db.get(InterviewQuestion, question_db_id)
            if question is None:
                raise AppError(ErrorCode.NOT_FOUND, "Question not found", status_code=404)
            question_text = question.question_text
            prep_package_id = question.prep_package_id
            question_id = question.question_id
        elif custom_question_text:
            question_text = custom_question_text
            question_id = None
        else:
            raise AppError(
                ErrorCode.VALIDATION_ERROR,
                "question_db_id or custom_question_text is required",
                status_code=422,
            )

        result = await AgentHarness().run_agent(
            db=db,
            user_id=user_id,
            run_type="answer_evaluation",
            agent=AnswerEvaluatorAgent(llm_client=get_llm_client()),
            input_data={
                "question_id": question_id,
                "question_text": question_text,
                "user_answer": user_answer,
            },
            output_schema=AnswerEvaluationSchema,
        )
        output = result.output
        dimension_scores = {item.name: item.score for item in output.dimension_scores}
        evaluation = AnswerEvaluation(
            user_id=user_id,
            prep_package_id=prep_package_id,
            question_db_id=question_db_id,
            custom_question_text=custom_question_text,
            user_answer=user_answer,
            agent_run_id=result.agent_run_id,
            total_score=output.total_score,
            relevance_score=dimension_scores.get("relevance", 0),
            technical_accuracy_score=dimension_scores.get("technical_accuracy", 0),
            project_specificity_score=dimension_scores.get("project_specificity", 0),
            structure_score=dimension_scores.get("structure", 0),
            communication_score=dimension_scores.get("communication", 0),
            risk_control_score=dimension_scores.get("risk_control", 0),
            strengths_json=output.strengths,
            improvement_points_json=output.improvement_points,
            risks_json=output.risks,
            improved_answer=output.improved_answer,
            follow_up_questions_json=output.follow_up_questions,
            next_practice_suggestion=output.next_practice_suggestion,
            memory_update_json=output.memory_update,
            evaluation_json=output.model_dump(mode="json"),
        )
        db.add(evaluation)
        db.commit()
        db.refresh(evaluation)
        MemoryService().apply_memory_update(db, evaluation)
        return evaluation, result.agent_run_id

    def get_evaluation(self, db: Session, answer_evaluation_id: UUID) -> AnswerEvaluation:
        evaluation = db.get(AnswerEvaluation, answer_evaluation_id)
        if evaluation is None:
            raise AppError(ErrorCode.NOT_FOUND, "Answer evaluation not found", status_code=404)
        return evaluation

    def list_evaluations(self, db: Session, *, limit: int, offset: int) -> dict:
        total = db.scalar(select(func.count(AnswerEvaluation.id))) or 0
        items = db.scalars(
            select(AnswerEvaluation)
            .order_by(AnswerEvaluation.created_at.desc())
            .limit(limit)
            .offset(offset)
        ).all()
        return {
            "total": total,
            "items": [self.serialize_summary(item) for item in items],
        }

    def serialize_detail(self, evaluation: AnswerEvaluation) -> dict:
        return {
            **self.serialize_summary(evaluation),
            "question_db_id": evaluation.question_db_id,
            "custom_question_text": evaluation.custom_question_text,
            "user_answer": evaluation.user_answer,
            "strengths": evaluation.strengths_json,
            "improvement_points": evaluation.improvement_points_json,
            "risks": evaluation.risks_json,
            "improved_answer": evaluation.improved_answer,
            "follow_up_questions": evaluation.follow_up_questions_json,
            "next_practice_suggestion": evaluation.next_practice_suggestion,
            "memory_update": evaluation.memory_update_json,
            "evaluation": evaluation.evaluation_json,
        }

    def serialize_summary(self, evaluation: AnswerEvaluation) -> dict:
        return {
            "answer_evaluation_id": evaluation.id,
            "prep_package_id": evaluation.prep_package_id,
            "agent_run_id": evaluation.agent_run_id,
            "total_score": float(evaluation.total_score),
            "created_at": evaluation.created_at,
        }
