# Phase 2.4D-B Provider 稳定性与 Token 记账协议 v2 Spec

## 1. 范围与结论边界

本阶段只读取 `question-bank-token-phase-2-4d-b-20261022-run1`、`run2`、`run3`，形成新的阻塞事件记录并实现独立 protocol v2。旧运行目录、旧 protocol v1、旧报告和旧结论不回写。没有真实 Provider 调用，没有创建 run4，也不评价 Prompt v0.2 的正文质量。

Prompt v0.1/v0.2、`QuestionBankMetadataAssemblerV2`、Draft/最终 Schema、三套 fixtures、模型与生成参数、Provider client、retry/fallback、生产 `QuestionBankAgent` 均冻结。实施前 110 个受保护文件的 SHA-256 已保存到独立审计目录。

## 2. v2 记账对象

每次 variant 执行必须分别记录以下五类信息：

1. `successful_response_usage`：只取最终成功的真实 Provider response usage。三个 token 字段均为非负整数时标记 `complete`；失败 attempt 的 usage 不进入该数值。
2. `billing_usage_completeness`：只有该执行的每个 Provider attempt 都有完整 usage 才为 `complete`。任一 attempt 未知即为 `incomplete`，并列出未知 attempt；零调用为 `not_applicable`。
3. `known_token_lower_bound`：仅累加实际出现的字段。若某字段没有任何已知值，保存 `null`，不得用 0 代替未知。
4. `provider_call_budget`：在下一次 Provider call 之前检查的硬上限。到达上限后禁止调用。
5. `execution_reliability`：分别统计 timeout、network、其他失败、retry、deadline、real/fallback，不从 token 字段推断可靠性。

## 3. Token pair 准入

一个 pair 只有在 baseline 和 candidate 同时满足以下条件时才可比较：

- final output 为 real；
- Schema、assembler、跨栈、重复和内容安全检查均有效；
- 最终成功 response 的 input/output/total usage 完整；
- output tokens 是成功 response 的真实值。

失败 attempt 的 usage 未知不会覆盖成功 response 的 output token。它会把 `billing_usage_completeness` 标成 `incomplete`，并在报告中显示大写警告。fallback、mock、deadline、成功 response usage 不完整或安全检查失败都会排除该侧及整个 pair。fallback 的长度、内容和 token 不进入 Prompt v0.2 评价。

## 4. Token 预算冻结选择

当前 Provider payload 没有 `max_tokens`，因此无法从本地协议证明单请求 output-token 上界，也无法在 attempt usage 缺失时证明真实 total-token 消耗。protocol v2 冻结选择为 `known_lower_bound_audit`：

- `max_total_tokens` 不再声称为可证明的硬门禁；
- 始终报告已知 token 下界和 billing 完整性；
- Provider call budget 继续作为硬停止条件；
- 不使用臆测的保守 token 上界。

本阶段不增加 `max_tokens`，以保持生成参数冻结。若后续需要可证明的单请求上界，必须建立新的固定协议版本、固定 `max_tokens`，重新执行 readiness、smoke、pilot 和 full；protocol v1/v2 数据不得混用。

## 5. Provider readiness gate

readiness 与正式 A/B 使用不同账本，输出不计入 Token A/B，也不进入盲评包。规则预注册如下：

- 最多 2 次 readiness attempt；
- 每次严格 1 个 Provider call，内部 retry 为 0；
- 获得一个 real、安全有效、成功 response usage 完整且本次 billing usage 完整的响应后通过；
- 首次失败只允许在同一个 readiness ledger 记录第二次尝试；
- 两次均失败后状态永久为 `blocked`，不得通过连续建立新运行目录重试；
- readiness 未通过时，正式 A/B runner 必须在创建运行目录之前终止。

readiness 自身产生的已知或未知费用只在 readiness ledger 审计，不并入 A/B token 指标。

## 6. Provider client 审计结果

- 请求层 timeout 为每个 HTTP attempt 60 秒；variant 外层 `asyncio.timeout` 为整次执行 120 秒。
- `BaseAgent.run_with_fallback` 是唯一 retry owner，冻结为最多 2 次；Provider client 和实验 harness 没有第二层 retry 循环。
- `RemoteProtocolError` 被安全观测层分类为 `network`。这是错误类别，不是根因判断。
- 注入 `AsyncClient` 时连接池生命周期由调用方管理；默认路径在每次 `generate_json` 内新建并关闭 `AsyncClient`，attempt 之间不复用默认连接池。
- 项目代码没有显式固定 proxy、TLS CA/verify、HTTP2 或 keep-alive limits；它们来自当前 httpx 默认值、环境处理或注入 client 的配置。

现有运行没有 Provider 侧 trace、失败进程的代理/TLS 快照、连接生命周期 trace 或 request id，无法声称已找到 Provider 根因。

## 7. 机器可执行资产

- `app/services/question_draft_token_protocol_v2.py`：纯离线记账、pair 准入、调用预算和 readiness 状态机。
- `app/services/phase_2_4d_b_protocol_review.py`：只读三次旧运行并生成脱敏事件与静态 client 审计。
- `scripts/review_question_draft_token_protocol_v2.py`：离线生成审计资产，不实例化 Provider client。
- `storage/reports/question-bank-token-phase-2-4d-b-protocol-v2-review-20261022/`：基线哈希、事件、client 审计、协议快照及验证结果。

protocol v2 是新的预注册协议，不能回写或重新解释 Phase 2.4B、Phase 2.4D-A 或三次 protocol v1 运行。
