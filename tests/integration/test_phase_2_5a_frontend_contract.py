import hashlib
import json
from pathlib import Path

from app.schemas.evaluation import AnswerEvaluation
from scripts.phase_2_5a_contract import (
    CONTRACT_DIR,
    ENDPOINT_UI_METADATA,
    MANIFEST_PATH,
    MATRIX_PATH,
    MOCK_DIR,
    OPENAPI_PATH,
    OPENAPI_SHA_PATH,
    ROOT,
    build_contract_matrix,
    canonical_json_bytes,
    current_openapi,
    operation_templates,
    validate_contract_assets,
    validate_mock_fixture,
)


EXPECTED_SCENARIOS = {
    "standard-success",
    "upstream-fallback",
    "question-bank-fallback",
    "evaluator-degraded",
    "standard-evaluation",
    "memory-write-blocked",
    "agent-running",
    "retryable-provider-error",
    "nonretryable-contract-error",
    "empty-history",
    "file-upload-failure",
    "request-cancelled-timeout",
}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_openapi_snapshot_is_canonical_repeatable_and_hashed() -> None:
    expected = canonical_json_bytes(current_openapi())

    assert OPENAPI_PATH.read_bytes() == expected
    assert OPENAPI_SHA_PATH.read_text(encoding="utf-8").split()[0] == hashlib.sha256(
        expected
    ).hexdigest()
    assert validate_contract_assets()["operation_count"] == 16


def test_api_matrix_covers_every_openapi_operation() -> None:
    openapi = load_json(OPENAPI_PATH)
    matrix = load_json(MATRIX_PATH)

    assert set(ENDPOINT_UI_METADATA) == operation_templates(openapi)
    assert matrix == build_contract_matrix(openapi)
    assert {
        "/api/v1/health",
        "/api/v1/documents/text",
        "/api/v1/documents/upload",
        "/api/v1/resumes",
        "/api/v1/jobs",
        "/api/v1/experiences",
        "/api/v1/prep-packages",
        "/api/v1/evaluations",
        "/api/v1/agent-runs/{agent_run_id}",
    }.issubset({row["path"] for row in matrix})


def test_versioned_mocks_validate_against_openapi_and_pydantic_contracts() -> None:
    openapi = load_json(OPENAPI_PATH)
    fixtures = {path.stem: load_json(path) for path in MOCK_DIR.glob("*.json")}

    assert set(fixtures) == EXPECTED_SCENARIOS
    for value in fixtures.values():
        validate_mock_fixture(value, openapi)
        assert value["schema_version"] == "frontend-mock-v0.1"
        assert value["data_classification"] == "synthetic_non_personal"


def test_nullable_score_semantics_are_explicit() -> None:
    degraded = load_json(MOCK_DIR / "evaluator-degraded.json")
    standard = load_json(MOCK_DIR / "standard-evaluation.json")
    degraded_data = degraded["steps"][0]["response"]["body"]["data"]
    standard_data = standard["steps"][0]["response"]["body"]["data"]

    degraded_model = AnswerEvaluation.model_validate(degraded_data["evaluation"])
    standard_model = AnswerEvaluation.model_validate(standard_data["evaluation"])
    assert degraded_model.evaluation_mode == "degraded"
    assert degraded_model.score_available is False
    assert degraded_model.total_score is None
    assert degraded_model.dimension_scores == []
    assert standard_model.evaluation_mode == "standard"
    assert standard_model.score_available is True
    assert standard_model.total_score == 80
    assert standard_model.dimension_scores


def test_fallback_and_memory_blocked_states_are_structured() -> None:
    for name in ("upstream-fallback", "question-bank-fallback"):
        fixture = load_json(MOCK_DIR / f"{name}.json")
        run_step = next(
            item
            for item in fixture["steps"]
            if item["response"]
            and "execution_mode" in item["response"]["body"]["data"]
        )
        run = run_step["response"]["body"]["data"]
        assert run["execution_mode"] == "fallback"
        assert run["fallback_reason"]["code"]
        assert run_step["ui"]["state"] == "degraded"
        assert run_step["ui"]["source_quality_display"]["value"] == "degraded"
        assert run_step["ui"]["source_quality_display"]["derived_from"] == "execution_mode"
        assert run_step["ui"]["reason_message"]

    memory = load_json(MOCK_DIR / "memory-write-blocked.json")
    update = memory["steps"][0]["response"]["body"]["data"]["memory_update"]
    assert update["write_decision"] == "skip"
    assert "blocked" in update["skip_reason"]["code"]


def test_question_bank_mock_keeps_final_schema_and_exact_8_8_9_order() -> None:
    fixture = load_json(MOCK_DIR / "standard-success.json")
    questions = fixture["steps"][1]["response"]["body"]["data"]["items"]

    assert len(questions) == 25
    assert [item["module"] for item in questions[:8]] == ["self_intro"] * 8
    assert [item["module"] for item in questions[8:16]] == ["professional"] * 8
    assert [item["module"] for item in questions[16:]] == ["behavior_project"] * 9
    assert [item["sort_order"] for item in questions] == list(range(1, 26))


def test_mocks_have_no_sensitive_markers_or_prompt_v03_assumption() -> None:
    all_mock_text = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(MOCK_DIR.glob("*.json"))
    ).lower()

    for marker in (
        "api_key",
        "authorization: bearer",
        "raw_response",
        "reasoning_content",
        "chain_of_thought",
        "begin private key",
        "question_bank_draft_agent_v0.3",
    ):
        assert marker not in all_mock_text


def test_manifest_preserves_research_and_no_scaffold_boundaries() -> None:
    manifest = load_json(MANIFEST_PATH)

    assert manifest["mode"] == "offline_design_only"
    assert manifest["provider_calls"] == 0
    assert manifest["frontend_scaffold_created"] is False
    assert manifest["npm_dependencies_installed"] is False
    assert manifest["production_question_bank_agent"] == "unchanged"
    assert manifest["prompt_v0_3_status"] == "research_candidate_not_promoted"
    assert manifest["frontend_stack_adr"]["status"] == "awaiting_explicit_user_confirmation"
    assert not (ROOT / "package.json").exists()
    assert CONTRACT_DIR.exists()


def test_frozen_phase_2_4_assets_match_recorded_hashes() -> None:
    protected = load_json(
        ROOT
        / "storage/reports/question-bank-token-phase-2-4d-f-b-offline-20261024"
        / "protected-assets-after.json"
    )

    assert protected["file_count"] == 30
    for relative_path, expected_hash in protected["files"].items():
        path = ROOT / relative_path
        assert path.is_file(), relative_path
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected_hash, relative_path


def test_openapi_response_typing_gap_is_recorded_as_proposal_only() -> None:
    manifest = load_json(MANIFEST_PATH)
    proposals = " ".join(manifest["known_contract_gaps_proposals_only"])

    assert "response_model" in proposals
    assert "ErrorResponse" in proposals
    assert "memory-write" in proposals
