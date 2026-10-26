"""Offline Phase 2.4C replay and blinded artifact preparation; no provider route."""

from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import secrets
import sys
from uuid import uuid4

from app.agents.question_bank_agent import QuestionBankAgent
from app.agents.question_bank_assembler import QuestionBankAssembler
from app.agents.question_bank_metadata_v2 import (
    QuestionBankMetadataAssemblerV2, collect_evidence, mentioned_technologies,
    question_intent,
)
from app.agents.question_metadata_rules import topics_for
from app.schemas.question import QuestionBank
from app.schemas.question_draft import QuestionDraftBank


class ReplaySafetyError(RuntimeError):
    pass


class _NoProvider:
    provider = "mock"
    model_name = "offline-metadata-only"
    calls = 0

    async def generate_json(self, request):
        self.calls += 1
        raise ReplaySafetyError("Metadata replay must never request model generation")


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tree_hashes(root: Path) -> dict[str, str]:
    return {p.relative_to(root).as_posix(): file_sha256(p) for p in sorted(root.rglob("*")) if p.is_file()}


@contextmanager
def offline_readonly_guard(source: Path):
    source = source.resolve()
    state = {"active": True, "network_attempts": 0, "source_write_attempts": 0}

    def in_source(path):
        if not isinstance(path, (str, bytes, Path)):
            return False
        try:
            return Path(path).resolve().is_relative_to(source)
        except (OSError, ValueError, TypeError):
            return False

    def audit(event, args):
        if not state["active"]:
            return
        if event in {"socket.connect", "socket.getaddrinfo", "http.client.connect", "subprocess.Popen", "os.system"}:
            state["network_attempts"] += 1
            raise ReplaySafetyError("Offline replay forbids network and subprocesses")
        changed = []
        if event == "open":
            mode, flags = args[1], args[2]
            if (mode and any(x in mode for x in "wax+")) or (flags and flags & 3):
                changed = [args[0]]
        elif event in {"os.remove", "os.rmdir", "os.mkdir", "os.chmod", "os.utime"}:
            changed = [args[0]]
        elif event in {"os.rename", "os.replace"}:
            changed = [args[0], args[1]]
        if any(in_source(path) for path in changed):
            state["source_write_attempts"] += 1
            raise ReplaySafetyError("The original experiment directory is read-only")

    sys.addaudithook(audit)
    try:
        yield state
    finally:
        state["active"] = False


def _read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def _flat(bank):
    return [q for key in ("self_intro_questions", "professional_questions", "behavior_project_questions") for q in bank[key]]


def _draft(submission):
    groups = {"self_intro_questions": [], "professional_questions": [], "behavior_project_questions": []}
    for position, question in enumerate(submission["questions"], 1):
        if question["position"] != position:
            raise ReplaySafetyError("Replay questions must retain their original positions")
        groups[f"{question['module']}_questions"].append({"question_text": question["question_text"]})
    draft = QuestionDraftBank.model_validate(groups)
    preserved = [q.question_text for group in (draft.self_intro_questions, draft.professional_questions, draft.behavior_project_questions) for q in group]
    if preserved != [q["question_text"] for q in submission["questions"]]:
        raise ReplaySafetyError("Draft normalization would change frozen question text")
    return draft


def _curated_questions(bank):
    fields = ("module", "question_text", "purpose", "difficulty", "source_type", "source_refs", "jd_keywords", "answer_framework", "star_template", "scoring_anchors", "follow_up_questions", "preparation_advice")
    return [{"position": index, **{key: q[key] for key in fields}, "source_summaries": [ref["summary"] for ref in q["source_refs"]]} for index, q in enumerate(_flat(bank), 1)]


def validate_evidence_quotes(bank, input_data):
    documented = {(item.source_type, item.path, item.value): item for item in collect_evidence(input_data)}
    texts = {q["question_text"] for q in _flat(bank)}
    for question in _flat(bank):
        for ref in question["source_refs"]:
            if ref["source_type"] == "inferred" and ref.get("quote") in texts and ref["summary"].startswith("Question-derived"):
                continue
            matches = [item for (source, path, value), item in documented.items() if source == ref["source_type"] and value == ref.get("quote") and path in ref["summary"]]
            if not matches:
                raise ReplaySafetyError("Metadata citation is not traceable to a whitelisted input field")
            if any(item.kind in {"gap", "priority", "assessment"} and ref["source_type"] != "inferred" for item in matches):
                raise ReplaySafetyError("Matching assessment was promoted to factual experience")


def run_metadata_replay(*, source_dir: Path, output_dir: Path, input_file: Path, holdout_file: Path) -> dict:
    source_dir, output_dir = source_dir.resolve(), output_dir.resolve()
    if output_dir.is_relative_to(source_dir) or source_dir.is_relative_to(output_dir):
        raise ReplaySafetyError("Replay output must be separate from the original experiment")
    if (output_dir / "blind-review/metadata-review-packet.json").exists():
        raise ReplaySafetyError("An existing blind packet cannot be silently regenerated")
    before = tree_hashes(source_dir)
    with offline_readonly_guard(source_dir) as guard:
        report = _read(source_dir / "question-bank-ab-report.json")
        questions = _read(source_dir / "blind-question-review-packet.json")
        original_metadata = _read(source_dir / "blind-metadata-review-packet.json")
        inputs = _read(input_file)
        holdout = _read(holdout_file)
        if file_sha256(input_file) != report["input_sha256"]:
            raise ReplaySafetyError("Frozen input does not match the experiment")
        question_map = {s["submission_id"]: s for s in questions["submissions"]}
        old_meta = {s["submission_id"]: s for s in original_metadata["submissions"]}
        input_map = {case["case_id"]: case["input"] for case in inputs["cases"]}
        runs = [run for run in report["runs"] if run["variant"] == "candidate"]
        if len(runs) != 15 or any(run["execution_mode"] != "real" for run in runs):
            raise ReplaySafetyError("Expected the 15 real Candidate executions")
        records = []
        for index, run in enumerate(runs, 1):
            submission = question_map[run["submission_id"]]
            records.append({
                "corpus_id": f"replay-{index:02d}", "partition": "frozen_run2",
                "case_id": run["case_id"], "source_submission_id": run["submission_id"],
                "draft": _draft(submission).model_dump(mode="json"), "input": input_map[run["case_id"]],
            })
        for case in holdout["cases"]:
            records.append({"corpus_id": case["case_id"], "case_id": case["case_id"], "partition": "authored_holdout", "source_submission_id": None, "draft": case["draft"], "input": case["input"]})
        provider = _NoProvider()
        assemblers = {"v1": QuestionBankAssembler(QuestionBankAgent(provider)), "v2": QuestionBankMetadataAssemblerV2()}
        comparisons, private_map, blind_submissions, banks = [], [], [], []
        for record in records:
            draft = QuestionDraftBank.model_validate(record["draft"])
            original_texts = [q["question_text"] for key in ("self_intro_questions", "professional_questions", "behavior_project_questions") for q in record["draft"][key]]
            evidence_context = [{"source_type": item.source_type, "field_path": item.path, "quote": item.value, "kind": item.kind} for item in collect_evidence(record["input"])]
            allowed = set().union(*(mentioned_technologies(item.value) for item in collect_evidence(record["input"]) if item.source_type in {"resume", "jd"}))
            for version, assembler in assemblers.items():
                bank = assembler.assemble(draft, record["input"])
                repeated = assembler.assemble(draft, record["input"])
                if bank != repeated:
                    raise ReplaySafetyError("Assembler replay is not deterministic")
                parsed = QuestionBank.model_validate(bank)
                QuestionBankAssembler._validate_final_bank(parsed)
                QuestionBankMetadataAssemblerV2.validate_output_boundary(parsed, allowed)
                flat = _flat(bank)
                if [q["question_text"] for q in flat] != original_texts:
                    raise ReplaySafetyError("Assembler changed a frozen question")
                if version == "v2":
                    validate_evidence_quotes(bank, record["input"])
                if version == "v1" and record["source_submission_id"]:
                    old = old_meta[record["source_submission_id"]]["questions"]
                    curated = _curated_questions(bank)
                    if any(any(new[key] != prior[key] for key in prior) for new, prior in zip(curated, old)):
                        raise ReplaySafetyError("Replayed v1 differs from the historical metadata")
                opaque_id = "metadata-" + uuid4().hex
                private_map.append({"submission_id": opaque_id, "version": version, "corpus_id": record["corpus_id"], "partition": record["partition"]})
                blind_submissions.append({"submission_id": opaque_id, "evidence_context": evidence_context, "questions": _curated_questions(bank)})
                banks.append({"corpus_id": record["corpus_id"], "version": version, "bank": bank})
                comparisons.append({
                    "corpus_id": record["corpus_id"], "partition": record["partition"], "version": version,
                    "schema": "passed", "strict_count": "passed", "duplicate": "passed", "stack_boundary": "passed", "question_text_preserved": True,
                    "deterministic": True, "evidence_quotes_verified": version == "v2",
                    "bank_sha256": hashlib.sha256(json.dumps(bank, sort_keys=True, ensure_ascii=False).encode()).hexdigest(),
                    "field_unique_counts": {key: len({json.dumps(q[key], sort_keys=True, ensure_ascii=False) for q in flat}) for key in ("purpose", "answer_framework", "scoring_anchors", "follow_up_questions", "preparation_advice")},
                    "intent_counts": {intent: sum(question_intent(q["question_text"], q["module"]) == intent for q in flat) for intent in sorted({question_intent(q["question_text"], q["module"]) for q in flat})},
                    "unclassified_topic_positions": [i for i, q in enumerate(flat, 1) if not topics_for(q["question_text"])],
                })
        secrets.SystemRandom().shuffle(blind_submissions)
        packet = {
            "packet_version": "phase-2.4c-independent-metadata-review-v1",
            "blinding": "Opaque IDs and shuffled order. No version labels or mapping. Evaluate each question against its curated evidence context; do not infer identity.",
            "submissions": blind_submissions,
        }
        template = {
            "review_version": "phase-2.4c-independent-metadata-review-v1",
            "scale": "1-5", "evaluator": {"type": None, "identifier": None, "independence_confirmed": None},
            "instructions": "Score purpose, source, framework, anchors, follow-up and advice fit per question. Exactly 25 metadata_fit_scores per submission. Do not read private audit/mapping, implementation, comparison reports or historical scores. Do not reuse old scores. Record evaluator type explicitly; AI ratings are not human ratings.",
            "submissions": [{"submission_id": s["submission_id"], "metadata_fit_scores": [None] * 25, "field_notes": {key: "" for key in ("purpose", "source", "framework", "anchors", "follow_up", "advice")}} for s in blind_submissions],
        }
        if provider.calls or guard["network_attempts"]:
            raise ReplaySafetyError("Offline replay attempted generation or networking")
        after = tree_hashes(source_dir)
        if before != after:
            raise ReplaySafetyError("Original experiment changed during replay")
        summary = {
            "phase": "2.4C", "status": "awaiting_independent_metadata_review",
            "source_files_unchanged": before == after, "source_hashes": before,
            "input_sha256": file_sha256(input_file), "holdout_sha256": file_sha256(holdout_file),
            "frozen_candidate_banks": 15, "frozen_candidate_questions": 375,
            "authored_holdout_banks": len(holdout["cases"]), "authored_holdout_questions": len(holdout["cases"]) * 25,
            "comparison_banks": len(comparisons), "blind_submission_count": len(blind_submissions),
            "provider_calls": provider.calls, "network_attempts": guard["network_attempts"],
            "source_write_attempts": guard["source_write_attempts"],
            "implementation_hashes": {p.as_posix(): file_sha256(p) for p in (
                Path("app/agents/question_bank_assembler.py"), Path("app/agents/question_bank_metadata_v2.py"), Path("app/agents/question_metadata_rules.py"), Path(__file__),
            )},
            "new_metadata_fit": None, "historical_scores_used_for_new_acceptance": False,
            "production_default_changed": False, "quality_gate": "pending_new_independent_blind_review",
            "limitations": ["Engineering checks do not prove arbitrary natural-language semantic correctness.", "Authored holdout is separate from run2, but is visible to the implementation author.", "Metadata language is English; Chinese questions and source facts are preserved and matched.", "Knowledge rules are finite; unclassified topics use conservative question-scoped guidance.", "Content style may suggest identity even though labels and maps are removed."],
            "comparisons": comparisons,
        }
        _write(output_dir / "audit/frozen-replay-corpus.json", {
            "corpus_version": "phase-2.4c-frozen-run2-and-authored-holdout-v1",
            "source_hashes": before,
            "records": [{key: value for key, value in record.items() if key != "input"} for record in records],
        })
        _write(output_dir / "audit/private-blinding-map.json", {"do_not_distribute_to_reviewers": True, "mapping": private_map})
        _write(output_dir / "audit/replayed-question-banks.json", {"banks": banks})
        _write(output_dir / "offline-replay-report.json", summary)
        _write(output_dir / "blind-review/metadata-review-packet.json", packet)
        _write(output_dir / "blind-review/metadata-review-template.json", template)
        (output_dir / "blind-review/REVIEW-INSTRUCTIONS.md").write_text(
            "# Independent metadata review\n\nRead only metadata-review-packet.json and metadata-review-template.json in this directory.\n"
            "Do not inspect the parent reports, audit directory, mapping, source code or historical grades.\n"
            "Fill 25 scores per submission (1–5), preserve IDs/order, and record evaluator type explicitly.\n"
            "AI evaluation must be labeled AI, never human. Do not infer implementation identity.\n"
            "Return a separate metadata-review-completed.json; do not modify either input.\n", encoding="utf-8",
        )
        if tree_hashes(source_dir) != before:
            raise ReplaySafetyError("Original experiment changed during artifact generation")
        return summary
