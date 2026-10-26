from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.harness import AgentHarness
from app.agents.llm_client import get_llm_client
from app.agents.matching_agent import MatchingAgent
from app.agents.question_bank_agent import QuestionBankAgent
from app.agents.source_quality import source_record, source_record_from_run
from app.core.config import get_settings
from app.core.errors import AppError, ErrorCode
from app.db.models.agent_run import AgentRun
from app.db.models.interview_experience import ExperienceProfile, InterviewExperience
from app.db.models.job_description import JDProfile, JobDescription
from app.db.models.prep_package import (
    InterviewPrepPackage,
    MatchReport,
    PrepPackageExperience,
)
from app.db.models.question import InterviewQuestion, RecommendedQuestion
from app.db.models.resume import Resume, ResumeProfile
from app.schemas.prep_package import MatchReport as MatchReportSchema
from app.schemas.question import QuestionBank


class PrepPackageService:
    async def create_prep_package(
        self,
        db: Session,
        *,
        user_id: UUID,
        resume_id: UUID,
        job_description_id: UUID,
        interview_experience_ids: list[UUID] | None = None,
        preparation_goal: str,
        title: str | None = None,
        originating_workflow_job_id: UUID | None = None,
    ) -> tuple[InterviewPrepPackage, UUID]:
        if originating_workflow_job_id is not None:
            existing = db.scalar(
                select(InterviewPrepPackage).where(
                    InterviewPrepPackage.originating_workflow_job_id
                    == originating_workflow_job_id
                )
            )
            if existing is not None and existing.status == "ready" and existing.agent_run_id:
                return existing, existing.agent_run_id
        interview_experience_ids = interview_experience_ids or []
        resume = db.get(Resume, resume_id)
        job = db.get(JobDescription, job_description_id)
        if resume is None:
            raise AppError(ErrorCode.NOT_FOUND, "Resume not found", status_code=404)
        if job is None:
            raise AppError(ErrorCode.NOT_FOUND, "Job description not found", status_code=404)

        resume_profile = self._latest_resume_profile(db, resume_id)
        jd_profile = self._latest_jd_profile(db, job_description_id)
        if resume_profile is None:
            raise AppError(ErrorCode.NOT_FOUND, "Resume profile not found", status_code=404)
        if jd_profile is None:
            raise AppError(ErrorCode.NOT_FOUND, "JD profile not found", status_code=404)

        experience_links: list[tuple[InterviewExperience, ExperienceProfile | None]] = []
        for experience_id in interview_experience_ids:
            experience = db.get(InterviewExperience, experience_id)
            if experience is None:
                raise AppError(
                    ErrorCode.NOT_FOUND,
                    "Interview experience not found",
                    status_code=404,
                )
            experience_links.append(
                (experience, self._latest_experience_profile(db, experience.id))
            )

        package = InterviewPrepPackage(
            originating_workflow_job_id=originating_workflow_job_id,
            user_id=user_id,
            resume_id=resume.id,
            resume_profile_id=resume_profile.id,
            job_description_id=job.id,
            jd_profile_id=jd_profile.id,
            title=title or f"{job.title} 面试备战包",
            status="generating",
            package_version="v0.1",
            overview_json={
                "preparation_goal": preparation_goal,
                "resume_title": resume.title,
                "job_title": job.title,
                "interview_experience_ids": [
                    str(experience.id) for experience, _ in experience_links
                ],
            },
            priority_plan_json={},
            action_items_json=[],
        )
        db.add(package)
        db.commit()
        db.refresh(package)

        for experience, experience_profile in experience_links:
            db.add(
                PrepPackageExperience(
                    prep_package_id=package.id,
                    interview_experience_id=experience.id,
                    experience_profile_id=(
                        experience_profile.id if experience_profile is not None else None
                    ),
                )
            )
        if experience_links:
            db.commit()

        experience_profile_ids = [
            str(experience_profile.id)
            for _, experience_profile in experience_links
            if experience_profile is not None
        ]
        experience_profiles = [
            experience_profile.profile_json
            for _, experience_profile in experience_links
            if experience_profile is not None
        ]
        profile_source_context = {
            "resume_profile": source_record_from_run(
                db.get(AgentRun, resume_profile.agent_run_id)
                if resume_profile.agent_run_id is not None
                else None
            ),
            "jd_profile": source_record_from_run(
                db.get(AgentRun, jd_profile.agent_run_id)
                if jd_profile.agent_run_id is not None
                else None
            ),
        }
        for index, (_, experience_profile) in enumerate(experience_links, start=1):
            if experience_profile is None:
                continue
            profile_source_context[f"experience_profile_{index}"] = source_record_from_run(
                db.get(AgentRun, experience_profile.agent_run_id)
                if experience_profile.agent_run_id is not None
                else None
            )
        matching_result = await AgentHarness().run_agent(
            db=db,
            user_id=user_id,
            run_type="matching",
            agent=MatchingAgent(llm_client=get_llm_client()),
            input_data={
                "resume_profile_id": str(resume_profile.id),
                "jd_profile_id": str(jd_profile.id),
                "resume_profile": resume_profile.profile_json,
                "jd_profile": jd_profile.profile_json,
                "preparation_goal": preparation_goal,
                "interview_experience_ids": [
                    str(experience.id) for experience, _ in experience_links
                ],
                "experience_profile_ids": experience_profile_ids,
                "experience_profiles": experience_profiles,
                "source_context": profile_source_context,
            },
            output_schema=MatchReportSchema,
        )
        match_output = matching_result.output
        match_report = MatchReport(
            prep_package_id=package.id,
            agent_run_id=matching_result.agent_run_id,
            overall_score=match_output.overall_score,
            strengths_json=match_output.matched_strengths,
            gaps_json=match_output.missing_capabilities,
            expression_issues_json=match_output.expression_issues,
            risk_points_json=match_output.risk_points,
            resume_suggestions_json=[
                item.model_dump(mode="json") for item in match_output.resume_suggestions
            ],
            evidence_refs_json=[
                item.model_dump(mode="json") for item in match_output.evidence_refs
            ],
            report_json=match_output.model_dump(mode="json"),
        )
        db.add(match_report)
        db.commit()

        question_source_context = {
            **profile_source_context,
            "matching": source_record(
                matching_result.metadata.execution_mode,
                agent_run_id=matching_result.agent_run_id,
            ),
        }

        question_result = await AgentHarness().run_agent(
            db=db,
            user_id=user_id,
            run_type="question_bank",
            agent=QuestionBankAgent(llm_client=get_llm_client()),
            input_data={
                "prep_package_id": str(package.id),
                "match_report_id": str(match_report.id),
                "match_report": match_output.model_dump(mode="json"),
                "resume_profile": resume_profile.profile_json,
                "jd_profile": jd_profile.profile_json,
                "preparation_goal": preparation_goal,
                "interview_experience_ids": [
                    str(experience.id) for experience, _ in experience_links
                ],
                "experience_profile_ids": experience_profile_ids,
                "experience_profiles": experience_profiles,
                "source_context": question_source_context,
            },
            output_schema=QuestionBank,
        )
        question_bank = question_result.output
        questions = [
            *question_bank.self_intro_questions,
            *question_bank.professional_questions,
            *question_bank.behavior_project_questions,
        ]
        db_questions: list[InterviewQuestion] = []
        for question in questions:
            db_question = InterviewQuestion(
                prep_package_id=package.id,
                question_id=question.question_id,
                module=question.module,
                question_text=question.question_text,
                purpose=question.purpose,
                difficulty=question.difficulty,
                source_type=question.source_type,
                source_refs_json=[
                    item.model_dump(mode="json") for item in question.source_refs
                ],
                jd_keywords_json=question.jd_keywords,
                answer_framework=question.answer_framework,
                star_template=question.star_template,
                scoring_anchors_json=[
                    item.model_dump(mode="json") for item in question.scoring_anchors
                ],
                follow_up_questions_json=question.follow_up_questions,
                preparation_advice=question.preparation_advice,
                sort_order=question.sort_order,
            )
            db.add(db_question)
            db_questions.append(db_question)
        db.flush()

        for rank, question in enumerate(db_questions[:3], start=1):
            db.add(
                RecommendedQuestion(
                    prep_package_id=package.id,
                    question_db_id=question.id,
                    rank=rank,
                    reason="优先覆盖当前准备目标和岗位核心能力",
                    related_weaknesses_json=["项目深度", "技术取舍"],
                )
            )

        package.agent_run_id = question_result.agent_run_id
        package.status = "ready"
        package.priority_plan_json = {
            "priorities": match_output.preparation_priorities,
        }
        package.action_items_json = [
            {
                "title": "准备项目深挖案例",
                "priority": "high",
                "description": "围绕一个后端项目补齐背景、取舍、结果和指标",
            }
        ]
        db.commit()
        db.refresh(package)
        return package, question_result.agent_run_id

    def _latest_resume_profile(self, db: Session, resume_id: UUID) -> ResumeProfile | None:
        return db.scalars(
            select(ResumeProfile)
            .where(ResumeProfile.resume_id == resume_id)
            .order_by(ResumeProfile.created_at.desc())
        ).first()

    def _latest_jd_profile(self, db: Session, job_description_id: UUID) -> JDProfile | None:
        return db.scalars(
            select(JDProfile)
            .where(JDProfile.job_description_id == job_description_id)
            .order_by(JDProfile.created_at.desc())
        ).first()

    def _latest_experience_profile(
        self, db: Session, interview_experience_id: UUID
    ) -> ExperienceProfile | None:
        return db.scalars(
            select(ExperienceProfile)
            .where(ExperienceProfile.interview_experience_id == interview_experience_id)
            .order_by(ExperienceProfile.created_at.desc())
        ).first()
