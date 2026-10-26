from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.agents.answer_evaluator import AnswerEvaluatorAgent
from app.agents.harness import AgentHarness
from app.agents.llm_client import get_llm_client
from app.agents.source_quality import source_record, source_record_from_run
from app.core.config import get_settings
from app.core.errors import AppError, ErrorCode
from app.db.models.agent_run import AgentRun
from app.db.models.evaluation import AnswerEvaluation
from app.db.models.interview_experience import ExperienceProfile
from app.db.models.job_description import JDProfile
from app.db.models.prep_package import (
    InterviewPrepPackage,
    MatchReport,
    PrepPackageExperience,
)
from app.db.models.question import InterviewQuestion
from app.db.models.resume import ResumeProfile
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
        originating_workflow_job_id: UUID | None = None,
    ) -> tuple[AnswerEvaluation, UUID]:
        if originating_workflow_job_id is not None:
            existing = db.scalar(
                select(AnswerEvaluation).where(
                    AnswerEvaluation.originating_workflow_job_id
                    == originating_workflow_job_id
                )
            )
            if existing is not None and existing.agent_run_id is not None:
                return existing, existing.agent_run_id
        question: InterviewQuestion | None = None
        prep_package_id: UUID | None = None
        resume_profile_json: dict | None = None
        jd_profile_json: dict | None = None
        scoring_anchors: list[dict] = []
        source_context: dict[str, dict] = {}
        if question_db_id is not None:
            question = db.get(InterviewQuestion, question_db_id)
            if question is None:
                raise AppError(ErrorCode.NOT_FOUND, "Question not found", status_code=404)
            question_text = question.question_text
            prep_package_id = question.prep_package_id
            question_id = question.question_id
            scoring_anchors = question.scoring_anchors_json
            prep_package = db.get(InterviewPrepPackage, prep_package_id)
            if prep_package is not None:
                resume_profile = db.get(ResumeProfile, prep_package.resume_profile_id)
                jd_profile = db.get(JDProfile, prep_package.jd_profile_id)
                resume_profile_json = (
                    resume_profile.profile_json if resume_profile is not None else None
                )
                jd_profile_json = jd_profile.profile_json if jd_profile is not None else None
                source_context = {
                    "question": source_record_from_run(
                        db.get(AgentRun, prep_package.agent_run_id)
                        if prep_package.agent_run_id is not None
                        else None
                    ),
                    "resume_profile": source_record_from_run(
                        db.get(AgentRun, resume_profile.agent_run_id)
                        if resume_profile is not None
                        and resume_profile.agent_run_id is not None
                        else None
                    ),
                    "jd_profile": source_record_from_run(
                        db.get(AgentRun, jd_profile.agent_run_id)
                        if jd_profile is not None and jd_profile.agent_run_id is not None
                        else None
                    ),
                }
                match_report = db.scalars(
                    select(MatchReport)
                    .where(MatchReport.prep_package_id == prep_package.id)
                    .order_by(MatchReport.created_at.desc())
                ).first()
                source_context["matching"] = source_record_from_run(
                    db.get(AgentRun, match_report.agent_run_id)
                    if match_report is not None and match_report.agent_run_id is not None
                    else None
                )
                experience_links = db.scalars(
                    select(PrepPackageExperience).where(
                        PrepPackageExperience.prep_package_id == prep_package.id
                    )
                ).all()
                for index, link in enumerate(experience_links, start=1):
                    experience_profile = (
                        db.get(ExperienceProfile, link.experience_profile_id)
                        if link.experience_profile_id is not None
                        else None
                    )
                    source_context[f"experience_profile_{index}"] = (
                        source_record_from_run(
                            db.get(AgentRun, experience_profile.agent_run_id)
                            if experience_profile is not None
                            and experience_profile.agent_run_id is not None
                            else None
                        )
                    )
        elif custom_question_text:
            question_text = custom_question_text
            question_id = None
            source_context = {"question": source_record("user")}
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
                "scoring_anchors": scoring_anchors,
                "resume_profile": resume_profile_json,
                "jd_profile": jd_profile_json,
                "source_context": source_context,
            },
            output_schema=AnswerEvaluationSchema,
        )
        output = result.output
        dimension_scores = {item.name: item.score for item in output.dimension_scores}
        persisted_source_context = {
            **source_context,
            "answer_evaluation": source_record(
                result.metadata.execution_mode,
                agent_run_id=result.agent_run_id,
            ),
        }
        evaluation = AnswerEvaluation(
            originating_workflow_job_id=originating_workflow_job_id,
            user_id=user_id,
            prep_package_id=prep_package_id,
            question_db_id=question_db_id,
            custom_question_text=custom_question_text,
            user_answer=user_answer,
            agent_run_id=result.agent_run_id,
            evaluation_mode=output.evaluation_mode,
            score_available=output.score_available,
            source_quality=output.source_quality,
            source_context_json=persisted_source_context,
            degradation_reasons_json=output.degradation_reasons,
            total_score=output.total_score,
            relevance_score=dimension_scores.get("relevance"),
            technical_accuracy_score=dimension_scores.get("technical_accuracy"),
            project_specificity_score=dimension_scores.get("project_specificity"),
            structure_score=dimension_scores.get("structure"),
            communication_score=dimension_scores.get("communication"),
            risk_control_score=dimension_scores.get("risk_control"),
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
            "evaluation_mode": evaluation.evaluation_mode,
            "score_available": evaluation.score_available,
            "source_quality": evaluation.source_quality,
            "degradation_reasons": evaluation.degradation_reasons_json,
            "total_score": (
                float(evaluation.total_score)
                if evaluation.total_score is not None
                else None
            ),
            "created_at": evaluation.created_at,
        }
