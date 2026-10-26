import json
from pathlib import Path

import pytest

from app.agents.mock_client import MockLLMClient
from app.agents.prompt_loader import load_prompt
from app.agents.question_bank_agent import QuestionBankAgent
from app.schemas.question import QuestionBank


SAMPLE_CASE_DIR = Path(__file__).parents[1] / "fixtures" / "sample_cases"


def test_question_bank_prompt_v01_is_preserved_as_baseline() -> None:
    baseline = load_prompt("question_bank_agent", "v0.1")

    assert baseline.path.name == "question_bank_agent_v0.1.md"
    assert baseline.content


def test_question_bank_v02_candidate_contract_is_preserved() -> None:
    agent = QuestionBankAgent(llm_client=MockLLMClient())
    prompt = load_prompt("question_bank_agent", "v0.2")

    assert agent.prompt_version == "question_bank_agent_v0.1"
    assert "只生成 25 道题" in prompt.content
    assert "self_intro_questions` 恰好 8 道" in prompt.content
    assert "professional_questions` 恰好 8 道" in prompt.content
    assert "behavior_project_questions` 恰好 9 道" in prompt.content
    assert "不得仅在同一个问题末尾添加序号" in prompt.content
    assert "Go 或 Java 岗位材料没有出现 FastAPI" in prompt.content
    assert "不要输出分析过程" in prompt.content


def test_question_bank_schema_quality_constraints_remain_strict() -> None:
    schema = QuestionBank.model_json_schema()
    properties = schema["properties"]

    assert properties["self_intro_questions"]["minItems"] == 8
    assert properties["professional_questions"]["minItems"] == 8
    assert properties["behavior_project_questions"]["minItems"] == 8
    assert properties["total_count"]["minimum"] == 25


@pytest.mark.parametrize(
    ("case_filename", "required_stack", "unrelated_stack"),
    [
        ("backend_go_case.json", "Go", "FastAPI"),
        ("backend_java_case.json", "Java", "FastAPI"),
        ("backend_python_case.json", "FastAPI", "Spring Boot"),
    ],
)
def test_v02_request_keeps_each_regression_case_stack_visible(
    case_filename: str,
    required_stack: str,
    unrelated_stack: str,
) -> None:
    case_data = json.loads((SAMPLE_CASE_DIR / case_filename).read_text(encoding="utf-8"))

    class CandidateV02QuestionBankAgent(QuestionBankAgent):
        prompt_version = "question_bank_agent_v0.2"

    agent = CandidateV02QuestionBankAgent(llm_client=MockLLMClient())

    request = agent._build_request(
        {
            "resume_profile": {"source_summary": case_data["resume_text"]},
            "jd_profile": {"source_summary": case_data["jd_text"]},
            "experience_profiles": [{"source_summary": case_data["experience_text"]}],
            "match_report": {"summary": "regression case"},
            "preparation_goal": case_data["preparation_goal"],
        },
        QuestionBank,
    )

    assert required_stack in request.user_prompt
    assert unrelated_stack not in request.user_prompt
    assert "不得引入简历、JD、面经和准备目标均未出现的框架或语言" in request.system_prompt
    assert '"minItems": 8' in request.system_prompt
    assert '"minimum": 25' in request.system_prompt
