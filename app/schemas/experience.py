from app.schemas.common import AgentOutputMetadata, EvidenceRef


class ExperienceProfile(AgentOutputMetadata):
    source_summary: str
    frequent_questions: list[str]
    frequent_topics: list[str]
    follow_up_patterns: list[str]
    jd_related_points: list[str]
    resume_related_points: list[str]
    evidence_refs: list[EvidenceRef]
