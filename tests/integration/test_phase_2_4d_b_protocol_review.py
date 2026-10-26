import hashlib
import json
from pathlib import Path

from app.services.phase_2_4d_b_protocol_review import (
    DEFAULT_REVIEW_DIR,
    RUN_NAMES,
    build_review,
    verify_protected_assets,
    write_review_artifacts,
)
from app.services.question_draft_token_experiment import (
    PROTOCOL_VERSION as LEGACY_PROTOCOL_VERSION,
)
from app.services.question_draft_token_protocol_v2 import PROTOCOL_VERSION


PROJECT_ROOT = Path(__file__).resolve().parents[2]
REPORT_ROOT = PROJECT_ROOT / "storage/reports"
EXPECTED_EVIDENCE_HASHES = {
    "question-bank-token-phase-2-4d-b-20261022-run1": {
        "manifest.json": "7e3f616658219297e7f97a34da3f4cb6ddb0747ec962f0f43391cd1635849062",
        "question-draft-token-report.json": "787bd9eacc7da70b0b1ffdaf5c5113a8c8b89b60aa87024efccd3e75efbbe4c7",
        "audit/executions.json": "c5a52b596a0e5ecbdbdda317acc412911c3bcf1c20cf57aa51fa42540be70f71",
    },
    "question-bank-token-phase-2-4d-b-20261022-run2": {
        "manifest.json": "57ef4f5112242c17e02b4d32c7bfe4b78556403f0d6e6bc70cd15ceb632587c4",
        "question-draft-token-report.json": "9fcdf09969911f2b6014764904a830f2a6665cb32dc231907da03ddb6cf5acf0",
        "audit/executions.json": "5c78dbf59230b0a2b0fba03e88570e61f58ffb750234e27d379f3e3719f6b0ee",
    },
    "question-bank-token-phase-2-4d-b-20261022-run3": {
        "manifest.json": "9c99e3dedb3473a2faafb5385b61399a43d1fe41b6cbaca499cf33d03a50b2c4",
        "question-draft-token-report.json": "7a2a73265a01424cc0e6b12c5aa04c8677e29927a9f3614fbdf93e1daf9d101a",
        "audit/executions.json": "b6f6d8c3aad721b80782a4f93d2feabb89034900c50d49438200f1c68c1b0be7",
    },
}


def tree_hashes(path):
    return {
        item.relative_to(path).as_posix(): hashlib.sha256(item.read_bytes()).hexdigest()
        for item in path.rglob("*")
        if item.is_file()
    }


def test_offline_review_records_each_run_without_mutating_evidence(tmp_path):
    before = {name: tree_hashes(REPORT_ROOT / name) for name in RUN_NAMES}
    artifacts = write_review_artifacts(tmp_path / "review")
    after = {name: tree_hashes(REPORT_ROOT / name) for name in RUN_NAMES}
    assert after == before
    assert set(artifacts) == {"events", "provider_audit", "protocol", "review"}

    review = json.loads(artifacts["review"].read_text(encoding="utf-8"))
    assert review["network_accessed"] is False
    assert review["run4_created"] is False
    assert review["historical_reports_rewritten"] is False
    assert len(review["events"]) == 3
    by_run = {event["source_run"]: event for event in review["events"]}

    run1 = by_run[RUN_NAMES[0]]
    assert run1["incident_kind"] == "timeout_then_real_success"
    accounting = run1["protocol_v2_accounting_projection"]
    assert accounting["successful_response_usage"]["output_tokens"] == 2528
    assert accounting["billing_usage_completeness"]["status"] == "incomplete"
    assert accounting["known_token_lower_bound"]["total_tokens"] == 3565
    assert accounting["execution_reliability"]["timeout_attempts"] == 1

    run2 = by_run[RUN_NAMES[1]]
    assert run2["incident_kind"] == "manifest_model_label_misconfiguration"
    assert run2["protocol_v2_accounting_projection"]["provider_call_budget"]["used"] == 0
    assert run2["prompt_v0_2_token_ab_eligibility"] == "excluded"

    run3 = by_run[RUN_NAMES[2]]
    assert run3["incident_kind"] == "network_failures_then_fallback"
    assert run3["protocol_v2_accounting_projection"]["known_token_lower_bound"]["total_tokens"] is None
    assert run3["protocol_v2_accounting_projection"]["execution_reliability"]["network_error_attempts"] == 2
    assert run3["fallback_content_used_for_evaluation"] is False


def test_provider_audit_is_bounded_and_does_not_claim_root_cause():
    audit = build_review()["provider_client_audit"]
    assert audit["timeout_layers"]["provider_request_seconds"] == 60
    assert audit["timeout_layers"]["variant_deadline_seconds"] == 120
    assert audit["retry_ownership"]["owner"] == "BaseAgent.run_with_fallback"
    assert audit["remote_protocol_error"]["classification"] == "network"
    assert audit["remote_protocol_error"]["classification_only_not_root_cause"] is True
    assert audit["http_connection_pool_lifecycle"]["cross_attempt_pool_reuse_on_default_path"] is False
    assert audit["root_cause_conclusion"] == "insufficient_evidence"
    assert audit["max_tokens"]["request_field_present"] is False
    encoded = json.dumps(audit).lower()
    assert "bearer " not in encoded
    assert "raw_response" not in encoded


def test_old_protocol_and_original_reports_remain_byte_identical():
    assert LEGACY_PROTOCOL_VERSION == "phase-2.4d-question-draft-prompt-token-v1"
    assert PROTOCOL_VERSION == "phase-2.4d-question-draft-prompt-token-v2"
    for run_name, files in EXPECTED_EVIDENCE_HASHES.items():
        for relative, expected in files.items():
            actual = hashlib.sha256((REPORT_ROOT / run_name / relative).read_bytes()).hexdigest()
            assert actual == expected
        manifest = json.loads((REPORT_ROOT / run_name / "manifest.json").read_text(encoding="utf-8"))
        assert manifest["protocol_version"] == LEGACY_PROTOCOL_VERSION


def test_all_frozen_assets_match_preimplementation_hash_baseline():
    result = verify_protected_assets(DEFAULT_REVIEW_DIR / "protected-assets-before.json")
    assert result["status"] == "passed"
    assert result["checked_file_count"] == 110
    assert result["missing"] == []
    assert result["changed"] == []
