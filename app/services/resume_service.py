from uuid import UUID

from sqlalchemy.orm import Session

from app.agents.harness import AgentHarness
from app.agents.llm_client import get_llm_client
from app.agents.resume_analyzer import ResumeAnalyzerAgent
from app.core.config import get_settings
from app.core.errors import AppError, ErrorCode
from app.db.models.resume import Resume, ResumeProfile
from app.db.models.source_document import SourceDocument
from app.schemas.resume import ResumeProfile as ResumeProfileSchema


class ResumeService:
    def create_resume(
        self,
        db: Session,
        *,
        user_id: UUID,
        source_document_id: UUID,
        title: str,
        target_direction: str | None = None,
        version_label: str | None = None,
    ) -> Resume:
        source_document = db.get(SourceDocument, source_document_id)
        if source_document is None:
            raise AppError(ErrorCode.NOT_FOUND, "Source document not found", status_code=404)
        if source_document.document_type != "resume":
            raise AppError(
                ErrorCode.VALIDATION_ERROR,
                "Source document must be a resume",
                status_code=422,
            )

        resume = Resume(
            user_id=user_id,
            source_document_id=source_document_id,
            title=title,
            target_direction=target_direction,
            version_label=version_label,
            is_active=True,
        )
        db.add(resume)
        db.commit()
        db.refresh(resume)
        return resume

    async def parse_resume(self, db: Session, *, resume_id: UUID) -> tuple[ResumeProfile, UUID]:
        resume = db.get(Resume, resume_id)
        if resume is None:
            raise AppError(ErrorCode.NOT_FOUND, "Resume not found", status_code=404)

        source_document = db.get(SourceDocument, resume.source_document_id)
        if source_document is None:
            raise AppError(ErrorCode.NOT_FOUND, "Source document not found", status_code=404)

        agent = ResumeAnalyzerAgent(llm_client=get_llm_client())
        result = await AgentHarness().run_agent(
            db=db,
            user_id=get_settings().default_user_id,
            run_type="resume_parse",
            agent=agent,
            input_data={
                "resume_id": str(resume.id),
                "source_document_id": str(source_document.id),
                "raw_text": source_document.raw_text,
            },
            output_schema=ResumeProfileSchema,
        )
        output = result.output
        profile = ResumeProfile(
            resume_id=resume.id,
            agent_run_id=result.agent_run_id,
            schema_version=output.schema_version,
            profile_json=output.model_dump(mode="json"),
            skills=output.skills,
            projects=[project.model_dump(mode="json") for project in output.projects],
            backend_tags=output.backend_tags,
            risk_points=output.risk_points,
        )
        db.add(profile)
        db.commit()
        db.refresh(profile)
        return profile, result.agent_run_id
