# Phase 2.3：测试环境隔离与降级链路安全化实施计划 v0.1

## 1. 实施顺序

### 阶段 A：测试边界

1. 让 `get_settings()` 在 `APP_ENV=test` 时显式禁用 dotenv。
2. 新建根级 `tests/conftest.py`，在普通测试会话导入应用前固定 mock、清空真实 key、关闭真实开关。
3. 为 real smoke 增加显式 marker 与进程环境门禁。
4. 为普通测试会话安装 socket 阻断器并在 pytest 摘要输出尝试次数。

### 阶段 B：来源质量基础设施

1. 新增纯函数模块统一 execution mode 到 source quality 的映射、来源上下文聚合与 fallback 判定。
2. 为 `BaseAgent` 增加策略型 fallback 完成方法，只写 metadata，不新增重试循环。
3. 在 prep package、evaluation 和 acceptance runner 中传递安全来源上下文。

### 阶段 C：fallback 安全化

1. Resume fallback 改为只提取原文可见技能，其他事实字段为空。
2. QuestionBank fallback 改为使用 resume/JD/matching/experience/goal 的上下文模板，保证问题实质唯一和跨技术栈差异。
3. AnswerEvaluator 将 mock 基线输出与 real-failure fallback 输出分开；后者及上游降级均使用 degraded semantics。
4. MemoryAgent 和 MemoryService 同时执行写入门禁，防止 agent 输出或服务层任一路径绕过。

### 阶段 D：数据与 API

1. 扩展评价和 memory Schema，增加条件校验。
2. 扩展 `AnswerEvaluation` 模型并创建 Alembic 迁移。
3. 响应增加模式与质量字段；degraded 的分数返回 null，standard 响应保持原行为。

### 阶段 E：验证

1. 单元测试：配置隔离、来源聚合、三技术栈题库、无事实 Resume、degraded Schema、策略 metadata、memory gate。
2. 集成测试：数据库迁移、API degraded 响应、AgentRun 可观测、memory 不落库。
3. 端到端测试：三个 sample cases 的 mock 闭环；注入可控 fallback 后验证“上游降级 → 无分数评价 → 无长期记忆”。
4. 在 `.env` 存在且未移动的情况下运行离线全量 pytest，核对 0 socket 尝试。

## 2. 拟修改文件

### 配置与测试基础设施

- `app/core/config.py`
- `tests/conftest.py`（新增）
- `pyproject.toml`
- `tests/smoke/test_llm_providers_smoke.py`

### Agent 与来源传播

- `app/agents/base.py`
- `app/agents/source_quality.py`（新增）
- `app/agents/resume_analyzer.py`
- `app/agents/question_bank_agent.py`
- `app/agents/answer_evaluator.py`
- `app/agents/memory_agent.py`
- `app/services/prep_package_service.py`
- `app/services/evaluation_service.py`
- `app/services/memory_service.py`
- `app/services/llm_acceptance_service.py`

### Schema、模型、迁移与 API

- `app/schemas/evaluation.py`
- `app/schemas/memory.py`
- `app/db/models/evaluation.py`
- `app/api/v1/routes/evaluations.py`
- `alembic/versions/c72e3f4a5b6c_add_degraded_evaluation_safety.py`（新增）

### 测试

- 调整受新条件语义影响的现有测试。
- 新增 Phase 2.3 unit、integration、e2e 测试文件。
- 扩展 migration 测试。

### 文档

- `docs/26-phase-2-3-test-isolation-and-fallback-safety-spec-v0.1.md`
- `docs/27-phase-2-3-test-isolation-and-fallback-safety-plan-v0.1.md`
- `docs/28-phase-2-3-test-isolation-and-fallback-safety-tasks-v0.1.md`
- `docs/29-phase-2-3-test-isolation-and-fallback-safety-risk-analysis-v0.1.md`

## 3. 明确不修改

- `app/agents/prompts/*.md`；
- 所有 agent 的 `prompt_version`；
- provider/model 配置和 temperature；
- provider client 的请求实现；
- 前端；
- Phase 2.1 的重试次数和重试所有权。

## 4. 回滚单位

实现按“测试隔离”“来源质量”“fallback 内容”“评价/记忆语义”“迁移/API”分层，避免把 Prompt、模型或 provider 波动混入归因。若迁移或兼容测试失败，先回滚评价持久化层，不通过恢复固定 76 分或允许降级记忆写入来绕过。
