from uuid import UUID

import pytest
from pydantic import ValidationError

from app.schemas.memory import MemoryItem


def test_memory_item_accepts_valid_payload() -> None:
    item = MemoryItem(
        memory_type="weakness",
        category="answer_quality",
        content="Needs more measurable project impact",
        evidence=[{"source_type": "answer", "summary": "Single answer evaluation"}],
        confidence=0.85,
        source_type="answer_evaluation",
        source_id=UUID("00000000-0000-0000-0000-000000000001"),
        status="active",
    )

    assert item.status == "active"


def test_memory_item_rejects_invalid_status() -> None:
    with pytest.raises(ValidationError):
        MemoryItem(
            memory_type="weakness",
            category="answer_quality",
            content="Needs metrics",
            evidence=[{"source_type": "answer", "summary": "Evaluation"}],
            confidence=0.85,
            source_type="answer_evaluation",
            source_id=None,
            status="pending",
        )
