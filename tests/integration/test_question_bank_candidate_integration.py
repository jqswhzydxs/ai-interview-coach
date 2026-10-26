import json
from pathlib import Path
import sys

import pytest

from app.agents.mock_client import MockLLMClient
from app.agents.question_bank_candidate_agent import candidate_asset_hashes
from app.services.question_bank_candidate_validation import (
    REVIEW, RUN2, validate_candidate_integration,
)
from app.services.question_bank_metadata_replay import ReplaySafetyError, offline_readonly_guard


def test_frozen_replay_holdout_versions_and_audit_records(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Candidate offline validation must not generate")

    monkeypatch.setattr(MockLLMClient, "generate_json", forbidden)
    out = tmp_path / "candidate-integration"
    report = validate_candidate_integration(output_dir=out)
    assert report["status"] == "passed"
    assert report["replay_banks"] == 15 and report["holdout_banks"] == 4
    assert report["questions_per_version"] == 475
    assert report["assembly_executions"] == 76
    assert report["provider_calls"] == report["network_attempts"] == report["protected_write_attempts"] == 0
    assert report["protected_inputs_unchanged"] is True
    assert len(report["comparisons"]) == 38
    assert all(r["frozen_bank_equal"] and r["deterministic"] and r["identity_equal"] for r in report["comparisons"])
    runs = json.loads((out / "candidate-run-records.json").read_text(encoding="utf-8"))["runs"]
    assert len(runs) == 38
    for run in runs:
        assert run["metadata_assembler_version"] == "deterministic-metadata-" + run["selected_metadata_version"]
        assert run["asset_sha256"] == candidate_asset_hashes()
        assert run["metadata_applied"] is True
        assert run["execution_mode"] == "offline_replay"
        assert run["provider_call_count"] == 0
        assert len(run["draft_sha256"]) == 64
    with pytest.raises(ReplaySafetyError, match="already exist"):
        validate_candidate_integration(output_dir=out)


@pytest.mark.parametrize("protected", [RUN2, REVIEW, RUN2 / "integration", REVIEW / "integration"])
def test_protected_experiment_is_not_a_valid_output_destination(protected):
    with pytest.raises(ReplaySafetyError, match="protected"):
        validate_candidate_integration(output_dir=protected)


def test_socket_guard_and_readonly_guard_block_synthetic_attempts(tmp_path):
    path = tmp_path / "protected.txt"
    path.write_text("frozen", encoding="utf-8")
    with offline_readonly_guard(tmp_path) as guard:
        with pytest.raises(ReplaySafetyError, match="network"):
            sys.audit("socket.connect", None, ("offline.invalid", 443))
        with pytest.raises(ReplaySafetyError, match="read-only"):
            path.write_text("invalid", encoding="utf-8")
        assert guard["network_attempts"] == guard["source_write_attempts"] == 1
    assert path.read_text(encoding="utf-8") == "frozen"
