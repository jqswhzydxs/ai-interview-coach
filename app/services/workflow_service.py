from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError, ErrorCode
from app.core.workflow_config import WorkflowSettings, get_workflow_settings
from app.db.models.interview_experience import InterviewExperience
from app.db.models.job_description import JobDescription
from app.db.models.question import InterviewQuestion
from app.db.models.resume import Resume
from app.db.models.workflow import (
    AnswerSubmission,
    PrepPackageRequest,
    WorkflowJob,
    WorkflowJobResult,
    WorkflowJobStage,
)
from app.schemas.workflow import (
    AnswerSubmissionCreate,
    PrepPackageRequestCreate,
    WorkflowJobCreate,
)


ACTIVE_STATUSES = {"queued", "running"}
TERMINAL_STATUSES = {"succeeded", "failed", "cancelled"}


class WorkflowService:
    def __init__(self, settings: WorkflowSettings | None = None) -> None:
        self.settings = settings or get_workflow_settings()

    def create_prep_package_request(
        self, db: Session, *, user_id: UUID, payload: PrepPackageRequestCreate
    ) -> PrepPackageRequest:
        self._owned(db, Resume, payload.resume_id, user_id, "Resume")
        self._owned(db, JobDescription, payload.job_description_id, user_id, "Job description")
        for experience_id in payload.interview_experience_ids:
            self._owned(db, InterviewExperience, experience_id, user_id, "Interview experience")
        request = PrepPackageRequest(
            user_id=user_id,
            resume_id=payload.resume_id,
            job_description_id=payload.job_description_id,
            interview_experience_ids_json=[str(value) for value in payload.interview_experience_ids],
            preparation_goal=payload.preparation_goal,
            title=payload.title,
        )
        db.add(request)
        db.commit()
        db.refresh(request)
        return request

    def create_answer_submission(
        self, db: Session, *, user_id: UUID, payload: AnswerSubmissionCreate
    ) -> AnswerSubmission:
        if payload.question_db_id is not None and db.get(InterviewQuestion, payload.question_db_id) is None:
            raise AppError(ErrorCode.NOT_FOUND, "Question not found", status_code=404)
        submission = AnswerSubmission(
            user_id=user_id,
            question_db_id=payload.question_db_id,
            custom_question_text=payload.custom_question_text,
            user_answer=payload.user_answer,
        )
        db.add(submission)
        db.commit()
        db.refresh(submission)
        return submission

    def enqueue(
        self,
        db: Session,
        *,
        user_id: UUID,
        payload: WorkflowJobCreate,
        idempotency_key: str,
    ) -> tuple[WorkflowJob, bool]:
        if not idempotency_key or len(idempotency_key) > 200:
            raise AppError(ErrorCode.VALIDATION_ERROR, "A valid Idempotency-Key is required", 422)
        self._validate_input_resource(db, user_id=user_id, payload=payload)
        digest = self._key_digest(idempotency_key)
        fingerprint = self._fingerprint(payload)
        existing = db.scalar(
            select(WorkflowJob).where(
                WorkflowJob.user_id == user_id,
                WorkflowJob.idempotency_key_digest == digest,
            )
        )
        if existing is not None:
            self._assert_fingerprint(existing, fingerprint)
            return existing, True

        now = datetime.now(timezone.utc)
        job = WorkflowJob(
            user_id=user_id,
            workflow_type=payload.workflow_type,
            input_resource_type=payload.input_resource.resource_type,
            input_resource_id=payload.input_resource.resource_id,
            idempotency_key_digest=digest,
            request_fingerprint=fingerprint,
            status="queued",
            outcome_mode=None,
            progress_stage="queued",
            progress_current=0,
            progress_total=len(self._stage_keys(payload.workflow_type)),
            max_attempts=self.settings.max_attempts,
            available_at=now,
            absolute_deadline_at=now + timedelta(seconds=self.settings.absolute_deadline_seconds),
            agent_run_ids_json=[],
        )
        db.add(job)
        db.flush()
        for index, stage_key in enumerate(self._stage_keys(payload.workflow_type), start=1):
            db.add(
                WorkflowJobStage(
                    workflow_job_id=job.id,
                    stable_stage_id=f"{job.id}:{stage_key}",
                    stage_key=stage_key,
                    stage_order=index,
                    status="pending",
                    external_effect_state="not_started",
                )
            )
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            existing = db.scalar(
                select(WorkflowJob).where(
                    WorkflowJob.user_id == user_id,
                    WorkflowJob.idempotency_key_digest == digest,
                )
            )
            if existing is None:
                raise
            self._assert_fingerprint(existing, fingerprint)
            return existing, True
        db.refresh(job)
        return job, False

    def get_owned(self, db: Session, *, user_id: UUID, job_id: UUID) -> WorkflowJob:
        job = db.get(WorkflowJob, job_id)
        if job is None or job.user_id != user_id:
            raise AppError(ErrorCode.NOT_FOUND, "Workflow job not found", 404)
        return job

    def cancel(self, db: Session, *, user_id: UUID, job_id: UUID) -> tuple[WorkflowJob, int]:
        job = self.get_owned(db, user_id=user_id, job_id=job_id)
        now = datetime.now(timezone.utc)
        if job.status == "queued":
            job.status = "cancelled"
            job.progress_stage = "cancelled"
            job.cancel_requested_at = now
            job.finished_at = now
            for stage in self._stages(db, job.id):
                if stage.status == "pending":
                    stage.status = "cancelled"
                    stage.finished_at = now
            db.commit()
            return job, 200
        if job.status == "running":
            if job.cancel_requested_at is None:
                job.cancel_requested_at = now
                db.commit()
            return job, 202
        if job.status == "cancelled":
            return job, 200
        raise AppError(ErrorCode.CONFLICT, "Terminal workflow job cannot be cancelled", 409)

    def serialize(self, db: Session, job: WorkflowJob) -> dict:
        stages = self._stages(db, job.id)
        results = db.scalars(
            select(WorkflowJobResult)
            .where(WorkflowJobResult.workflow_job_id == job.id)
            .order_by(WorkflowJobResult.created_at, WorkflowJobResult.relation)
        ).all()
        safe_failure = None
        if job.safe_failure_category and job.safe_failure_code:
            safe_failure = {"category": job.safe_failure_category, "code": job.safe_failure_code}
        return {
            "workflow_job_id": job.id,
            "workflow_type": job.workflow_type,
            "status": job.status,
            "outcome_mode": job.outcome_mode,
            "progress_stage": job.progress_stage,
            "progress_current": job.progress_current,
            "progress_total": job.progress_total,
            "attempt_count": job.attempt_count,
            "cancel_requested": job.cancel_requested_at is not None,
            "safe_failure": safe_failure,
            "result_resources": [
                {
                    "relation": result.relation,
                    "resource_type": result.resource_type,
                    "resource_id": result.resource_id,
                    "href": result.resource_href,
                }
                for result in results
            ],
            "agent_run_ids": [UUID(value) for value in job.agent_run_ids_json],
            "stages": [
                {
                    "stage_id": stage.stable_stage_id,
                    "stage": stage.stage_key,
                    "order": stage.stage_order,
                    "status": stage.status,
                    "started_at": stage.started_at,
                    "finished_at": stage.finished_at,
                }
                for stage in stages
            ],
            "created_at": job.created_at,
            "started_at": job.started_at,
            "heartbeat_at": job.heartbeat_at,
            "finished_at": job.finished_at,
        }

    def _validate_input_resource(self, db: Session, *, user_id: UUID, payload: WorkflowJobCreate) -> None:
        models = {
            "resume": Resume,
            "job_description": JobDescription,
            "interview_experience": InterviewExperience,
            "prep_package_request": PrepPackageRequest,
            "answer_submission": AnswerSubmission,
        }
        self._owned(
            db,
            models[payload.input_resource.resource_type],
            payload.input_resource.resource_id,
            user_id,
            "Input resource",
        )

    @staticmethod
    def _owned(db: Session, model: type, resource_id: UUID, user_id: UUID, label: str):
        resource = db.get(model, resource_id)
        if resource is None or resource.user_id != user_id:
            raise AppError(ErrorCode.NOT_FOUND, f"{label} not found", 404)
        return resource

    def _key_digest(self, raw_key: str) -> str:
        secret = self.settings.effective_idempotency_secret().encode("utf-8")
        return hmac.new(secret, raw_key.encode("utf-8"), hashlib.sha256).hexdigest()

    @staticmethod
    def _fingerprint(payload: WorkflowJobCreate) -> str:
        canonical = json.dumps(payload.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @staticmethod
    def _assert_fingerprint(job: WorkflowJob, fingerprint: str) -> None:
        if not hmac.compare_digest(job.request_fingerprint, fingerprint):
            raise AppError(ErrorCode.CONFLICT, "Idempotency-Key conflicts with a different request", 409)

    @staticmethod
    def _stage_keys(workflow_type: str) -> list[str]:
        if workflow_type == "prep_package_generation":
            return ["resume_parse", "job_description_parse", "interview_experience_parse", "prep_package_generation"]
        return [workflow_type]

    @staticmethod
    def _stages(db: Session, job_id: UUID) -> list[WorkflowJobStage]:
        return list(
            db.scalars(
                select(WorkflowJobStage)
                .where(WorkflowJobStage.workflow_job_id == job_id)
                .order_by(WorkflowJobStage.stage_order)
            ).all()
        )
