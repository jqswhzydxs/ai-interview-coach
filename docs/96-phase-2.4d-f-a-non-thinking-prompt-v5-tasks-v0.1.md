# Phase 2.4D-F-A Protocol v5 Tasks

## 本阶段完成

- [x] 建立 193 个既有资产的实施前 SHA-256 基线。
- [x] 新建 Prompt v0.3，加入 personalization、coverage/diversity、training value、technical correctness、clarity 与禁止虚构约束。
- [x] 显式绑定 baseline v0.2 与 candidate v0.3，并固定 exact metadata v2 assembler。
- [x] 新建 non-thinking 实验 client，双方发送 `thinking.type=disabled` 且不发送 `reasoning_effort`。
- [x] 新建 protocol v5 五类记账与机器可读预注册。
- [x] 新建 readiness v5 runner/CLI，保证单 ledger、两次上限、每 attempt 单 call、无 retry/fallback、终态幂等与双重授权。
- [x] 新建 A/B v5 runner/CLI，支持 3×5 pairs、交替顺序、120 秒 deadline、62-call 硬预算和逐阶段授权。
- [x] 实现 request invariant、fallback 排除、unknown usage、白名单 usage details 和脱敏失败记录。
- [x] 实现随机盲评、私有映射和 30/150/750 严格校验。
- [x] 实现绝对 Token/延迟门禁、质量提升门禁、五维质量门禁和 metadata fit 门禁；相对 Token 变化仅报告。
- [x] 验证生产默认 Agent 与 v1–v4 历史资产不变。

## 未来逐阶段授权后执行

- [ ] 创建正式 v5 readiness ledger。
- [ ] 最多执行两次 readiness attempt。
- [ ] readiness passed 后创建全新 v5 A/B 目录。
- [ ] 分别授权 smoke、pilot、full。
- [ ] 取得独立盲评并 finalize。

这些项目不属于本次离线实现；不得复用 v3/v4 真实样本。
