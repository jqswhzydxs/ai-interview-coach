# Phase 2.4D-D-A Tasks

- [x] 建立 161 文件实施前冻结哈希基线。
- [x] 新增实验专用 `DeepSeekThinkingExperimentClient`。
- [x] 固定 baseline enabled / candidate disabled，禁止 `reasoning_effort`。
- [x] 新增 protocol v3 独立记账模块。
- [x] 新增 readiness v3 runner 与 `prepare/attempt/status` CLI。
- [x] 新增 reasoning A/B v3 runner 与 `prepare/smoke/pilot/full/status/finalize` CLI。
- [x] readiness passed 前阻止 A/B 目录创建。
- [x] 保存白名单 usage details；缺失为 unknown。
- [x] 排除 fallback 的 Token 和盲评资格。
- [x] 固定 3 cases × 5 pairs、交替顺序、120 秒 deadline 和 62-call 预算。
- [x] 注册 candidate 15/15、Token、延迟、质量和 metadata v2 门禁。
- [x] 为 smoke/pilot/full 设置各自显式授权 flag。
- [x] 添加请求层、readiness、记账、runner 和历史资产测试。
- [ ] 执行真实 readiness；本阶段禁止。
- [ ] 创建正式 A/B 目录；本阶段禁止。
- [ ] 执行 smoke/pilot/full/finalize；等待后续逐阶段授权。
