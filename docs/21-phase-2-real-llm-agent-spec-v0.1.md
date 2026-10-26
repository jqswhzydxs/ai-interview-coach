# Phase 2 Spec：真实 LLM Agent 接入 v0.1

## 1. 目标

在保持 MVP Phase 1 mock 闭环稳定的前提下，逐步接入真实 LLM Provider，让 Agent 可以在显式配置开启时调用真实模型，并继续输出可入库、可校验、可降级的结构化结果。

Phase 2 当前已完成 `QuestionBankAgent`、`ResumeAnalyzerAgent`、`JDAnalyzerAgent`、`ExperienceAnalyzerAgent`、`MatchingAgent`、`AnswerEvaluatorAgent` 和 `MemoryAgent` 的首轮真实 LLM 分支接入。

## 2. 核心约束

1. 默认仍使用 mock/rule-based 输出。
2. 只有配置选择真实 provider 时才调用真实 LLM。
3. mock agent 仍可用于单元测试、集成测试和端到端测试。
4. 真实 LLM 输出必须通过现有 Pydantic Schema 校验。
5. 真实 LLM 调用失败、JSON 无效、Schema 不匹配或超时时，必须降级到 mock/rule-based 输出。
6. 新增 provider smoke test，但真实 API key 测试默认跳过。
7. Phase 1 现有 100 个测试必须继续通过。

## 3. Provider 范围

当前使用既有 `LLMClient` 抽象：

1. `mock`
2. `deepseek`
3. `kimi`

业务层不得直接调用 provider SDK 或 HTTP。所有真实调用必须通过 `LLMClient.generate_json()`。

## 4. Agent 输出契约

每个真实 Agent 都必须满足：

1. Prompt 要求模型只返回 JSON object。
2. Provider 响应先解析为 dict。
3. dict 再交给目标 Pydantic Schema 校验。
4. 校验通过后返回 `model_dump(mode="json")`。
5. 校验失败或异常时进入降级路径。

Phase 2 已接入 Agent：

1. `QuestionBankAgent` -> `QuestionBank`
2. `ResumeAnalyzerAgent` -> `ResumeProfile`
3. `JDAnalyzerAgent` -> `JDProfile`
4. `ExperienceAnalyzerAgent` -> `ExperienceProfile`
5. `MatchingAgent` -> `MatchReport`
6. `AnswerEvaluatorAgent` -> `AnswerEvaluation`
7. `MemoryAgent` -> `MemoryUpdate` / `MemoryItem`

## 5. 降级策略

`QuestionBankAgent` 的降级策略：

1. 默认 provider 为 `mock` 时，直接使用 rule-based 题库。
2. provider 为 `deepseek` 或 `kimi` 时，先调用真实 LLM。
3. 真实 LLM 输出通过 `QuestionBank` 校验后返回。
4. 如遇以下情况，降级到 rule-based 题库：
   - provider 抛出异常；
   - provider 超时；
   - provider 返回非 JSON 或 JSON 解析失败；
   - provider 返回 JSON 但不满足 `QuestionBank` Schema；
   - provider 返回题量不足、模块不足、重复 question_id 等业务约束错误。

## 6. Smoke Test 策略

Provider smoke test 只验证 provider 最小可用性：

1. 默认 skip。
2. 仅当显式配置开启且存在对应 API key 时运行。
3. 不进入默认 CI 必跑路径。
4. 不记录真实密钥或真实敏感输入。

建议开启条件：

```text
RUN_REAL_LLM_SMOKE_TESTS=1
LLM_PROVIDER=deepseek|kimi
DEEPSEEK_API_KEY=...
KIMI_API_KEY=...
```

## 7. 非目标

1. 不修改 Phase 1 API 合约。
2. 不引入正式前端。
3. 不要求默认测试访问真实外部网络。
4. 不将 API key 写入代码、文档示例以外的 fixture 或测试。
5. 不保存完整敏感原文到默认 Agent run 日志。
