# Phase 2.4D-D-A 离线验证报告

验证日期：2026-10-23（Asia/Singapore）。本阶段没有访问真实 Provider，没有创建正式 readiness ledger 或正式 A/B 目录，没有执行 readiness attempt、smoke、pilot、full 或 finalize。

## 1. 请求层验证

MockTransport 捕获到实验 client 实际发送的 JSON body：baseline 明确携带 `thinking.type=enabled`，candidate 明确携带 `thinking.type=disabled`。删除 `thinking` 后两个 body 完全相同，且两侧都不含 `reasoning_effort`。普通生产 `DeepSeekClient` 的请求仍不含 `thinking` 或 `reasoning_effort`。

实验 response 中的 reasoning、visible completion 和 cached input 数值可以通过白名单提取。伪造的 `reasoning_content`、未知 response 字段和原始正文没有进入 response 序列化、ledger、audit 或报告。Provider 未返回 details 时所有细分项保持 `unknown`，没有填 0 或推算。

## 2. Readiness 与 A/B 验证

离线 fake client 场景确认：

- readiness 首次成功只调用一次；
- 首次 network failure 后可在同一 ledger 第二次成功；
- 两次失败后永久 blocked；
- passed/blocked 后重复 attempt 不新增调用且 ledger 字节不变；
- usage 缺失或内容检查失败不能通过；
- readiness 无 retry、无 fallback；
- wrong Provider/model/thinking 在 ledger 创建前拒绝；
- pending readiness 在 A/B 目录创建前拒绝；
- baseline/candidate Prompt SHA-256 相同且均为 v0.2；
- 15 个 pair 按奇偶交替，30 条 run 的 request invariant 每 pair 一致；
- fake full 形成 15 个 comparable pairs，candidate 15/15 real、安全有效；
- fallback 不进入 Token 比较或盲评包；
- timeout 后成功保留 successful-response usage，同时 billing 标为 incomplete；
- 62-call budget 在下一次调用前硬停止；
- smoke、pilot、full 分别缺少自己的授权 flag 时均在 client 构造/Provider call 前终止。

fake token 数值只用于验证计算逻辑，不是新的实验结果。

## 3. 验证结果

| 检查 | 结果 |
|---|---|
| v3 单元与集成专项 | 26 passed，real socket attempts=0 |
| v3 + B/B2/C 历史回归 | 69 passed，real socket attempts=0 |
| 全量离线测试 | 409 passed，1 skipped，1 既有弃用 warning，real socket attempts=0 |
| 迁移测试 | 3 passed，real socket attempts=0 |
| compileall | passed |
| `git diff --check` | passed；仅有工作区既有 LF/CRLF 提示 |
| CLI `--help` | readiness 3 commands、A/B 6 commands 均通过 |
| 冻结资产 SHA-256 | 161/161 passed，missing=0，changed=0 |
| 正式 D-D 目录检查 | 未创建 readiness 或 A/B 正式目录 |

保护基线 SHA-256：`fa133ff09611f9eb5ee5a70679fd6823689064e9a35bcda1aa8fabda27fc02f1`。

## 4. 交付状态

protocol v3、实验 Provider client、独立 readiness、A/B runner、两个 CLI、Spec、Plan、Tasks、Risk Analysis 和命令说明已完成。机器可读预注册与验证报告位于 `storage/reports/question-bank-token-phase-2-4d-d-a-offline-20261023`。

生产默认 Agent、普通 Provider client、Prompt v0.2、Schema、metadata v2、fixtures、ab1 和旧 readiness ledger 均与实施前哈希一致。本阶段停止在离线就绪状态，等待未来 readiness/smoke/pilot/full 的逐阶段明确授权。
