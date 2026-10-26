from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.experience_analyzer import ExperienceAnalyzerAgent
from app.agents.harness import AgentHarness
from app.agents.llm_client import get_llm_client
from app.core.config import get_settings
from app.core.errors import AppError, ErrorCode
from app.db.models.interview_experience import ExperienceProfile, InterviewExperience
from app.db.models.source_document import SourceDocument
from app.schemas.experience import ExperienceProfile as ExperienceProfileSchema


class ExperienceService:
    def create_experience(
        self,
        db: Session,
        *,
        user_id: UUID,
        source_document_id: UUID,
        title: str,
        experience_type: str,
        company_name: str | None = None,
        role_name: str | None = None,
    ) -> InterviewExperience:
        source_document = db.get(SourceDocument, source_document_id)
        if source_document is None:
            raise AppError(ErrorCode.NOT_FOUND, "Source document not found", status_code=404)
        if source_document.document_type != "interview_experience":
            raise AppError(
                ErrorCode.VALIDATION_ERROR,
                "Source document must be an interview_experience",
                status_code=422,
            )

        experience = InterviewExperience(
            user_id=user_id,
            source_document_id=source_document_id,
            title=title,
            experience_type=experience_type,
            company_name=company_name,
            role_name=role_name,
            raw_text=source_document.raw_text,
        )
        db.add(experience)
        db.commit()
        db.refresh(experience)
        return experience

    async def parse_experience(
        self,
        db: Session,
        *,
        interview_experience_id: UUID,
        originating_workflow_job_id: UUID | None = None,
    ) -> tuple[ExperienceProfile, UUID]:
        if originating_workflow_job_id is not None:
            existing = db.scalar(
                select(ExperienceProfile).where(
                    ExperienceProfile.originating_workflow_job_id
                    == originating_workflow_job_id,
                    ExperienceProfile.interview_experience_id == interview_experience_id,
                )
            )
            if existing is not None and existing.agent_run_id is not None:
                return existing, existing.agent_run_id
        experience = db.get(InterviewExperience, interview_experience_id)
        if experience is None:
            raise AppError(ErrorCode.NOT_FOUND, "Interview experience not found", status_code=404)

        agent = ExperienceAnalyzerAgent(llm_client=get_llm_client())
        result = await AgentHarness().run_agent(
            db=db,
            user_id=get_settings().default_user_id,
            run_type="experience_parse",
            agent=agent,
            input_data={
                "interview_experience_id": str(experience.id),
                "title": experience.title,
                "raw_text": experience.raw_text,
            },
            output_schema=ExperienceProfileSchema,
        )
        output = result.output
        profile = ExperienceProfile(
            originating_workflow_job_id=originating_workflow_job_id,
            interview_experience_id=experience.id,
            agent_run_id=result.agent_run_id,
            schema_version=output.schema_version,
            profile_json=output.model_dump(mode="json"),
            frequent_questions=output.frequent_questions,
            frequent_topics=output.frequent_topics,
            follow_up_patterns=output.follow_up_patterns,
        )
        db.add(profile)
        db.commit()
        db.refresh(profile)
        return profile, result.agent_run_id
