from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.harness import AgentHarness
from app.agents.jd_analyzer import JDAnalyzerAgent
from app.agents.llm_client import get_llm_client
from app.core.config import get_settings
from app.core.errors import AppError, ErrorCode
from app.db.models.job_description import JDProfile, JobDescription
from app.db.models.source_document import SourceDocument
from app.schemas.job_description import JDProfile as JDProfileSchema


class JobService:
    def create_job_description(
        self,
        db: Session,
        *,
        user_id: UUID,
        source_document_id: UUID,
        title: str,
        company_name: str | None = None,
        job_url: str | None = None,
        target_direction: str = "backend",
    ) -> JobDescription:
        source_document = db.get(SourceDocument, source_document_id)
        if source_document is None:
            raise AppError(ErrorCode.NOT_FOUND, "Source document not found", status_code=404)
        if source_document.document_type != "jd":
            raise AppError(
                ErrorCode.VALIDATION_ERROR,
                "Source document must be a jd",
                status_code=422,
            )

        job = JobDescription(
            user_id=user_id,
            source_document_id=source_document_id,
            title=title,
            company_name=company_name,
            job_url=job_url,
            raw_text=source_document.raw_text,
            target_direction=target_direction,
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        return job

    async def parse_job_description(
        self,
        db: Session,
        *,
        job_description_id: UUID,
        originating_workflow_job_id: UUID | None = None,
    ) -> tuple[JDProfile, UUID]:
        if originating_workflow_job_id is not None:
            existing = db.scalar(
                select(JDProfile).where(
                    JDProfile.originating_workflow_job_id == originating_workflow_job_id
                )
            )
            if existing is not None and existing.agent_run_id is not None:
                return existing, existing.agent_run_id
        job = db.get(JobDescription, job_description_id)
        if job is None:
            raise AppError(ErrorCode.NOT_FOUND, "Job description not found", status_code=404)

        agent = JDAnalyzerAgent(llm_client=get_llm_client())
        result = await AgentHarness().run_agent(
            db=db,
            user_id=get_settings().default_user_id,
            run_type="jd_parse",
            agent=agent,
            input_data={
                "job_description_id": str(job.id),
                "title": job.title,
                "company_name": job.company_name,
                "raw_text": job.raw_text,
            },
            output_schema=JDProfileSchema,
        )
        output = result.output
        profile = JDProfile(
            originating_workflow_job_id=originating_workflow_job_id,
            job_description_id=job.id,
            agent_run_id=result.agent_run_id,
            schema_version=output.schema_version,
            profile_json=output.model_dump(mode="json"),
            core_responsibilities=output.core_responsibilities,
            hard_requirements=output.hard_requirements,
            bonus_points=output.bonus_points,
            tech_keywords=output.tech_keywords,
            backend_dimensions=output.backend_dimensions,
        )
        db.add(profile)
        db.commit()
        db.refresh(profile)
        return profile, result.agent_run_id
