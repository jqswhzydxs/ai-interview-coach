# Phase 2.4A：QuestionBank 最小草稿协议实施计划 v0.1

## 1. 实施顺序

### A. 内部协议

1. 在独立 Schema 文件定义 `QuestionDraft` 与严格 8/8/9 的 `QuestionDraftBank`。
2. 增加规范化文本函数和最小契约复杂度测试。

### B. 确定性 assembler

1. 复用基线 Agent 的 Phase 2.3 上下文提取和元数据模板。
2. 将三组草稿映射为固定 module、ID、sort order。
3. 验证规范化唯一性、近重复、技术边界、来源和最终 Schema。
4. assembler 只返回最终 `QuestionBank` JSON，不持久化中间草稿。

### C. 独立候选 Agent

1. 新增 `QuestionBankDraftAgent` 和独立 prompt 文件。
2. 扩展 BaseAgent 的现有单一重试循环，允许在成功响应验证后执行 transform。
3. transform 异常归类为 schema failure；fallback factory 直接复用 Phase 2.3 安全 QuestionBank。
4. 不替换任何运行时 `QuestionBankAgent` 引用。

### D. acceptance runner 注入

1. 构造函数增加可选 `question_bank_agent_factory`。
2. 默认值为当前基线类。
3. 候选测试显式传入 factory，不修改模块全局状态。

### E. 离线验证

1. Unit：Draft Schema、assembler 规则、三技术栈、重复/串栈/证据失败。
2. Fake provider：成功只调用一次；失败保持现有 2 attempts 后安全 fallback。
3. Integration：Harness 最终只接受 `QuestionBank`，AgentRun 可观测。
4. Acceptance runner：同进程基线/候选分别运行且 prompt_version 隔离。
5. 全量 pytest：保留 `.env`，真实 socket 尝试为 0。

## 2. 拟修改文件

- `app/schemas/question_draft.py`（新增）
- `app/agents/question_bank_assembler.py`（新增）
- `app/agents/question_bank_draft_agent.py`（新增）
- `app/agents/prompts/question_bank_draft_agent_v0.1.md`（新增）
- `app/agents/base.py`
- `app/services/llm_acceptance_service.py`
- Phase 2.4A unit/integration 测试（新增）
- `tests/integration/test_llm_acceptance_runner.py`（扩展）

## 3. 明确不修改

- `app/agents/question_bank_agent.py` 的运行时类和 `prompt_version`；
- `question_bank_agent_v0.1.md` 与 v0.2 A/B 资产；
- `app/schemas/question.py` 的最终 QuestionBank 约束；
- provider clients、LLMRequest temperature、timeout、max attempts；
- 其他 Agent、API、数据库迁移和前端。

## 4. 回滚单位

候选是新增类和内部 Schema。若离线门禁失败，删除候选注入即可恢复；默认运行时和 API 不需切换或迁移。BaseAgent transform 参数默认 `None`，现有 Agent 行为保持不变。
