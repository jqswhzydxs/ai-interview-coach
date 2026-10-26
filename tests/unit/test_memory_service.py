from decimal import Decimal
from uuid import UUID

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db.base import Base, import_models
from app.db.models.evaluation import AnswerEvaluation
from app.db.models.memory import MemoryItem
from app.db.models.user import User
from app.services.memory_service import MemoryService


def make_session():
    import_models()
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    return SessionLocal()


def create_evaluation(session, *, confidence: float) -> AnswerEvaluation:
    user_id = UUID("00000000-0000-0000-0000-000000000001")
    session.add(User(id=user_id, display_name="Default Candidate", role="candidate"))
    evaluation = AnswerEvaluation(
        user_id=user_id,
        custom_question_text="Explain your project",
        user_answer="I built FastAPI APIs.",
        total_score=Decimal("76"),
        relevance_score=Decimal("17"),
        technical_accuracy_score=Decimal("19"),
        project_specificity_score=Decimal("14"),
        structure_score=Decimal("12"),
        communication_score=Decimal("8"),
        risk_control_score=Decimal("6"),
        strengths_json=["clear stack"],
        improvement_points_json=["add metrics"],
        risks_json=[],
        improved_answer="Add metrics and tradeoffs.",
        follow_up_questions_json=["What tradeoff did you make?"],
        next_practice_suggestion="Practice project depth.",
        memory_update_json={"content": "Needs metrics", "confidence": confidence},
        evaluation_json={},
    )
    session.add(evaluation)
    session.commit()
    session.refresh(evaluation)
    return evaluation


def test_high_confidence_memory_update_is_persisted() -> None:
    session = make_session()
    evaluation = create_evaluation(session, confidence=0.85)

    item = MemoryService().apply_memory_update(session, evaluation)

    stored = session.scalars(select(MemoryItem)).all()
    assert item is not None
    assert len(stored) == 1
    assert stored[0].source_type == "answer_evaluation"
    assert stored[0].source_id == evaluation.id
    assert stored[0].confidence == Decimal("0.850")


def test_low_confidence_memory_update_is_not_persisted() -> None:
    session = make_session()
    evaluation = create_evaluation(session, confidence=0.55)

    item = MemoryService().apply_memory_update(session, evaluation)

    stored = session.scalars(select(MemoryItem)).all()
    assert item is None
    assert stored == []


def test_degraded_evaluation_memory_update_is_never_persisted() -> None:
    session = make_session()
    evaluation = create_evaluation(session, confidence=0.99)
    evaluation.evaluation_mode = "degraded"
    evaluation.score_available = False
    evaluation.source_quality = "degraded"
    evaluation.source_context_json = {
        "question": {"execution_mode": "fallback", "source_quality": "degraded"}
    }
    evaluation.total_score = None
    evaluation.relevance_score = None
    evaluation.technical_accuracy_score = None
    evaluation.project_specificity_score = None
    evaluation.structure_score = None
    evaluation.communication_score = None
    evaluation.risk_control_score = None
    evaluation.memory_update_json = {
        "write_decision": "skip",
        "skip_reason": {"code": "degraded_evaluation"},
        "confidence": 0,
    }
    session.commit()

    item = MemoryService().apply_memory_update(session, evaluation)

    assert item is None
    assert session.scalars(select(MemoryItem)).all() == []
