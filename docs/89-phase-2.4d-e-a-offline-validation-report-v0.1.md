# Phase 2.4D-E-A Offline Validation Report

验证日期：2026-10-24（Asia/Singapore）。本阶段 Provider calls=0；没有创建正式 v4 readiness ledger 或 A/B 目录，没有执行 readiness attempt、smoke、pilot、full 或 finalize。

## 1. 实现结果

新增实验专用 DeepSeek client、纯离线 protocol v4、独立 readiness runner/CLI、独立 A/B runner/CLI 和机器可读预注册。Baseline/candidate 固定 thinking enabled，并分别显式发送 reasoning_effort high/low。生产 `DeepSeekClient`、生产默认 `QuestionBankAgent` 和 v1/v2/v3 runner 未修改。

MockTransport 捕获的最终请求证明两个实验字段没有被 SDK/client 丢弃。把 `reasoning_effort` 归一化后，两侧请求逐字段一致。Response 只提取 usage 与白名单数字细分；`reasoning_content`、CoT、原始响应和完整敏感输入不会进入 manifest、audit 或公开报告。

## 2. 离线场景覆盖

专项测试覆盖：readiness 首次成功、首次失败后第二次成功、两次失败永久 blocked、每 attempt 一 call、无 retry/fallback、usage 缺失或内容检查失败拒绝、终态幂等、A/B 前置 readiness/哈希/Provider/model 拒绝、15 pairs 交替顺序、timeout 后成功与 billing incomplete、RemoteProtocolError、fallback 排除、comparable pair、62-call 硬停止、阶段授权、严格盲评 30/150/750 计数、隐私过滤和 203 个冻结资产保护。

Fake client 与 fake token/评分只验证状态机和计算逻辑，不构成真实 Provider 结论。

## 3. 验证结果

| 检查 | 结果 |
|---|---|
| v4 单元与集成专项 | 27 passed，real socket attempts=0 |
| v1/v2/v3 历史协议回归 | 75 passed，real socket attempts=0 |
| 全量离线测试 | 443 passed，1 skipped，1 条既有弃用 warning，real socket attempts=0 |
| 迁移测试 | 3 passed，real socket attempts=0 |
| compileall | passed |
| `git diff --check` | passed；仅有工作区既有 LF/CRLF 提示 |
| CLI `--help` | readiness 3 commands、A/B 6 commands 均通过 |
| 冻结资产 SHA-256 | 203/203 passed，missing=0，changed=0 |
| 正式 v4 目录检查 | 未创建 readiness ledger 或 A/B 目录 |

机器可读结果位于同目录的 `offline-validation-report.json`。保护基线 SHA-256 为 `9a3f7eabb3dbb3e136607501a61d4b81f5b8775477be5e675a85e0c1c094cedc`，包含 203 个文件。

## 4. 停止点

当前状态为 `offline_implementation_complete`。机器可读预注册已经在任何 v4 真实数据产生前冻结。下一步只能在用户逐阶段明确授权后，按 Command Guide 执行 readiness、smoke、pilot、full 和 finalize；本阶段在此停止。
