# Phase 2.4D-B2 Readiness 与 Token Protocol v2 Runner Tasks

## Readiness

- [x] 新增 `prepare/attempt/status` CLI。
- [x] 固定 Go fixture、Prompt v0.2、QuestionDraftBank、metadata v2。
- [x] 每个 attempt 结构上限制为一个 direct Provider call。
- [x] 禁用 Agent retry 和 fallback。
- [x] 实现 2-attempt 单 ledger 状态机和 terminal 幂等。
- [x] 实现真实 attempt 双重授权及安全日志门禁。
- [x] ledger 保存资产哈希、脱敏失败、v2 记账和内容检查。

## Protocol v2 A/B

- [x] 新增独立 runner/CLI，不修改 protocol v1。
- [x] readiness 通过前禁止创建 A/B 目录。
- [x] 校验 ledger、Provider/model、冻结资产和 hash 漂移。
- [x] manifest 保存 readiness ledger SHA-256。
- [x] 集成五类 protocol v2 记账。
- [x] fallback 排除 Token 和盲评质量比较。
- [x] 固定 Prompt、assembler、参数、deadline 和 62-call budget。

## 验证

- [x] 首次成功；首次失败后第二次成功；两次失败 blocked。
- [x] 单 call、无 retry、无 fallback、terminal 幂等。
- [x] usage 缺失与内容检查失败不能通过。
- [x] readiness/Provider/model/assets/ledger hash 拒绝。
- [x] timeout 后成功、RemoteProtocolError、fallback 排除。
- [x] comparable pair 与 call budget。
- [x] protocol v1 和生产默认路径不变。
- [x] 专项测试最终复跑：32 passed。
- [x] 全量离线测试：372 passed，1 skipped。
- [x] 迁移测试：3 passed。
- [x] compileall。
- [x] `git diff --check`。
- [x] socket guard：真实 socket 尝试 0。
- [x] 冻结资产最终哈希检查：129/129 未变化。
