# Phase 2.1：真实 LLM 验收与可观测性 v0.1

## 1. 目标与范围

Phase 2.1 在执行 DeepSeek/Kimi 真实验收前，先让每次 Agent 执行能够明确回答：是否调用了真实模型、调用了几次、是否重试、最终是否降级、为什么降级、耗时和 token 用量是多少。

本阶段不修改现有 API 合约、不开发前端、不改变 `LLM_PROVIDER=mock` 默认值，也不在默认测试或 dry-run 中访问真实 provider。

## 2. 唯一职责边界

1. Provider client：一次方法调用对应一次 HTTP 请求；解析 OpenAI-compatible 响应和 token usage；不重试、不降级。
2. `BaseAgent`：真实调用重试的唯一所有者；默认最多调用 2 次，即最多重试 1 次；全部失败后执行一次 rule-based fallback。
3. `AgentHarness`：每个 Agent 只调用一次；负责最终 Schema 防线、AgentRun/step 持久化和应用错误转换，不重跑 Agent。
4. `AgentRunService`：负责安全摘要、运行指标落库和跨 AgentRun 聚合，不参与调用、重试或 fallback 决策。
5. 验收运行器：组织固定样例和生成报告，不实现另一套调用或重试逻辑。

因此不存在 Harness 重跑 Agent 与 Agent 内部重试叠加形成的 2×2 调用。

## 3. 执行结果

每个 AgentRun 的 `execution_mode` 只能是：

- `mock`：没有真实调用，直接使用 rule-based 输出；
- `real`：至少一次真实调用，最终真实输出通过 Schema；
- `fallback`：尝试过真实调用，但最终使用 rule-based 输出。

AgentRun 记录：

- provider、model、prompt_version；
- real_call_count、retry_count、总 latency；
- input/output/total tokens；
- 结构化 fallback_reason；
- 按 `json`、`schema`、`timeout`、`provider` 分类的失败计数。

AgentRun step 按真实调用尝试记录安全指标；fallback 会额外记录一个步骤。step 不保存 prompt、完整输入或原始响应。

## 4. 聚合口径

- 真实成功率：最终 `execution_mode=real` 且成功的运行数 / 进入 real 或 fallback 路径的运行数；
- 降级率：`execution_mode=fallback` 的运行数 / 进入 real 或 fallback 路径的运行数；
- 失败类型：汇总每次真实调用的结构化失败分类；
- token usage：汇总 provider 返回的 usage；provider 未返回的值保持未知，不从文本长度推算。

## 5. 成本策略

代码不内置 DeepSeek/Kimi 价格。只有同时显式配置以下两项时，报告才按每百万 token 估算：

```text
LLM_INPUT_COST_PER_MILLION
LLM_OUTPUT_COST_PER_MILLION
```

未配置时，报告将成本标记为 `not_configured`。

## 6. 安全策略

1. `SAVE_FULL_LLM_LOGS=false` 保持默认值。
2. 默认日志只保存字段名摘要，不保存完整简历、JD、回答或 prompt。
3. 即使显式开启 full logging，已知敏感字段和 credential 字段仍会被结构化脱敏。
4. provider 原始文本不会写入 AgentRun、step 或验收报告。
5. fallback reason 使用固定错误码和阶段，不写异常中的模型原文。
6. 真实验收需要 `RUN_REAL_LLM_ACCEPTANCE=true`；否则运行器拒绝真实调用。

## 7. 验收运行器

运行器固定读取：

- `tests/fixtures/sample_cases/backend_go_case.json`
- `tests/fixtures/sample_cases/backend_java_case.json`
- `tests/fixtures/sample_cases/backend_python_case.json`

离线验证报告结构：

```powershell
.\.venv\Scripts\python.exe scripts\run_llm_acceptance.py --dry-run
```

真实验收由环境配置显式开启；运行器生成同名 JSON 和 Markdown 汇总，写入 `REPORT_DIR`。报告包含逐 Agent 指标和整体成功率/降级率，不包含完整样例输入与原始模型响应。
