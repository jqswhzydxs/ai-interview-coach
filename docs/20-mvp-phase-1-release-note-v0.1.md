# MVP Phase 1 Release Note: 面试问题生成与单题评价 v0.1

发布日期：2026-10-14

对应任务清单：

1. `docs/17-mvp-question-generation-and-answer-evaluation-spec-v0.1.md`
2. `docs/18-mvp-question-generation-and-answer-evaluation-plan-v0.1.md`
3. `docs/19-mvp-question-generation-and-answer-evaluation-tasks-v0.1.md`

## 1. 发布摘要

MVP Phase 1 已完成后端闭环：

```text
输入简历 + JD + 准备目标
-> 解析简历/JD
-> 生成岗位相关面试题库
-> 提交单题答案
-> 获得结构化评价、改进建议、追问和记忆更新
```

当前版本使用 mock/stub Agent 打通完整流程，未新增自动联网搜索、登录注册、正式前端、实时语音、PDF 导出、真实面试复盘、质量评测后台等非目标功能。

## 2. 已交付能力

### 2.1 后端基础设施

已完成 FastAPI 后端项目结构、`uv + pyproject.toml` 依赖管理、Python 3.11 运行环境约束、配置读取、基础日志、request_id 中间件、统一响应结构、统一错误模型、分页参数和健康检查接口。

关键实现：

1. `app/main.py`
2. `app/core/config.py`
3. `app/core/logging.py`
4. `app/core/middleware.py`
5. `app/core/errors.py`
6. `app/api/v1/routes/health.py`
7. `app/schemas/response.py`
8. `app/schemas/pagination.py`

### 2.2 数据库、迁移和默认用户

已完成 SQLAlchemy 连接、FastAPI DB dependency、Alembic 配置、MVP ORM 模型、初始迁移和默认用户初始化。

已实现表覆盖：

1. `users`
2. `source_documents`
3. `resumes`
4. `resume_profiles`
5. `job_descriptions`
6. `jd_profiles`
7. `interview_experiences`
8. `experience_profiles`
9. `interview_prep_packages`
10. `prep_package_experiences`
11. `match_reports`
12. `interview_questions`
13. `recommended_questions`
14. `answer_evaluations`
15. `memory_items`
16. `agent_runs`
17. `agent_run_steps`

确认未实现非目标表：

1. `interview_reviews`
2. `quality_evaluations`

关键实现：

1. `app/db/models/*.py`
2. `app/db/init_db.py`
3. `alembic/versions/9c8951c88817_initial_mvp_schema.py`

### 2.3 Schema 和输入处理工具

已完成通用 Schema、Profile Schema、题库与备战包 Schema、单题评价与记忆 Schema、Agent run/step 响应 Schema。

已完成文本 hash、手机号/邮箱脱敏、TXT/Markdown/DOCX/PDF 文件解析、5MB 文件大小限制和不支持类型错误处理。

关键实现：

1. `app/schemas/common.py`
2. `app/schemas/resume.py`
3. `app/schemas/job_description.py`
4. `app/schemas/experience.py`
5. `app/schemas/question.py`
6. `app/schemas/prep_package.py`
7. `app/schemas/evaluation.py`
8. `app/schemas/memory.py`
9. `app/schemas/agent.py`
10. `app/tools/text_utils.py`
11. `app/tools/file_parser.py`

### 2.4 Agent 基础设施和 Prompt

已完成 Agent 基类、LLMClient 抽象、MockLLMClient、DeepSeek/Kimi Provider 骨架、Prompt 文件加载器、Harness、Agent run/step 日志、Schema 校验失败重试一次、失败状态记录。

关键实现：

1. `app/agents/base.py`
2. `app/agents/llm_client.py`
3. `app/agents/mock_client.py`
4. `app/agents/deepseek_client.py`
5. `app/agents/kimi_client.py`
6. `app/agents/harness.py`
7. `app/agents/prompt_loader.py`
8. `app/agents/prompts/*.md`
9. `app/services/agent_run_service.py`

### 2.5 材料、简历、JD 和面经

已完成材料保存接口、文件上传接口、简历创建与解析、JD 创建与解析、可选面经创建与解析。

关键 API：

1. `POST /api/v1/documents/text`
2. `POST /api/v1/documents/upload`
3. `POST /api/v1/resumes`
4. `POST /api/v1/resumes/{resume_id}/parse`
5. `POST /api/v1/jobs`
6. `POST /api/v1/jobs/{job_description_id}/parse`
7. `POST /api/v1/experiences`
8. `POST /api/v1/experiences/{interview_experience_id}/parse`

关键实现：

1. `app/api/v1/routes/documents.py`
2. `app/api/v1/routes/resumes.py`
3. `app/api/v1/routes/jobs.py`
4. `app/api/v1/routes/experiences.py`
5. `app/services/document_service.py`
6. `app/services/resume_service.py`
7. `app/services/job_service.py`
8. `app/services/experience_service.py`
9. `app/agents/resume_analyzer.py`
10. `app/agents/jd_analyzer.py`
11. `app/agents/experience_analyzer.py`

### 2.6 问题生成和题库查询

已完成 Matching Agent mock、Question Bank Agent mock、备战包生成服务、匹配报告保存、题库保存、推荐题保存、备战包详情查询和题库查询过滤。

当前题库约束：

1. 总题量不少于 25 道。
2. 自我介绍定制题不少于 8 道。
3. 后端岗位专业能力题不少于 8 道。
4. 行为经历与项目深挖题不少于 8 道。
5. 推荐先练题数量为 3 道。
6. 24 道题样例会被 Schema 校验拒绝。

关键 API：

1. `POST /api/v1/prep-packages`
2. `GET /api/v1/prep-packages/{prep_package_id}`
3. `GET /api/v1/prep-packages/{prep_package_id}/questions`

关键实现：

1. `app/agents/matching_agent.py`
2. `app/agents/question_bank_agent.py`
3. `app/services/prep_package_service.py`
4. `app/services/question_service.py`
5. `app/api/v1/routes/prep_packages.py`

### 2.7 单题评价、记忆和日志查询

已完成 Answer Evaluator mock、Memory Agent mock、题库题目评分、自定义题目评分、评分详情查询、评分历史分页查询、高置信度记忆写入、低置信度记忆仅保留在评价记录中、Agent run 查询。

当前评价约束：

1. 总分范围为 0 到 100。
2. 分项评分不超过对应满分。
3. 至少包含 1 条改进建议。
4. 至少包含 1 个追问。
5. 返回改进版回答和下一题建议。

关键 API：

1. `POST /api/v1/evaluations`
2. `GET /api/v1/evaluations/{answer_evaluation_id}`
3. `GET /api/v1/evaluations`
4. `GET /api/v1/agent-runs/{agent_run_id}`

关键实现：

1. `app/agents/answer_evaluator.py`
2. `app/agents/memory_agent.py`
3. `app/services/evaluation_service.py`
4. `app/services/memory_service.py`
5. `app/api/v1/routes/evaluations.py`
6. `app/api/v1/routes/agent_runs.py`

## 3. 验证结果

本次核对基于当前代码直接运行测试得到以下结果：

| 测试命令 | 结果 |
| --- | --- |
| `.\\.venv\\Scripts\\python.exe -m pytest tests\\unit` | 65 passed |
| `.\\.venv\\Scripts\\python.exe -m pytest tests\\integration` | 34 passed, 1 warning |
| `.\\.venv\\Scripts\\python.exe -m pytest tests\\e2e` | 1 passed, 1 warning |

合计：100 个测试通过。

已知 warning：

1. integration/e2e 测试中出现 `StarletteDeprecationWarning: Using httpx with starlette.testclient is deprecated; install httpx2 instead.`。
2. 该 warning 不影响当前测试通过结果，但后续升级依赖时需要关注 TestClient/httpx 兼容性。

## 4. docs/19 任务实现与测试对应检查

| 任务 | 实现对应 | 测试对应 | 结论 |
| --- | --- | --- | --- |
| T001 初始化后端项目结构 | `pyproject.toml`、基础目录、包初始化文件 | 项目可导入，全部测试可运行 | 已覆盖 |
| T002 配置、日志、request_id、健康检查 | `app/core/*`、`app/main.py`、health route | `tests/integration/test_health.py` | 已覆盖 |
| T003 统一响应、错误模型、分页 | response/pagination/errors | `test_response_schemas.py`、`test_error_response.py` | 已覆盖 |
| T004 hash、脱敏、文件解析 | `text_utils.py`、`file_parser.py` | `test_text_utils.py`、`test_file_parser.py` | 功能和测试已覆盖；固定 fixture 文件未落库，测试中动态生成样例文件 |
| T005 DB 连接和 Alembic | `app/db/base.py`、`session.py`、`deps.py`、Alembic 配置 | `test_db_config.py`、迁移测试间接覆盖 | 已覆盖 |
| T006 MVP ORM 模型 | `app/db/models/*.py` | `test_models_metadata.py` | 已覆盖 |
| T007 初始迁移和默认用户 | 初始 migration、`init_db.py`、lifespan 初始化 | `test_migrations.py`、`test_default_user.py` | 已覆盖 |
| T008 通用 Schema | `app/schemas/common.py` | `test_common_schemas.py` | 已覆盖 |
| T009 Profile Schema | resume/job/experience schemas | `test_profile_schemas.py` | 已覆盖 |
| T010 题库与备战包 Schema | question/prep_package schemas | `test_question_bank_schemas.py`、`test_prep_package_schemas.py` | 已覆盖 |
| T011 单题评价与记忆 Schema | evaluation/memory/agent schemas | `test_evaluation_schemas.py`、`test_memory_schemas.py` | 已覆盖 |
| T012 Agent 基础设施和 mock LLMClient | base/llm/mock/deepseek/kimi clients | `test_llm_client.py` | 已覆盖 |
| T013 Harness 和 Agent 运行日志 | `harness.py`、`agent_run_service.py` | `test_harness.py` | 已覆盖 |
| T014 Prompt 文件与加载器 | prompt loader、7 个 prompt 文件 | `test_prompt_loader.py` | 已覆盖 |
| T015 材料保存接口 | documents route/service | `test_documents_api.py` | 已覆盖 |
| T016 简历创建与解析 | resumes route/service/agent | `test_resumes_api.py` | 已覆盖 |
| T017 JD 创建与解析 | jobs route/service/agent | `test_jobs_api.py` | 已覆盖 |
| T018 面经创建与解析 | experiences route/service/agent | `test_experiences_api.py` | 已覆盖 |
| T019 问题生成 Agent mocks | matching/question_bank agents | `test_question_generation_agents.py` | 已覆盖 |
| T020 备战包生成服务与 API | prep package service/route | `test_prep_packages_api.py` | 已覆盖 |
| T021 题库查询 API | question service、prep package route | `test_questions_api.py` | 已覆盖 |
| T022 单题评价 Agent mocks | answer evaluator、memory agent | `test_answer_evaluation_agents.py` | 已覆盖 |
| T023 单题评价服务与 API | evaluation service/route | `test_evaluations_api.py` | 已覆盖 |
| T024 记忆写入策略 | memory service | `test_memory_service.py`、`test_evaluations_api.py` | 已覆盖 |
| T025 Agent 运行日志查询 API | agent_runs route/service | `test_agent_runs_api.py`、e2e 测试 | 已覆盖 |
| T026 固定样例与测试套件 | 3 组 sample case JSON、Schema/API 主路径测试 | `test_schema_constraints.py`、`test_mvp_api_flow.py` | 已覆盖 |
| T027 端到端验收测试 | 完整 mock Agent 闭环 | `test_question_generation_and_evaluation_flow.py` | 已覆盖 |

结论：T001 到 T027 均有当前实现和测试对应。唯一需要记录的差异是 T004 文档列出的 `tests/fixtures/files/sample_resume.txt/md/docx/pdf` 当前不存在，文件解析测试通过 `tmp_path` 动态生成四类样例文件完成覆盖。

## 5. 非目标确认

当前代码和测试未引入以下非目标能力：

1. 自动联网搜索。
2. 登录注册。
3. 正式前端。
4. 实时语音。
5. PDF 报告导出。
6. 真实面试复盘主线。
7. 质量评测后台。
8. `interview_reviews` 表。
9. `quality_evaluations` 表。

## 6. 发布判定

MVP Phase 1 满足发布条件：

1. 后端基础设施可运行。
2. 数据库迁移和默认用户初始化通过测试。
3. mock Agent 可跑通完整闭环。
4. 题库生成、查询、推荐题、单题评价、记忆写入、Agent run 查询均有测试覆盖。
5. unit、integration、e2e 测试全部通过。

发布状态：可发布为 MVP Phase 1 v0.1。
