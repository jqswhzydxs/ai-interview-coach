"""Deterministic Phase 2.5A OpenAPI and frontend mock contract tooling.

This module is deliberately offline. It imports the FastAPI application to read its
OpenAPI model, but never starts the lifespan, opens a socket, or calls a Provider.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.api.v1.routes.documents import TextDocumentCreate
from app.api.v1.routes.evaluations import EvaluationCreate
from app.api.v1.routes.experiences import ExperienceCreate
from app.api.v1.routes.jobs import JobDescriptionCreate
from app.api.v1.routes.prep_packages import PrepPackageCreate
from app.api.v1.routes.resumes import ResumeCreate
from app.main import app
from app.schemas.evaluation import AnswerEvaluation
from app.schemas.question import QuestionBank
from app.schemas.response import ErrorResponse, SuccessResponse


CONTRACT_VERSION = "phase-2.5a-v0.1"
CONTRACT_DIR = ROOT / "contracts" / "frontend" / CONTRACT_VERSION
OPENAPI_PATH = CONTRACT_DIR / "openapi.json"
OPENAPI_SHA_PATH = CONTRACT_DIR / "openapi.sha256"
MATRIX_PATH = CONTRACT_DIR / "api-contract-matrix.json"
MOCK_DIR = CONTRACT_DIR / "mocks"
MOCK_CATALOG_PATH = CONTRACT_DIR / "mock-scenario-catalog.json"
MANIFEST_PATH = CONTRACT_DIR / "contract-manifest.json"

MOCK_SCHEMA_VERSION = "frontend-mock-v0.1"
SYNTHETIC_DATE = "2026-10-24T08:00:00Z"

UUIDS = {
    "document_resume": "00000000-0000-4000-8000-000000000101",
    "document_jd": "00000000-0000-4000-8000-000000000102",
    "resume": "00000000-0000-4000-8000-000000000201",
    "job": "00000000-0000-4000-8000-000000000301",
    "prep": "00000000-0000-4000-8000-000000000401",
    "run": "00000000-0000-4000-8000-000000000501",
    "evaluation": "00000000-0000-4000-8000-000000000601",
    "question": "00000000-0000-4000-8000-000000000701",
}


def canonical_json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def current_openapi() -> dict[str, Any]:
    return deepcopy(app.openapi())


def success(data: Any, request_id: str) -> dict[str, Any]:
    return {"data": data, "message": "ok", "request_id": request_id}


def error(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"error": {"code": code, "details": details or {}, "message": message}}


def score_items() -> list[dict[str, Any]]:
    return [
        {"name": name, "score": score, "max_score": 20, "reason": reason}
        for name, score, reason in (
            ("relevance", 17, "回答围绕题目展开。"),
            ("technical_accuracy", 16, "技术说明基本准确。"),
            ("project_specificity", 15, "包含可验证的项目细节。"),
            ("structure", 16, "表达结构清晰。"),
            ("communication", 16, "关键信息易于理解。"),
        )
    ]


def evaluation_payload(*, degraded: bool, memory_blocked: bool = False) -> dict[str, Any]:
    reasons = ["upstream_fallback:question", "evaluator_fallback"] if degraded else []
    return {
        "schema_version": "0.1",
        "generated_at": SYNTHETIC_DATE,
        "agent_name": "AnswerEvaluatorAgent",
        "prompt_version": "answer_evaluator_v0.1",
        "evaluation_mode": "degraded" if degraded else "standard",
        "score_available": not degraded,
        "source_quality": "degraded" if degraded else ("mixed" if memory_blocked else "trusted"),
        "degradation_reasons": reasons,
        "question_id": "professional_01",
        "question_text": "请说明一次后端接口设计中的关键权衡。",
        "user_answer": "示例回答仅用于合同测试，不对应真实个人经历。",
        "total_score": None if degraded else 80,
        "dimension_scores": [] if degraded else score_items(),
        "overall_comment": "当前结果仅用于离线界面状态验证。",
        "strengths": [] if degraded else ["结构清楚"],
        "improvement_points": ["补充决策依据"],
        "risks": ["来源降级，不能给出可信分数"] if degraded else [],
        "improved_answer": "示例改写内容。",
        "follow_up_questions": ["你如何验证这个权衡的效果？"],
        "next_practice_suggestion": "围绕约束、选择和结果进行练习。",
        "memory_update": (
            {
                "write_decision": "skip",
                "skip_reason": {
                    "code": "degraded_source_memory_write_blocked"
                    if degraded
                    else "upstream_source_memory_write_blocked"
                },
                "memory_items": [],
            }
            if degraded or memory_blocked
            else {
                "write_decision": "write",
                "confidence": 0.84,
                "content": "需要继续练习技术权衡表达。",
            }
        ),
    }


def evaluation_detail_data(*, degraded: bool, memory_blocked: bool = False) -> dict[str, Any]:
    payload = evaluation_payload(degraded=degraded, memory_blocked=memory_blocked)
    return {
        "answer_evaluation_id": UUIDS["evaluation"],
        "prep_package_id": UUIDS["prep"],
        "agent_run_id": UUIDS["run"],
        "evaluation_mode": payload["evaluation_mode"],
        "score_available": payload["score_available"],
        "source_quality": payload["source_quality"],
        "degradation_reasons": payload["degradation_reasons"],
        "total_score": payload["total_score"],
        "created_at": SYNTHETIC_DATE,
        "question_db_id": UUIDS["question"],
        "custom_question_text": None,
        "user_answer": payload["user_answer"],
        "strengths": payload["strengths"],
        "improvement_points": payload["improvement_points"],
        "risks": payload["risks"],
        "improved_answer": payload["improved_answer"],
        "follow_up_questions": payload["follow_up_questions"],
        "next_practice_suggestion": payload["next_practice_suggestion"],
        "memory_update": payload["memory_update"],
        "evaluation": payload,
    }


def agent_run_data(
    *,
    status: str,
    execution_mode: str,
    fallback_code: str | None = None,
    retry_count: int = 0,
) -> dict[str, Any]:
    fallback_reason = (
        {
            "code": fallback_code,
            "stage": "question_bank" if "question" in fallback_code else "upstream_profile",
            "retryable": True,
        }
        if fallback_code
        else None
    )
    running = status == "running"
    return {
        "agent_run_id": UUIDS["run"],
        "run_type": "question_bank_generation",
        "status": status,
        "execution_mode": execution_mode,
        "provider": "mock" if execution_mode == "mock" else "configured-provider",
        "model_name": None if running else "configured-model",
        "prompt_version": None if running else "production-default",
        "real_call_count": 0 if execution_mode == "mock" else 1 + retry_count,
        "retry_count": retry_count,
        "latency_ms": None if running else 1840,
        "token_usage": {
            "input_tokens": None if running else 480,
            "output_tokens": None if running else 720,
            "total_tokens": None if running else 1200,
        },
        "fallback_reason": fallback_reason,
        "failure_types": {"network": retry_count} if retry_count else {},
        "input_summary": {"keys": ["jd_profile", "resume_profile"]},
        "output_summary": {} if running else {"question_count": 25},
        "error_message": None,
        "created_at": SYNTHETIC_DATE,
        "started_at": SYNTHETIC_DATE,
        "finished_at": None if running else "2026-10-24T08:00:02Z",
        "steps": [
            {
                "agent_run_step_id": "00000000-0000-4000-8000-000000000511",
                "step_order": 1,
                "agent_name": "QuestionBankAgent",
                "action_type": "generate",
                "status": "running" if running else "succeeded",
                "error_message": None,
                "latency_ms": None if running else 1840,
                "created_at": SYNTHETIC_DATE,
            }
        ],
    }


def question_item(index: int, module: str, module_index: int) -> dict[str, Any]:
    difficulty = ("basic", "medium", "hard")[(index - 1) % 3]
    prefix = {
        "self_intro": "请结合一个安全的示例事实说明你的后端能力重点",
        "professional": "请分析一个后端技术对象的约束与权衡",
        "behavior_project": "请复盘一个项目决策、难点与结果",
    }[module]
    return {
        "question_db_id": f"00000000-0000-4000-8000-{index:012d}",
        "question_id": f"{module}_{module_index:02d}",
        "module": module,
        "question_text": f"{prefix}（示例 {module_index}）。",
        "purpose": "验证结构化面试问题的展示合同。",
        "difficulty": difficulty,
        "source_type": "inferred",
        "source_refs": [
            {
                "source_type": "inferred",
                "source_id": None,
                "quote": None,
                "summary": "合成合同测试事实，不对应真实个人数据。",
            }
        ],
        "jd_keywords": ["backend"],
        "answer_framework": "背景、约束、选择、结果",
        "star_template": "S/T/A/R",
        "scoring_anchors": [
            {"name": "clarity", "score": 4, "max_score": 5, "reason": "表达清楚"}
        ],
        "follow_up_questions": ["你会如何验证结果？"],
        "preparation_advice": "准备可验证的约束和结果。",
        "sort_order": index,
    }


def question_bank_items() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    absolute = 1
    for module, count in (("self_intro", 8), ("professional", 8), ("behavior_project", 9)):
        for module_index in range(1, count + 1):
            items.append(question_item(absolute, module, module_index))
            absolute += 1
    return items


def step(
    name: str,
    method: str,
    path: str,
    *,
    request_body: Any = None,
    query: dict[str, Any] | None = None,
    response_status: int | None = 200,
    response_body: Any = None,
    client_outcome: str = "completed",
    ui_state: str = "success",
    retryable: bool = False,
    source_quality_display: dict[str, str] | None = None,
    reason_message: str | None = None,
) -> dict[str, Any]:
    response = (
        None
        if response_status is None
        else {"status_code": response_status, "body": response_body}
    )
    ui = {"state": ui_state, "retryable": retryable}
    if source_quality_display is not None:
        ui["source_quality_display"] = source_quality_display
    if reason_message is not None:
        ui["reason_message"] = reason_message
    return {
        "name": name,
        "method": method,
        "path": path,
        "request": {
            "body": request_body,
            "headers": {"x-request-id": f"mock-{name}"},
            "query": query or {},
        },
        "response": response,
        "client_outcome": client_outcome,
        "ui": ui,
    }


def fixture(scenario_id: str, category: str, description: str, steps: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": MOCK_SCHEMA_VERSION,
        "scenario_id": scenario_id,
        "category": category,
        "description": description,
        "data_classification": "synthetic_non_personal",
        "steps": steps,
    }


def build_mock_scenarios() -> dict[str, dict[str, Any]]:
    standard_eval = evaluation_detail_data(degraded=False)
    degraded_eval = evaluation_detail_data(degraded=True)
    memory_blocked_eval = evaluation_detail_data(degraded=False, memory_blocked=True)
    questions = question_bank_items()
    return {
        "standard-success": fixture(
            "standard-success",
            "standard",
            "准备包完成后取得严格 8/8/9 的题库。",
            [
                step(
                    "create-prep-package",
                    "POST",
                    "/api/v1/prep-packages",
                    request_body={
                        "resume_id": UUIDS["resume"],
                        "job_description_id": UUIDS["job"],
                        "interview_experience_ids": [],
                        "preparation_goal": "练习后端面试题",
                        "title": "合成准备任务",
                    },
                    response_body=success(
                        {
                            "prep_package_id": UUIDS["prep"],
                            "agent_run_id": UUIDS["run"],
                            "status": "ready",
                        },
                        "mock-create-prep-package",
                    ),
                ),
                step(
                    "get-question-bank",
                    "GET",
                    f"/api/v1/prep-packages/{UUIDS['prep']}/questions",
                    response_body=success(
                        {"total": 25, "items": questions}, "mock-get-question-bank"
                    ),
                ),
            ],
        ),
        "upstream-fallback": fixture(
            "upstream-fallback",
            "fallback",
            "上游画像使用 fallback，界面展示来源质量和结构化原因。",
            [
                step(
                    "upstream-fallback-run",
                    "GET",
                    f"/api/v1/agent-runs/{UUIDS['run']}",
                    response_body=success(
                        agent_run_data(
                            status="succeeded",
                            execution_mode="fallback",
                            fallback_code="upstream_profile_fallback",
                        ),
                        "mock-upstream-fallback-run",
                    ),
                    ui_state="degraded",
                    retryable=True,
                    source_quality_display={
                        "value": "degraded",
                        "derived_from": "execution_mode",
                        "label": "降级来源",
                    },
                    reason_message="上游画像暂时不可用，当前结果使用了安全降级来源。",
                )
            ],
        ),
        "question-bank-fallback": fixture(
            "question-bank-fallback",
            "fallback",
            "题库由 fallback 产生，题目仍可浏览但来源质量必须可见。",
            [
                step(
                    "question-fallback-run",
                    "GET",
                    f"/api/v1/agent-runs/{UUIDS['run']}",
                    response_body=success(
                        agent_run_data(
                            status="succeeded",
                            execution_mode="fallback",
                            fallback_code="question_bank_fallback",
                        ),
                        "mock-question-fallback-run",
                    ),
                    ui_state="degraded",
                    source_quality_display={
                        "value": "degraded",
                        "derived_from": "execution_mode",
                        "label": "降级来源",
                    },
                    reason_message="题库生成使用了安全 fallback，可继续浏览并查看运行详情。",
                ),
                step(
                    "fallback-question-bank",
                    "GET",
                    f"/api/v1/prep-packages/{UUIDS['prep']}/questions",
                    response_body=success(
                        {"total": 25, "items": questions}, "mock-fallback-question-bank"
                    ),
                    ui_state="degraded",
                    source_quality_display={
                        "value": "degraded",
                        "derived_from": "linked_agent_run.execution_mode",
                        "label": "降级来源",
                    },
                    reason_message="题库生成使用了安全 fallback，可继续浏览并查看运行详情。",
                ),
            ],
        ),
        "evaluator-degraded": fixture(
            "evaluator-degraded",
            "degraded",
            "评价降级时不给出伪造分数。",
            [
                step(
                    "degraded-evaluation",
                    "GET",
                    f"/api/v1/evaluations/{UUIDS['evaluation']}",
                    response_body=success(degraded_eval, "mock-degraded-evaluation"),
                    ui_state="degraded",
                    source_quality_display={
                        "value": "degraded",
                        "derived_from": "response.source_quality",
                        "label": "降级来源",
                    },
                    reason_message="本次无法提供可信分数，但仍可查看非评分反馈。",
                )
            ],
        ),
        "standard-evaluation": fixture(
            "standard-evaluation",
            "standard",
            "标准评价包含真实可用的总分和维度分。",
            [
                step(
                    "standard-evaluation-detail",
                    "GET",
                    f"/api/v1/evaluations/{UUIDS['evaluation']}",
                    response_body=success(standard_eval, "mock-standard-evaluation-detail"),
                )
            ],
        ),
        "memory-write-blocked": fixture(
            "memory-write-blocked",
            "memory_safety",
            "来源不满足长期记忆写入条件时展示已阻断状态。",
            [
                step(
                    "memory-write-blocked-evaluation",
                    "GET",
                    f"/api/v1/evaluations/{UUIDS['evaluation']}",
                    response_body=success(
                        memory_blocked_eval, "mock-memory-write-blocked-evaluation"
                    ),
                    ui_state="degraded",
                    source_quality_display={
                        "value": "mixed",
                        "derived_from": "response.source_quality",
                        "label": "混合来源",
                    },
                    reason_message="当前结果未写入长期记忆。",
                )
            ],
        ),
        "agent-running": fixture(
            "agent-running",
            "processing",
            "Agent 运行详情处于进行中。",
            [
                step(
                    "running-agent",
                    "GET",
                    f"/api/v1/agent-runs/{UUIDS['run']}",
                    response_body=success(
                        agent_run_data(status="running", execution_mode="mock"),
                        "mock-running-agent",
                    ),
                    ui_state="processing",
                )
            ],
        ),
        "retryable-provider-error": fixture(
            "retryable-provider-error",
            "error",
            "Provider 暂时失败，前端提供明确重试动作。",
            [
                step(
                    "retryable-provider-failure",
                    "POST",
                    "/api/v1/evaluations",
                    request_body={
                        "question_db_id": UUIDS["question"],
                        "custom_question_text": None,
                        "user_answer": "合成回答。",
                    },
                    response_status=502,
                    response_body=error(
                        "AGENT_FAILED",
                        "Agent execution failed",
                        {"failure_category": "network"},
                    ),
                    ui_state="error",
                    retryable=True,
                )
            ],
        ),
        "nonretryable-contract-error": fixture(
            "nonretryable-contract-error",
            "error",
            "请求不满足 Schema 时返回字段级错误且不可原样重试。",
            [
                step(
                    "invalid-evaluation-request",
                    "POST",
                    "/api/v1/evaluations",
                    request_body={
                        "question_db_id": None,
                        "custom_question_text": None,
                        "user_answer": "",
                    },
                    response_status=422,
                    response_body=error(
                        "VALIDATION_ERROR",
                        "Invalid input",
                        {"errors": [{"loc": ["body", "user_answer"], "type": "string_too_short"}]},
                    ),
                    ui_state="error",
                )
            ],
        ),
        "empty-history": fixture(
            "empty-history",
            "empty",
            "没有历史评价时返回稳定空列表。",
            [
                step(
                    "empty-evaluation-history",
                    "GET",
                    "/api/v1/evaluations",
                    query={"limit": 20, "offset": 0},
                    response_body=success(
                        {"total": 0, "items": []}, "mock-empty-evaluation-history"
                    ),
                    ui_state="empty",
                )
            ],
        ),
        "file-upload-failure": fixture(
            "file-upload-failure",
            "error",
            "文件类型或大小不符合约束。",
            [
                step(
                    "invalid-file-upload",
                    "POST",
                    "/api/v1/documents/upload",
                    request_body={
                        "document_type": "resume",
                        "file": {
                            "name": "synthetic-resume.exe",
                            "content_type": "application/octet-stream",
                            "size_bytes": 1048577,
                        },
                    },
                    response_status=422,
                    response_body=error(
                        "VALIDATION_ERROR",
                        "Unsupported file type",
                        {"allowed_types": ["pdf", "docx", "txt"]},
                    ),
                    ui_state="error",
                )
            ],
        ),
        "request-cancelled-timeout": fixture(
            "request-cancelled-timeout",
            "client_control",
            "取消和超时均保留用户输入并给出恢复动作。",
            [
                step(
                    "cancelled-prep-submit",
                    "POST",
                    "/api/v1/prep-packages",
                    request_body={
                        "resume_id": UUIDS["resume"],
                        "job_description_id": UUIDS["job"],
                        "interview_experience_ids": [],
                        "preparation_goal": "合成目标",
                        "title": None,
                    },
                    response_status=None,
                    client_outcome="cancelled",
                    ui_state="cancelled",
                    retryable=True,
                ),
                step(
                    "timed-out-evaluation",
                    "POST",
                    "/api/v1/evaluations",
                    request_body={
                        "question_db_id": UUIDS["question"],
                        "custom_question_text": None,
                        "user_answer": "合成回答。",
                    },
                    response_status=None,
                    client_outcome="timeout",
                    ui_state="error",
                    retryable=True,
                ),
            ],
        ),
    }


REQUEST_MODELS: dict[tuple[str, str], type] = {
    ("POST", "/api/v1/documents/text"): TextDocumentCreate,
    ("POST", "/api/v1/resumes"): ResumeCreate,
    ("POST", "/api/v1/jobs"): JobDescriptionCreate,
    ("POST", "/api/v1/experiences"): ExperienceCreate,
    ("POST", "/api/v1/prep-packages"): PrepPackageCreate,
    ("POST", "/api/v1/evaluations"): EvaluationCreate,
}


ENDPOINT_UI_METADATA: dict[tuple[str, str], dict[str, Any]] = {
    ("GET", "/api/v1/health"): {"async": "immediate", "ui": "应用可用性指示；失败时提供刷新。"},
    ("POST", "/api/v1/documents/text"): {"async": "submitting", "ui": "字段校验、保存中、禁止重复提交。"},
    ("POST", "/api/v1/documents/upload"): {"async": "uploading", "ui": "进度、类型/大小错误、取消。"},
    ("POST", "/api/v1/resumes"): {"async": "submitting", "ui": "创建简历记录并保留返回 ID。"},
    ("POST", "/api/v1/resumes/{resume_id}/parse"): {"async": "processing", "ui": "显示解析步骤并深链 Agent run。"},
    ("POST", "/api/v1/jobs"): {"async": "submitting", "ui": "创建 JD 记录并保留返回 ID。"},
    ("POST", "/api/v1/jobs/{job_description_id}/parse"): {"async": "processing", "ui": "显示解析步骤并深链 Agent run。"},
    ("POST", "/api/v1/experiences"): {"async": "submitting", "ui": "可选面经创建；允许跳过。"},
    ("POST", "/api/v1/experiences/{interview_experience_id}/parse"): {"async": "processing", "ui": "显示解析步骤并深链 Agent run。"},
    ("POST", "/api/v1/prep-packages"): {"async": "processing", "ui": "显示多步骤进度；成功后进入摘要。"},
    ("GET", "/api/v1/prep-packages/{prep_package_id}"): {"async": "loading", "ui": "展示状态、问题数和摘要。"},
    ("GET", "/api/v1/prep-packages/{prep_package_id}/questions"): {"async": "loading", "ui": "8/8/9 标签、筛选、来源与降级说明。"},
    ("POST", "/api/v1/evaluations"): {"async": "processing", "ui": "标准/降级结果分支；无分数不得显示 0。"},
    ("GET", "/api/v1/evaluations"): {"async": "loading", "ui": "分页历史和空状态。"},
    ("GET", "/api/v1/evaluations/{answer_evaluation_id}"): {"async": "loading", "ui": "展示评价模式、来源质量、分数或无分数状态。"},
    ("GET", "/api/v1/agent-runs/{agent_run_id}"): {"async": "pollable", "ui": "步骤、execution_mode、fallback_reason、重试和 Token 可用性。"},
}


def operation_templates(openapi: dict[str, Any]) -> set[tuple[str, str]]:
    methods = {"get", "post", "put", "patch", "delete", "options", "head"}
    return {
        (method.upper(), path)
        for path, path_item in openapi["paths"].items()
        for method in path_item
        if method in methods
    }


def match_template(method: str, concrete_path: str, openapi: dict[str, Any]) -> str:
    candidates = [path for op_method, path in operation_templates(openapi) if op_method == method]
    for template in candidates:
        pattern = "^" + re.sub(r"\{[^/]+\}", r"[^/]+", template) + "$"
        if re.match(pattern, concrete_path):
            return template
    raise ValueError(f"mock path is not in OpenAPI: {method} {concrete_path}")


def build_contract_matrix(openapi: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for method, path in sorted(operation_templates(openapi), key=lambda item: (item[1], item[0])):
        operation = openapi["paths"][path][method.lower()]
        request_body = operation.get("requestBody")
        parameters = operation.get("parameters", [])
        nullable_fields = _nullable_fields_for_operation(method, path)
        rows.append(
            {
                "method": method,
                "path": path,
                "operation_id": operation.get("operationId"),
                "request_schema": _request_schema_label(request_body, parameters),
                "response_schema": "runtime SuccessResponse[data]; OpenAPI currently exposes generic object",
                "nullable_fields": nullable_fields,
                "loading_async_semantics": ENDPOINT_UI_METADATA[(method, path)]["async"],
                "failure_statuses": _failure_statuses(method, path),
                "degradation_fields": _degradation_fields(path),
                "frontend_display": ENDPOINT_UI_METADATA[(method, path)]["ui"],
            }
        )
    return rows


def _request_schema_label(request_body: Any, parameters: list[dict[str, Any]]) -> str:
    labels: list[str] = []
    if request_body:
        for media_type, media in request_body.get("content", {}).items():
            schema = media.get("schema", {})
            labels.append(f"{media_type}:{schema.get('$ref', schema.get('title', 'inline'))}")
    for parameter in parameters:
        labels.append(f"{parameter.get('in')}:{parameter.get('name')}")
    return ", ".join(labels) if labels else "none"


def _nullable_fields_for_operation(method: str, path: str) -> list[str]:
    mapping = {
        ("POST", "/api/v1/documents/text"): ["metadata"],
        ("POST", "/api/v1/resumes"): ["target_direction", "version_label"],
        ("POST", "/api/v1/jobs"): ["company_name", "job_url"],
        ("POST", "/api/v1/experiences"): ["company_name", "role_name"],
        ("POST", "/api/v1/prep-packages"): ["title"],
        ("GET", "/api/v1/prep-packages/{prep_package_id}"): ["title"],
        ("POST", "/api/v1/evaluations"): ["question_db_id", "custom_question_text", "total_score"],
        ("GET", "/api/v1/evaluations"): ["prep_package_id", "agent_run_id", "total_score"],
        ("GET", "/api/v1/evaluations/{answer_evaluation_id}"): ["prep_package_id", "question_db_id", "custom_question_text", "agent_run_id", "total_score"],
        ("GET", "/api/v1/agent-runs/{agent_run_id}"): ["model_name", "prompt_version", "latency_ms", "token_usage.*", "fallback_reason", "error_message", "finished_at", "steps[].error_message", "steps[].latency_ms"],
    }
    return mapping.get((method, path), [])


def _failure_statuses(method: str, path: str) -> list[int]:
    mapping = {
        ("GET", "/api/v1/health"): [],
        ("POST", "/api/v1/documents/text"): [422],
        ("POST", "/api/v1/documents/upload"): [422],
        ("POST", "/api/v1/resumes"): [404, 422],
        ("POST", "/api/v1/resumes/{resume_id}/parse"): [404, 422, 502],
        ("POST", "/api/v1/jobs"): [404, 422],
        ("POST", "/api/v1/jobs/{job_description_id}/parse"): [404, 422, 502],
        ("POST", "/api/v1/experiences"): [404, 422],
        ("POST", "/api/v1/experiences/{interview_experience_id}/parse"): [404, 422, 502],
        ("POST", "/api/v1/prep-packages"): [404, 422, 502],
        ("GET", "/api/v1/prep-packages/{prep_package_id}"): [404, 422],
        ("GET", "/api/v1/prep-packages/{prep_package_id}/questions"): [404, 422],
        ("POST", "/api/v1/evaluations"): [404, 422, 502],
        ("GET", "/api/v1/evaluations"): [422],
        ("GET", "/api/v1/evaluations/{answer_evaluation_id}"): [404, 422],
        ("GET", "/api/v1/agent-runs/{agent_run_id}"): [404, 422],
    }
    return mapping[(method, path)]


def _degradation_fields(path: str) -> list[str]:
    if path.startswith("/api/v1/evaluations"):
        return ["evaluation_mode", "score_available", "source_quality", "degradation_reasons"]
    if path.startswith("/api/v1/agent-runs"):
        return ["execution_mode", "fallback_reason", "failure_types"]
    return []


def validate_mock_fixture(fixture_value: dict[str, Any], openapi: dict[str, Any]) -> None:
    required = {"schema_version", "scenario_id", "category", "description", "data_classification", "steps"}
    if set(fixture_value) != required:
        raise ValueError(f"unexpected fixture fields: {set(fixture_value) ^ required}")
    if fixture_value["schema_version"] != MOCK_SCHEMA_VERSION:
        raise ValueError("unsupported mock schema version")
    if fixture_value["data_classification"] != "synthetic_non_personal":
        raise ValueError("mock data must be synthetic and non-personal")
    if not fixture_value["steps"]:
        raise ValueError("mock scenario requires at least one step")

    for item in fixture_value["steps"]:
        method = item["method"].upper()
        template = match_template(method, item["path"], openapi)
        request_body = item["request"]["body"]
        model = REQUEST_MODELS.get((method, template))
        expected_contract_error = fixture_value["scenario_id"] == "nonretryable-contract-error"
        if model is not None and request_body is not None:
            try:
                model.model_validate(request_body)
            except ValidationError:
                if not expected_contract_error:
                    raise
            else:
                if expected_contract_error:
                    raise ValueError("contract-error mock request unexpectedly validates")

        response = item["response"]
        if response is None:
            if item["client_outcome"] not in {"cancelled", "timeout"}:
                raise ValueError("missing response is only valid for cancelled or timeout")
            continue
        status = response["status_code"]
        body = response["body"]
        if 200 <= status < 300:
            SuccessResponse.model_validate(body)
        else:
            ErrorResponse.model_validate(body)

    _validate_scenario_semantics(fixture_value)
    _validate_no_sensitive_markers(fixture_value)


def _validate_scenario_semantics(value: dict[str, Any]) -> None:
    scenario_id = value["scenario_id"]
    success_bodies = [
        item["response"]["body"]["data"]
        for item in value["steps"]
        if item["response"] is not None and item["response"]["status_code"] < 300
    ]
    if scenario_id in {"standard-success", "question-bank-fallback"}:
        question_data = next(body for body in success_bodies if body.get("total") == 25)
        items = question_data["items"]
        groups = {
            module: [
                {key: item_value for key, item_value in item.items() if key != "question_db_id"}
                for item in items
                if item["module"] == module
            ]
            for module in ("self_intro", "professional", "behavior_project")
        }
        if [len(groups[name]) for name in groups] != [8, 8, 9]:
            raise ValueError("question mock must keep exact 8/8/9 counts")
        QuestionBank.model_validate(
            {
                "self_intro_questions": groups["self_intro"],
                "professional_questions": groups["professional"],
                "behavior_project_questions": groups["behavior_project"],
                "total_count": 25,
            }
        )
    if scenario_id in {"evaluator-degraded", "standard-evaluation", "memory-write-blocked"}:
        detail = success_bodies[0]
        parsed = AnswerEvaluation.model_validate(detail["evaluation"])
        if parsed.evaluation_mode == "degraded":
            if parsed.score_available or parsed.total_score is not None or parsed.dimension_scores:
                raise ValueError("degraded evaluation must not expose a score")
        if scenario_id == "standard-evaluation":
            if not parsed.score_available or parsed.total_score is None or not parsed.dimension_scores:
                raise ValueError("standard evaluation requires score and dimensions")
        if scenario_id == "memory-write-blocked":
            if detail["memory_update"].get("write_decision") != "skip":
                raise ValueError("memory blocked mock must make the no-write state explicit")
    if scenario_id in {"upstream-fallback", "question-bank-fallback"}:
        run = next(body for body in success_bodies if "execution_mode" in body)
        if run["execution_mode"] != "fallback" or not run["fallback_reason"]:
            raise ValueError("fallback mock requires fallback execution and reason")
    if scenario_id == "agent-running" and success_bodies[0]["status"] != "running":
        raise ValueError("agent-running mock must be running")
    if scenario_id == "empty-history" and success_bodies[0] != {"total": 0, "items": []}:
        raise ValueError("empty-history mock must be empty")


def _validate_no_sensitive_markers(value: dict[str, Any]) -> None:
    serialized = json.dumps(value, ensure_ascii=False).lower()
    forbidden = (
        "api_key",
        "authorization: bearer",
        "raw_response",
        "reasoning_content",
        "chain_of_thought",
        "begin private key",
        "question_bank_draft_agent_v0.3",
    )
    found = [marker for marker in forbidden if marker in serialized]
    if found:
        raise ValueError(f"sensitive or forbidden mock marker(s): {found}")


def build_manifest(openapi_sha256: str, mock_hashes: dict[str, str], matrix_sha256: str) -> dict[str, Any]:
    return {
        "record_type": "phase_2_5a_frontend_contract_manifest",
        "contract_version": CONTRACT_VERSION,
        "created_date": "2026-10-24",
        "mode": "offline_design_only",
        "provider_calls": 0,
        "frontend_scaffold_created": False,
        "npm_dependencies_installed": False,
        "production_question_bank_agent": "unchanged",
        "prompt_v0_3_status": "research_candidate_not_promoted",
        "openapi": {
            "path": OPENAPI_PATH.relative_to(ROOT).as_posix(),
            "sha256": openapi_sha256,
            "operation_count": 16,
        },
        "api_contract_matrix": {
            "path": MATRIX_PATH.relative_to(ROOT).as_posix(),
            "sha256": matrix_sha256,
        },
        "mock_contract": {
            "schema_version": MOCK_SCHEMA_VERSION,
            "scenario_count": len(mock_hashes),
            "files": dict(sorted(mock_hashes.items())),
        },
        "frozen_external_semantics": [
            "source_quality",
            "score_available",
            "evaluation_mode",
            "degradation_reasons",
            "fallback_reason",
            "nullable_score",
            "execution_mode",
            "memory_write_blocked",
            "standard_degraded_fallback_distinction",
            "question_bank_final_api_schema",
        ],
        "known_contract_gaps_proposals_only": [
            "Add explicit response_model declarations without changing runtime payloads.",
            "Document the runtime ErrorResponse envelope and 404/502 responses in OpenAPI.",
            "Expose source_quality on prep-package and question-bank reads; current fallback visibility comes from execution_mode and fallback_reason.",
            "Expose a structured memory-write outcome when product requirements need guard-level observability.",
            "Define backend-owned upload size and MIME limits before Phase 2.5B binds client validation.",
            "Define polling cadence or asynchronous job semantics; current create endpoints await completion.",
        ],
        "frontend_stack_adr": {
            "recommended": "React + TypeScript + Vite",
            "status": "awaiting_explicit_user_confirmation",
            "alternatives": ["Vue + TypeScript + Vite", "Next.js + TypeScript"],
        },
        "next_state": "await_phase_2_5b_stack_confirmation",
    }


def write_contract_assets() -> dict[str, Any]:
    CONTRACT_DIR.mkdir(parents=True, exist_ok=True)
    MOCK_DIR.mkdir(parents=True, exist_ok=True)
    openapi = current_openapi()
    openapi_bytes = canonical_json_bytes(openapi)
    openapi_sha = sha256_bytes(openapi_bytes)
    OPENAPI_PATH.write_bytes(openapi_bytes)
    OPENAPI_SHA_PATH.write_text(f"{openapi_sha}  openapi.json\n", encoding="utf-8")

    matrix = build_contract_matrix(openapi)
    MATRIX_PATH.write_bytes(canonical_json_bytes(matrix))
    matrix_sha = sha256_file(MATRIX_PATH)

    scenarios = build_mock_scenarios()
    mock_hashes: dict[str, str] = {}
    for scenario_id, value in sorted(scenarios.items()):
        validate_mock_fixture(value, openapi)
        path = MOCK_DIR / f"{scenario_id}.json"
        path.write_bytes(canonical_json_bytes(value))
        mock_hashes[path.relative_to(ROOT).as_posix()] = sha256_file(path)

    catalog = {
        "schema_version": MOCK_SCHEMA_VERSION,
        "scenario_count": len(scenarios),
        "scenarios": [
            {
                "scenario_id": scenario_id,
                "category": value["category"],
                "description": value["description"],
                "file": f"mocks/{scenario_id}.json",
            }
            for scenario_id, value in sorted(scenarios.items())
        ],
    }
    MOCK_CATALOG_PATH.write_bytes(canonical_json_bytes(catalog))
    manifest = build_manifest(openapi_sha, mock_hashes, matrix_sha)
    MANIFEST_PATH.write_bytes(canonical_json_bytes(manifest))
    return manifest


def validate_contract_assets() -> dict[str, Any]:
    expected_openapi = canonical_json_bytes(current_openapi())
    if OPENAPI_PATH.read_bytes() != expected_openapi:
        raise ValueError("OpenAPI snapshot drift detected")
    expected_sha = sha256_bytes(expected_openapi)
    recorded_sha = OPENAPI_SHA_PATH.read_text(encoding="utf-8").split()[0]
    if recorded_sha != expected_sha:
        raise ValueError("OpenAPI SHA-256 file does not match snapshot")

    openapi = json.loads(OPENAPI_PATH.read_text(encoding="utf-8"))
    operations = operation_templates(openapi)
    if operations != set(ENDPOINT_UI_METADATA):
        raise ValueError("API matrix metadata does not cover every OpenAPI operation")
    matrix = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
    if matrix != build_contract_matrix(openapi):
        raise ValueError("API contract matrix drift detected")

    fixture_paths = sorted(MOCK_DIR.glob("*.json"))
    for path in fixture_paths:
        validate_mock_fixture(json.loads(path.read_text(encoding="utf-8")), openapi)

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if manifest["openapi"]["sha256"] != expected_sha:
        raise ValueError("manifest OpenAPI hash mismatch")
    if manifest["openapi"]["operation_count"] != len(operations):
        raise ValueError("manifest operation count mismatch")
    for relative_path, expected_hash in manifest["mock_contract"]["files"].items():
        if sha256_file(ROOT / relative_path) != expected_hash:
            raise ValueError(f"mock fixture drift detected: {relative_path}")
    if manifest["api_contract_matrix"]["sha256"] != sha256_file(MATRIX_PATH):
        raise ValueError("contract matrix hash mismatch")
    return {
        "status": "passed",
        "openapi_sha256": expected_sha,
        "operation_count": len(operations),
        "mock_scenario_count": len(fixture_paths),
        "provider_calls": 0,
    }


if __name__ == "__main__":
    write_contract_assets()
    print(json.dumps(validate_contract_assets(), ensure_ascii=False, sort_keys=True))
