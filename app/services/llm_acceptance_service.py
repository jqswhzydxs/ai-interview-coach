from dataclasses import dataclass
from collections.abc import Callable
from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.answer_evaluator import AnswerEvaluatorAgent
from app.agents.base import BaseAgent
from app.agents.experience_analyzer import ExperienceAnalyzerAgent
from app.agents.harness import AgentHarness
from app.agents.jd_analyzer import JDAnalyzerAgent
from app.agents.llm_client import LLMClient
from app.agents.matching_agent import MatchingAgent
from app.agents.memory_agent import MemoryAgent
from app.agents.question_bank_agent import QuestionBankAgent
from app.agents.resume_analyzer import ResumeAnalyzerAgent
from app.agents.source_quality import source_context_from_metadata
from app.db.models.agent_run import AgentRun
from app.schemas.evaluation import AnswerEvaluation
from app.schemas.experience import ExperienceProfile
from app.schemas.job_description import JDProfile
from app.schemas.memory import MemoryUpdate
from app.schemas.prep_package import MatchReport
from app.schemas.question import QuestionBank
from app.schemas.resume import ResumeProfile
from app.services.agent_run_service import AgentRunService


REQUIRED_CASE_FIELDS = {
    "resume_text",
    "jd_text",
    "preparation_goal",
    "experience_text",
    "user_answer",
}


@dataclass(frozen=True)
class AcceptanceArtifacts:
    json_path: Path
    markdown_path: Path
    report: dict


class LLMAcceptanceRunner:
    """Run fixed, synthetic acceptance cases without persisting their source text."""

    def __init__(
        self,
        *,
        llm_client: LLMClient,
        report_dir: Path,
        input_cost_per_million: Decimal | None = None,
        output_cost_per_million: Decimal | None = None,
        cost_currency: str = "USD",
        question_bank_agent_factory: Callable[[LLMClient], BaseAgent] | None = None,
    ) -> None:
        self.llm_client = llm_client
        self.report_dir = report_dir
        self.input_cost_per_million = input_cost_per_million
        self.output_cost_per_million = output_cost_per_million
        self.cost_currency = cost_currency
        self.question_bank_agent_factory = (
            question_bank_agent_factory or QuestionBankAgent
        )
        self.harness = AgentHarness()
        self.run_service = AgentRunService()

    async def run(
        self,
        *,
        db: Session,
        user_id: UUID,
        sample_dir: Path,
    ) -> AcceptanceArtifacts:
        cases = self._load_cases(sample_dir)
        case_reports: list[dict] = []
        all_run_ids: list[UUID] = []
        for case_id, case_data in cases:
            try:
                case_report, run_ids = await self._run_case(
                    db=db,
                    user_id=user_id,
                    case_id=case_id,
                    case_data=case_data,
                )
            except Exception:
                db.rollback()
                failed_runs = list(
                    db.scalars(
                        select(AgentRun)
                        .where(AgentRun.run_type.like(f"acceptance_{case_id}_%"))
                        .order_by(AgentRun.created_at)
                    ).all()
                )
                run_ids = [run.id for run in failed_runs]
                serialized = [
                    self.run_service.serialize_observability(run) for run in failed_runs
                ]
                case_report = {
                    "case_id": case_id,
                    "status": "failed",
                    "execution_mode": _case_execution_mode(serialized),
                    "failure": {"code": "acceptance_pipeline_failed"},
                    "agent_runs": serialized,
                }
            case_reports.append(case_report)
            all_run_ids.extend(run_ids)

        metrics = self.run_service.get_metrics(db, run_ids=all_run_ids)
        generated_at = datetime.now(timezone.utc)
        report = {
            "report_version": "v0.1",
            "generated_at": generated_at.isoformat(),
            "provider": getattr(self.llm_client, "provider", "unknown"),
            "model": getattr(self.llm_client, "model_name", None),
            "sample_case_count": len(cases),
            "summary": metrics,
            "cost_estimate": self._cost_estimate(metrics),
            "sample_cases": case_reports,
            "safety": {
                "contains_full_inputs": False,
                "contains_raw_model_responses": False,
                "save_full_llm_logs_required": False,
            },
        }
        return self._write_report(report, generated_at)

    def _load_cases(self, sample_dir: Path) -> list[tuple[str, dict]]:
        paths = sorted(sample_dir.glob("*.json"))
        if not paths:
            raise ValueError(f"No sample cases found in {sample_dir}")
        cases: list[tuple[str, dict]] = []
        for path in paths:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError(f"Sample case must be a JSON object: {path.name}")
            missing = sorted(REQUIRED_CASE_FIELDS - data.keys())
            if missing:
                raise ValueError(f"Sample case {path.name} is missing fields: {missing}")
            cases.append((path.stem, data))
        return cases

    async def _run_case(
        self,
        *,
        db: Session,
        user_id: UUID,
        case_id: str,
        case_data: dict,
    ) -> tuple[dict, list[UUID]]:
        run_ids: list[UUID] = []

        resume = await self._run_agent(
            db=db,
            user_id=user_id,
            case_id=case_id,
            stage="resume",
            agent=ResumeAnalyzerAgent(self.llm_client),
            input_data={"raw_text": case_data["resume_text"]},
            output_schema=ResumeProfile,
        )
        run_ids.append(resume.agent_run_id)
        jd = await self._run_agent(
            db=db,
            user_id=user_id,
            case_id=case_id,
            stage="jd",
            agent=JDAnalyzerAgent(self.llm_client),
            input_data={"raw_text": case_data["jd_text"], "title": "Backend Engineer"},
            output_schema=JDProfile,
        )
        run_ids.append(jd.agent_run_id)
        experience = await self._run_agent(
            db=db,
            user_id=user_id,
            case_id=case_id,
            stage="experience",
            agent=ExperienceAnalyzerAgent(self.llm_client),
            input_data={"raw_text": case_data["experience_text"]},
            output_schema=ExperienceProfile,
        )
        run_ids.append(experience.agent_run_id)
        profile_source_context = source_context_from_metadata(
            resume_profile=resume.metadata,
            jd_profile=jd.metadata,
            experience_profile=experience.metadata,
        )
        matching = await self._run_agent(
            db=db,
            user_id=user_id,
            case_id=case_id,
            stage="matching",
            agent=MatchingAgent(self.llm_client),
            input_data={
                "resume_profile": resume.output.model_dump(mode="json"),
                "jd_profile": jd.output.model_dump(mode="json"),
                "experience_profiles": [experience.output.model_dump(mode="json")],
                "preparation_goal": case_data["preparation_goal"],
                "source_context": profile_source_context,
            },
            output_schema=MatchReport,
        )
        run_ids.append(matching.agent_run_id)
        question_source_context = {
            **profile_source_context,
            **source_context_from_metadata(matching=matching.metadata),
        }
        question_bank = await self._run_agent(
            db=db,
            user_id=user_id,
            case_id=case_id,
            stage="question_bank",
            agent=self.question_bank_agent_factory(self.llm_client),
            input_data={
                "resume_profile": resume.output.model_dump(mode="json"),
                "jd_profile": jd.output.model_dump(mode="json"),
                "experience_profiles": [experience.output.model_dump(mode="json")],
                "match_report": matching.output.model_dump(mode="json"),
                "preparation_goal": case_data["preparation_goal"],
                "source_context": question_source_context,
            },
            output_schema=QuestionBank,
        )
        run_ids.append(question_bank.agent_run_id)
        question = question_bank.output.professional_questions[0]
        evaluation_source_context = {
            **question_source_context,
            **source_context_from_metadata(question=question_bank.metadata),
        }
        evaluation = await self._run_agent(
            db=db,
            user_id=user_id,
            case_id=case_id,
            stage="evaluation",
            agent=AnswerEvaluatorAgent(self.llm_client),
            input_data={
                "question_id": question.question_id,
                "question_text": question.question_text,
                "user_answer": case_data["user_answer"],
                "scoring_anchors": [
                    item.model_dump(mode="json") for item in question.scoring_anchors
                ],
                "resume_profile": resume.output.model_dump(mode="json"),
                "jd_profile": jd.output.model_dump(mode="json"),
                "source_context": evaluation_source_context,
            },
            output_schema=AnswerEvaluation,
        )
        run_ids.append(evaluation.agent_run_id)
        memory_source_context = {
            **evaluation_source_context,
            **source_context_from_metadata(answer_evaluation=evaluation.metadata),
        }
        memory = await self._run_agent(
            db=db,
            user_id=user_id,
            case_id=case_id,
            stage="memory",
            agent=MemoryAgent(self.llm_client),
            input_data={
                "answer_evaluation": evaluation.output.model_dump(mode="json"),
                "source_context": memory_source_context,
            },
            output_schema=MemoryUpdate,
        )
        run_ids.append(memory.agent_run_id)

        runs = list(
            db.scalars(select(AgentRun).where(AgentRun.id.in_(run_ids))).all()
        )
        runs_by_id = {run.id: run for run in runs}
        serialized = [
            self.run_service.serialize_observability(runs_by_id[run_id]) for run_id in run_ids
        ]
        return {
            "case_id": case_id,
            "status": "succeeded",
            "execution_mode": _case_execution_mode(serialized),
            "agent_runs": serialized,
        }, run_ids

    async def _run_agent(self, **kwargs):
        case_id = kwargs.pop("case_id")
        stage = kwargs.pop("stage")
        return await self.harness.run_agent(
            run_type=f"acceptance_{case_id}_{stage}"[:80],
            **kwargs,
        )

    def _cost_estimate(self, metrics: dict) -> dict:
        if self.input_cost_per_million is None or self.output_cost_per_million is None:
            return {
                "status": "not_configured",
                "amount": None,
                "currency": self.cost_currency,
                "note": "Configure per-million input and output token rates to estimate cost.",
            }
        usage = metrics["token_usage"]
        amount = (
            Decimal(usage["input_tokens"]) * self.input_cost_per_million
            + Decimal(usage["output_tokens"]) * self.output_cost_per_million
        ) / Decimal(1_000_000)
        return {
            "status": "estimated",
            "amount": format(amount.quantize(Decimal("0.000001")), "f"),
            "currency": self.cost_currency,
            "note": "Estimate uses explicitly configured rates; no provider price is hard-coded.",
        }

    def _write_report(self, report: dict, generated_at: datetime) -> AcceptanceArtifacts:
        self.report_dir.mkdir(parents=True, exist_ok=True)
        provider = _safe_filename(str(report["provider"]))
        stamp = generated_at.strftime("%Y%m%dT%H%M%SZ")
        base_name = f"llm-acceptance-{provider}-{stamp}"
        json_path = self.report_dir / f"{base_name}.json"
        markdown_path = self.report_dir / f"{base_name}.md"
        json_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        markdown_path.write_text(_render_markdown(report), encoding="utf-8")
        return AcceptanceArtifacts(
            json_path=json_path,
            markdown_path=markdown_path,
            report=report,
        )


def _safe_filename(value: str) -> str:
    return "".join(char if char.isalnum() or char in {"-", "_"} else "-" for char in value)


def _case_execution_mode(agent_runs: list[dict]) -> str:
    modes = {item["execution_mode"] for item in agent_runs}
    if not modes:
        return "unknown"
    if "fallback" in modes:
        return "fallback"
    if modes == {"real"}:
        return "real"
    if modes == {"mock"}:
        return "mock"
    return "mixed"


def _render_markdown(report: dict) -> str:
    summary = report["summary"]
    cost = report["cost_estimate"]
    lines = [
        "# Real LLM Acceptance Report",
        "",
        f"- Generated at: {report['generated_at']}",
        f"- Provider: {report['provider']}",
        f"- Model: {report['model'] or 'unspecified'}",
        f"- Sample cases: {report['sample_case_count']}",
        f"- Real success rate: {_format_rate(summary['real_success_rate'])}",
        f"- Fallback rate: {_format_rate(summary['fallback_rate'])}",
        f"- Real calls / retries: {summary['real_call_count']} / {summary['retry_count']}",
        f"- Token usage (input/output/total): {summary['token_usage']['input_tokens']} / "
        f"{summary['token_usage']['output_tokens']} / {summary['token_usage']['total_tokens']}",
        f"- Cost estimate: {cost['amount'] or cost['status']} {cost['currency']}",
        "",
        "## Failure types",
        "",
    ]
    if summary["failure_types"]:
        lines.extend(
            f"- {failure_type}: {count}"
            for failure_type, count in summary["failure_types"].items()
        )
    else:
        lines.append("- None")
    lines.extend(
        [
            "",
            "## Sample cases",
            "",
            "| Case | Status | Mode | Runs |",
            "| --- | --- | --- | ---: |",
        ]
    )
    for case in report["sample_cases"]:
        lines.append(
            f"| {case['case_id']} | {case['status']} | {case['execution_mode']} | "
            f"{len(case['agent_runs'])} |"
        )
    lines.extend(
        [
            "",
            "The report intentionally excludes full resumes, job descriptions, answers, prompts, "
            "API keys, and raw model responses.",
            "",
        ]
    )
    return "\n".join(lines)


def _format_rate(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.2%}"
