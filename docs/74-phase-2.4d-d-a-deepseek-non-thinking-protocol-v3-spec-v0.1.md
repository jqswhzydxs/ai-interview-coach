# Phase 2.4D-D-A DeepSeek Non-Thinking Protocol v3 Spec

## 1. 范围与协议身份

新协议标识为 `phase-2.4d-question-draft-reasoning-token-v3`。它不复用或续跑 protocol v1/v2、ab1 或旧 readiness ledger。Phase 2.4D-C 的 `stopped_for_engineering_futility` 决策和所有历史报告保持只读。

本阶段只实现和离线验证代码，不访问 Provider，不创建正式 readiness ledger 或 A/B 运行目录。生产 `QuestionBankAgent`、普通 `DeepSeekClient` 和生产配置不改变。

## 2. 严格单变量

| 项目 | Baseline | Candidate |
|---|---|---|
| Prompt | `question_bank_draft_agent_v0.2` | `question_bank_draft_agent_v0.2` |
| Model | `deepseek-v4-pro` | `deepseek-v4-pro` |
| Thinking | `{"type":"enabled"}` | `{"type":"disabled"}` |
| `reasoning_effort` | 不发送 | 不发送 |

两侧继续固定 QuestionDraftBank Schema、metadata v2、最终 QuestionBank Schema、Go/Java/Python fixtures、temperature=0.2、max_tokens=null、client timeout=60 秒、variant deadline=120 秒、Agent 最多 2 attempts、retry/fallback 行为、8/8/9、跨栈、重复和 evidence safety 检查。

同一 pair 的 `LLMRequest` 指纹必须完全相同。请求传输层唯一允许的差异路径是 `thinking.type`；发现其他差异时 runner 将实验标记为 `invalidated_protocol`。

## 3. 实验专用 Provider client

`DeepSeekThinkingExperimentClient` 通过构造参数显式注入 `thinking_type`，只由 v3 readiness/A/B CLI 构造。baseline 和 candidate 使用两个独立实例。普通 `DeepSeekClient` 没有 thinking 参数、环境开关或全局默认切换。

实验 client 将 `thinking` 直接写入 HTTP JSON body。请求层测试必须证明：

- baseline body 含 `thinking.type=enabled`；
- candidate body 含 `thinking.type=disabled`；
- 删除 `thinking` 后两个 body 完全相同；
- 两侧均不存在 `reasoning_effort`；
- MockTransport 实际接收上述字段，证明 client 没有丢弃；
- 普通 `DeepSeekClient` 的 request body 不含实验字段。

## 4. Readiness v3

readiness 使用 v3 独立 ledger，固定 candidate non-thinking 路径：Go fixture、Prompt v0.2、`thinking.type=disabled`、QuestionDraftBank、metadata v2 及全部内容检查。

- 最多 2 个 readiness attempts；
- 每个 attempt 严格 1 个 Provider call；
- 不进入 `BaseAgent.execute`，无 retry、无 fallback；
- 首次失败后只允许继续同一个 ledger；
- 两次失败后永久 `blocked`；
- terminal ledger 重复 attempt 字节幂等；
- 只有 real、安全有效、成功 response usage 三字段完整且 billing complete 时通过；
- readiness ledger 必须位于 A/B 目录外；
- passed 前 runner 构造失败，A/B 目录不得创建。

真实 readiness 同时要求 `RUN_REAL_LLM_ACCEPTANCE=true`、`SAVE_FULL_LLM_LOGS=false` 和 `--authorize-phase-2-4d-d-a-readiness`，并严格要求 Provider/model 为 `deepseek/deepseek-v4-pro`。

## 5. A/B 状态机与预算

CLI 支持 `prepare/status/smoke/pilot/full/finalize`。`prepare` 只能在 matching passed readiness ledger 后创建全新空目录。manifest 固定 ledger SHA-256、Provider/model、Prompt/Schema/fixture/metadata/client/runner 哈希及协议快照。

执行顺序：3 cases × 5 pairs。奇数 pair 为 baseline→candidate，偶数 pair 为 candidate→baseline。Pilot 只运行 pair 1；Full 只补 pair 2–5。Pilot 通过不会调用 Full。

smoke、pilot、full 分别要求自己的 CLI 授权 flag。每个 execution 有 120 秒绝对 deadline；全实验 Provider call budget 为 62，并在下一次调用前硬停止。

## 6. Token 与安全记账

每次 execution 保留 protocol v3 的五类记账：successful response usage、billing completeness、known lower bound、Provider call budget 和 execution reliability。失败 attempt usage 未知时保持 null，不污染最终成功 response token。

可选 usage details 仅保存以下显式非负整数：reasoning、visible completion、cached input、cache read input、cache creation input。缺失字段记为 `unknown`；不使用减法或其他方法推算。`reasoning_content`、CoT、完整 response、请求正文、异常正文和凭据不得持久化。

只有 pair 双方 final output 均为 real、安全有效，且成功 response usage 完整时才可进入 Token 比较。fallback 不进入 Token 比较或盲评包。

## 7. 预注册门禁

Full 完成和独立盲评导入后，所有以下门禁都必须通过：

- candidate 15/15 real、安全有效；
- 每个 case candidate 5/5 real、安全有效；
- 全部 30 runs 的 fallback 数为 0；
- Schema、assembler、strict count、跨栈、重复和 evidence safety 失败数为 0；
- request invariant mismatch 为 0；
- 至少 12 个 Token comparable pairs；
- candidate 平均 output tokens ≤1800；
- paired output-token reduction 相对 baseline ≥10%；
- candidate P95 ≤90 秒、max ≤120 秒；
- 独立盲评完整；正文综合质量 ≥4.0，且相对 baseline 下降不超过 0.2；
- metadata v2 适配度 ≥3.5。

任一必需门禁失败，non-thinking candidate 不通过。Pilot gate 只检查 candidate 3/3 real、安全有效，不代表最终通过。
