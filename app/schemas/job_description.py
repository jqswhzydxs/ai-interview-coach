from app.schemas.common import AgentOutputMetadata, EvidenceRef


class JDProfile(AgentOutputMetadata):
    job_title: str
    company_name: str | None = None
    job_level: str | None = None
    core_responsibilities: list[str]
    hard_requirements: list[str]
    bonus_points: list[str]
    tech_keywords: list[str]
    backend_dimensions: list[str]
    interview_focuses: list[str]
    evidence_refs: list[EvidenceRef]
