"""Exercise the Phase 2.5C local HTTP contract with synthetic data only."""

from __future__ import annotations

import argparse
from collections import Counter

import httpx


def _data(response: httpx.Response) -> dict:
    response.raise_for_status()
    payload = response.json()
    assert set(payload) == {"data", "message", "request_id"}
    assert payload["request_id"]
    return payload["data"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:18080/api/v1")
    args = parser.parse_args()
    base_url = args.base_url.rstrip("/")
    headers = {"origin": "http://127.0.0.1:14173"}

    with httpx.Client(base_url=base_url, headers=headers, timeout=120) as client:
        resume_document = _data(
            client.post(
                "/documents/text",
                json={
                    "document_type": "resume",
                    "raw_text": (
                        "合成测试简历：三年后端工程经验，使用 Python、FastAPI、"
                        "PostgreSQL，负责接口可靠性和自动化测试。"
                    ),
                },
            )
        )
        job_document = _data(
            client.post(
                "/documents/text",
                json={
                    "document_type": "jd",
                    "raw_text": (
                        "合成测试岗位：负责 Python 后端服务、API 设计、数据库性能、"
                        "可靠性治理和跨团队交付。"
                    ),
                },
            )
        )
        resume = _data(
            client.post(
                "/resumes",
                json={
                    "source_document_id": resume_document["source_document_id"],
                    "title": "合成测试简历",
                    "target_direction": "backend",
                },
            )
        )
        job = _data(
            client.post(
                "/jobs",
                json={
                    "source_document_id": job_document["source_document_id"],
                    "title": "合成测试岗位",
                    "target_direction": "backend",
                },
            )
        )
        _data(client.post(f"/resumes/{resume['resume_id']}/parse"))
        _data(client.post(f"/jobs/{job['job_description_id']}/parse"))
        package = _data(
            client.post(
                "/prep-packages",
                json={
                    "resume_id": resume["resume_id"],
                    "job_description_id": job["job_description_id"],
                    "interview_experience_ids": [],
                    "preparation_goal": "合成后端面试练习",
                    "title": "Phase 2.5C 合成准备包",
                },
            )
        )
        package_detail = _data(
            client.get(f"/prep-packages/{package['prep_package_id']}")
        )
        question_bank = _data(
            client.get(f"/prep-packages/{package['prep_package_id']}/questions")
        )
        counts = Counter(item["module"] for item in question_bank["items"])
        assert package_detail["status"] == "ready"
        assert question_bank["total"] == 25
        assert counts == {
            "self_intro": 8,
            "professional": 8,
            "behavior_project": 9,
        }
        question = question_bank["items"][0]
        evaluation = _data(
            client.post(
                "/evaluations",
                json={
                    "question_db_id": question["question_db_id"],
                    "custom_question_text": None,
                    "user_answer": (
                        "我会先确认接口目标和约束，再用自动化测试验证正常、异常和"
                        "并发路径，并根据监控结果复盘。"
                    ),
                },
            )
        )
        evaluation_detail = _data(
            client.get(f"/evaluations/{evaluation['answer_evaluation_id']}")
        )
        history = _data(client.get("/evaluations"))
        agent_run = _data(client.get(f"/agent-runs/{evaluation['agent_run_id']}"))

        assert evaluation_detail["score_available"] is True
        assert evaluation_detail["total_score"] is not None
        assert history["total"] == 1
        assert agent_run["status"] == "succeeded"
        assert agent_run["provider"] == "mock"
        assert agent_run["real_call_count"] == 0
        assert agent_run["execution_mode"] == "mock"

    print(
        "phase_2_5c_loopback_probe "
        "questions=25 modules=8/8/9 evaluations=1 provider_calls=0"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
