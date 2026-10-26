# Phase 2.4D-E-A Protocol v4 Tasks

## 已完成

- [x] 建立 203 个冻结/历史资产的实施前 SHA-256 基线。
- [x] 新增 `DeepSeekReasoningEffortExperimentClient`，固定 thinking enabled，强制 high/low 显式选择。
- [x] 验证实际 HTTP body 保留 thinking 与 reasoning_effort，且两侧只差 effort 值。
- [x] 验证普通生产 `DeepSeekClient` 不受影响。
- [x] 新增 protocol v4 的五类 Token/可靠性记账与机器可读预注册。
- [x] 新增独立 readiness v4 runner 与 `prepare/attempt/status` CLI。
- [x] 实现 readiness 两次上限、每 attempt 单 call、无 retry/fallback、终态幂等和双重授权。
- [x] 新增独立 A/B v4 runner 与 `prepare/status/smoke/pilot/full/finalize` CLI。
- [x] 实现 readiness 前置验证、3×5 pairs、交替顺序、120 秒 deadline 和 62-call 硬预算。
- [x] 实现 usage unknown、billing completeness、known lower bound、可靠性和 fallback 排除。
- [x] 实现失败 attempt 立即脱敏持久化与报告隐私过滤。
- [x] 实现随机盲评包、私有映射和 30/150/750 严格 finalize 校验。
- [x] 覆盖 readiness、请求不变量、预算、重试、fallback、账务、盲评和历史资产保护测试。
- [x] 生成 Spec、Plan、Tasks、Risk Analysis、Command Guide、Offline Validation Report 和机器可读预注册。

## 后续仅在逐阶段明确授权后执行

- [ ] 创建正式 v4 readiness ledger。
- [ ] 执行最多两次 readiness attempt。
- [ ] readiness passed 后创建全新正式 v4 A/B 目录。
- [ ] 分别授权并执行 smoke、pilot、full。
- [ ] 完成独立盲评并执行 finalize。

这些后续项不属于本次离线实现；不得复用 v3 样本或目录。
