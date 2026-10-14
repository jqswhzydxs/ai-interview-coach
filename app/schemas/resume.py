from app.schemas.common import AgentOutputMetadata, EvidenceRef, StrictBaseModel


class ResumeProject(StrictBaseModel):
    name: str
    role: str
    background: str
    tech_stack: list[str]
    responsibilities: list[str]
    highlights: list[str]
    metrics: list[str]
    evidence_refs: list[EvidenceRef]


class ResumeProfile(AgentOutputMetadata):
    basic_info: dict
    education: list[dict]
    skills: list[str]
    projects: list[ResumeProject]
    work_experiences: list[dict]
    awards: list[str]
    backend_tags: list[str]
    questionable_points: list[str]
    risk_points: list[str]
