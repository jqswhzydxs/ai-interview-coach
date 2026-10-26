from decimal import Decimal

from sqlalchemy.orm import Session

from app.agents.source_quality import fallback_source_names
from app.db.models.agent_run import AgentRun
from app.db.models.evaluation import AnswerEvaluation
from app.db.models.memory import MemoryItem


class MemoryService:
    high_confidence_threshold = 0.8

    def apply_memory_update(
        self, db: Session, evaluation: AnswerEvaluation
    ) -> MemoryItem | None:
        evaluator_run = (
            db.get(AgentRun, evaluation.agent_run_id)
            if evaluation.agent_run_id is not None
            else None
        )
        if (
            evaluation.evaluation_mode != "standard"
            or not evaluation.score_available
            or evaluation.source_quality == "degraded"
            or fallback_source_names(evaluation.source_context_json)
            or (
                evaluator_run is not None
                and evaluator_run.execution_mode == "fallback"
            )
        ):
            return None

        update = evaluation.memory_update_json or {}
        if update.get("write_decision", "write") != "write":
            return None
        confidence = float(update.get("confidence", 0))
        if confidence < self.high_confidence_threshold:
            return None

        content = update.get("content") or "需要继续观察的回答表现"
        memory_item = MemoryItem(
            user_id=evaluation.user_id,
            memory_type="weakness",
            category="answer_quality",
            content=content,
            evidence_json=[
                {
                    "source_type": "answer",
                    "source_id": str(evaluation.id),
                    "summary": "来自单题回答评价",
                }
            ],
            confidence=Decimal(str(confidence)),
            source_type="answer_evaluation",
            source_id=evaluation.id,
            status="active",
        )
        db.add(memory_item)
        db.commit()
        db.refresh(memory_item)
        return memory_item
