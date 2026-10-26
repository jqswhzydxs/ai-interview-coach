# Phase 2.4D-B Provider 稳定性与 Token 记账协议 v2 Tasks

## 证据与冻结

- [x] 建立 110 个受保护文件的实施前 SHA-256 基线。
- [x] 只读核对 run1/run2/run3 manifest、report 与 attempt audit。
- [x] 为三次运行分别生成新的阻塞事件记录。
- [x] 保持旧协议、旧报告、Prompt、metadata、Schema、fixtures、生成参数和生产路径不变。

## 协议实现

- [x] 拆分 `successful_response_usage` 与 `billing_usage_completeness`。
- [x] 实现 `known_token_lower_bound`，未知字段保持 `null`。
- [x] 实现硬 Provider call budget。
- [x] 独立记录 timeout/network/retry/deadline/fallback。
- [x] 实现 real + safe-valid + successful usage complete 的 pair 准入。
- [x] 冻结 total-token 不可证明时采用 lower-bound audit。
- [x] 冻结本协议不增加 `max_tokens`；未来修改必须新协议并完整重跑。

## Readiness

- [x] readiness 与 A/B 使用独立账本和计数域。
- [x] 冻结最多 2 次、每次 1 call、无内部 retry。
- [x] 要求 usage 完整的真实安全响应。
- [x] 两次失败后 blocked，禁止创建正式 A/B 目录。

## 离线验证

- [x] timeout 后成功。
- [x] network error 后成功。
- [x] 两次 network error 后 fallback。
- [x] 成功 usage 完整、失败 usage 未知。
- [x] call budget 与 known-token lower bound。
- [x] comparable pair 准入与排除。
- [x] 旧协议/旧报告 hash 不变。
- [x] 专项测试。
- [x] 全量离线测试：353 passed，1 skipped。
- [x] 迁移测试：3 passed。
- [x] compileall。
- [x] `git diff --check`。
- [x] socket guard：真实 socket 尝试 0。
- [x] 最终保护文件哈希检查：110/110 未变化。
