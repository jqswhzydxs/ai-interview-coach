# Phase 2 Tasks：真实 LLM Agent 接入 v0.1

## 1. 任务总览

| ID | 任务 | 验收 | 状态 |
| --- | --- | --- | --- |
| T201 | 新增 Phase 2 spec/plan/tasks 文档 | 文档说明默认 mock、真实 provider、校验、降级和 smoke test 策略 | 已完成 |
| T202 | 为 `QuestionBankAgent` 增加真实 LLM 分支 | `mock` provider 仍走 rule-based，真实 provider 才调用 LLM | 已完成 |
| T203 | 为真实 QuestionBank 输出增加 Pydantic 校验 | provider 输出必须通过 `QuestionBank` Schema | 已完成 |
| T204 | 为真实 QuestionBank 增加降级策略 | JSON 无效、schema 不匹配、timeout、异常均降级到 rule-based | 已完成 |
| T205 | 增加 QuestionBankAgent 真实分支单元测试 | 覆盖成功、JSON 无效、schema 不匹配、provider 超时 | 已完成 |
| T206 | 增加 provider smoke test | 默认 skip；显式启用且有 API key 时运行 | 已完成 |
| T207 | 回归 Phase 1 全量测试 | unit、integration、e2e 全部通过 | 已完成 |

## 2. 当前批次范围

本批已实现：

1. T201
2. T202
3. T203
4. T204
5. T205
6. T206
7. T207

## 3. 真实 Agent 扩展任务（已完成）

| ID | 任务 | 输出 Schema | 状态 |
| --- | --- | --- | --- |
| T208 | 接入 `ResumeAnalyzerAgent` 真实分支 | `ResumeProfile` | 已完成 |
| T209 | 接入 `JDAnalyzerAgent` 真实分支 | `JDProfile` | 已完成 |
| T210 | 接入 `ExperienceAnalyzerAgent` 真实分支 | `ExperienceProfile` | 已完成 |
| T211 | 接入 `MatchingAgent` 真实分支 | `MatchReport` | 已完成 |
| T212 | 接入 `AnswerEvaluatorAgent` 真实分支 | `AnswerEvaluation` | 已完成 |
| T213 | 接入 `MemoryAgent` 真实分支 | `MemoryUpdate` / `MemoryItem` | 已完成 |

每个后续任务都必须包含：

1. 默认 mock 不变。
2. 真实输出 Schema 校验。
3. 重试或降级策略。
4. 单元测试覆盖成功和失败路径。
