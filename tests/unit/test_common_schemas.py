from datetime import datetime, timezone
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.schemas.common import ActionItem, AgentOutputMetadata, EvidenceRef, ScoreItem


def test_evidence_ref_accepts_known_source_types() -> None:
    evidence = EvidenceRef(
        source_type="resume",
        source_id=UUID("00000000-0000-0000-0000-000000000001"),
        quote="Built FastAPI service",
        summary="Resume project evidence",
    )

    assert evidence.source_type == "resume"
    assert evidence.source_id is not None


def test_evidence_ref_rejects_unknown_source_type() -> None:
    with pytest.raises(ValidationError):
        EvidenceRef(source_type="mixed", summary="Question-level source type is not common evidence")


def test_score_item_rejects_score_above_max_score() -> None:
    with pytest.raises(ValidationError):
        ScoreItem(name="technical_accuracy", score=26, max_score=25, reason="too high")


def test_score_item_accepts_equal_score_and_max_score() -> None:
    item = ScoreItem(name="structure", score=15, max_score=15, reason="clear structure")

    assert item.score == item.max_score


def test_action_item_rejects_unknown_priority() -> None:
    with pytest.raises(ValidationError):
        ActionItem(title="Practice", priority="urgent", description="Not in MVP enum")


def test_agent_output_metadata_fields_are_required() -> None:
    generated_at = datetime.now(timezone.utc)
    metadata = AgentOutputMetadata(
        schema_version="v0.1",
        generated_at=generated_at,
        agent_name="resume_analyzer",
        prompt_version="resume_analyzer_v0.1",
    )

    assert metadata.generated_at == generated_at
