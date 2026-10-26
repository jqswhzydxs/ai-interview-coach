# Phase 2.4D-E-A DeepSeek Reasoning-Effort Protocol v4 Spec

## 1. 范围与协议身份

新协议标识为 `phase-2.4d-question-draft-reasoning-effort-token-v4`。它是独立协议，不复用或续跑 protocol v1/v2/v3 的 readiness ledger、A/B 目录或实验样本。Protocol v3 的最终失败结论及其 readiness、ab1、盲评、manifest、audit、报告和分析资产保持只读。

本阶段只实现代码、协议文件和离线验证，不访问 Provider，不创建正式 v4 readiness ledger 或 A/B 目录。生产 `QuestionBankAgent`、普通 `DeepSeekClient`、生产配置和 API 合约不改变。

## 2. 严格单变量

| 项目 | Baseline | Candidate |
|---|---|---|
| Prompt | `question_bank_draft_agent_v0.2` | `question_bank_draft_agent_v0.2` |
| Model | `deepseek-v4-pro` | `deepseek-v4-pro` |
| Thinking | `{"type":"enabled"}` | `{"type":"enabled"}` |
| `reasoning_effort` | `high`，显式发送 | `low`，显式发送 |

两侧固定 QuestionDraftBank Schema、metadata v2 assembler、最终 QuestionBank Schema、Go/Java/Python fixtures、temperature=0.2、max_tokens=null、client timeout=60 秒、execution deadline=120 秒、最多 2 attempts、retry/fallback、JSON Output、8/8/9 计数及技术栈、重复和 evidence safety 检查。

同一 pair 的 Provider 请求在把 `reasoning_effort` 归一化为占位值后必须逐字段一致。runner 保存归一化请求指纹；出现其他字段差异时记为 request invariant mismatch，并使最终门禁失败。

## 3. 实验专用 Provider client

`DeepSeekReasoningEffortExperimentClient` 只由 v4 readiness/A/B CLI 显式构造。它固定发送 `thinking.type=enabled`，并要求构造时明确选择 `reasoning_effort=high|low`。不存在环境级全局切换，普通 `DeepSeekClient` 的请求结构不变。

请求层离线测试证明：

- 两侧实际 HTTP JSON body 均携带 `thinking.type=enabled`；
- baseline 明确发送 `reasoning_effort=high`，candidate 明确发送 `reasoning_effort=low`；
- 将 `reasoning_effort` 归一化后，两侧 body 逐字段相同；
- MockTransport 捕获到两个字段，SDK/client 没有丢弃或覆盖；
- 普通生产 client 不含 `thinking` 或 `reasoning_effort`。

## 4. Readiness v4

Readiness 使用独立 ledger，固定 Go fixture、Prompt v0.2、QuestionDraftBank、metadata v2、`thinking.type=enabled` 和 `reasoning_effort=low`。

- 最多 2 个 attempts；
- 每个 attempt 严格 1 个 Provider call；
- 不进入 BaseAgent retry，不使用 fallback；
- 第一次失败后只允许继续同一 ledger；
- 两次失败后永久 `blocked`；
- `passed`/`blocked` 终态重复 attempt 字节幂等；
- 只有 real、安全有效、Schema/assembler/8-8-9/技术栈/重复/evidence 全部通过，且成功响应 usage 三字段完整、billing complete 时才可 `passed`；
- readiness 输出不计入 A/B、盲评包或生产数据；
- ledger 必须位于 A/B 目录外，passed 前 runner 在创建 A/B 目录之前拒绝。

真实 attempt 同时要求 `RUN_REAL_LLM_ACCEPTANCE=true`、`SAVE_FULL_LLM_LOGS=false` 和 `--authorize-phase-2-4d-e-a-readiness`。Provider/model 必须严格匹配 `deepseek/deepseek-v4-pro`。

## 5. A/B 状态机与隔离

独立 CLI 支持 `prepare/status/smoke/pilot/full/finalize`。`prepare` 首先验证 passed readiness ledger、Provider/model 及全部资产哈希，然后才可创建全新的 A/B 目录。manifest 固定 readiness ledger SHA-256、实验资产哈希、协议快照与请求配置。

正式设计为 3 cases × 5 pairs，共 15 paired samples。Pilot 只运行每个 case 的 pair 1；Full 只补 pair 2–5。奇数 pair 顺序为 baseline→candidate，偶数 pair 为 candidate→baseline。Smoke、Pilot、Full 各自需要独立授权 flag，任何阶段均不会自动进入下一阶段。

每个 execution 使用 120 秒绝对 deadline。每个 execution 最多 2 个 Provider attempts；全实验 Provider call budget 为 62，并在下一次调用前硬停止。每个失败 attempt 立即以脱敏记录持久化。

## 6. Token、可靠性与隐私记账

每个 execution 独立保存五类语义：successful response usage、billing usage completeness、known token lower bound、Provider call budget、execution reliability。失败 attempt usage 未知时保持 null；不得填 0，也不得污染成功响应的 output tokens。

只接受 Provider 明确返回的非负整数：input/output/total tokens、reasoning tokens、visible completion tokens、cached input tokens、cache read input tokens、cache creation input tokens。缺失字段为 `unknown`，不通过减法或其他方式推算。

只有 pair 双方 final output 都是 real、安全有效且成功 response usage 三字段完整，才进入 Token 比较。Fallback 永远不进入 Token 比较或盲评包。

持久化资产禁止包含 `reasoning_content`、CoT、完整 Provider response、完整敏感输入、密钥和未过滤异常正文。盲评包只包含完成盲评所需的脱敏 evidence context 与题目；私有映射单独保存。

## 7. 盲评合同

Full 完成后生成随机顺序的 `question-review-packet.json`、`question-review-template.json` 和私有 blinding map。Finalize 严格要求：

- 恰好 30 份安全 real submissions，ID 与模板顺序一致；
- evaluator 的 `type`、`identifier`、`independence_confirmed` 完整；
- 每份 submission 有 5 个正文维度分数，共 150 个；
- 每份 submission 有 25 个逐题 metadata 分数，共 750 个；
- review 文件与该次 v4 packet 严格匹配。

## 8. 预注册最终门禁

所有门禁必须同时通过：candidate 15/15 real safe；每个技术栈 5/5 real safe；fallback=0；request invariant mismatch=0；Schema、assembler、count、跨栈、重复、evidence failure=0；comparable pairs≥12；candidate 平均 output tokens≤1800；相对 high baseline 的 paired reduction≥10%；candidate P95≤90 秒且 max≤120 秒；独立盲评完整；candidate 正文综合质量≥4.0；相对 baseline 下降≤0.2；candidate metadata v2 fit≥3.5。

任一必需门禁失败即拒绝 low-effort candidate。Pilot operational gate 通过也不代表最终通过，不会触发 Full。
