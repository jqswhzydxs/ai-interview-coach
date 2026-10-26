# Phase 2.4D-B2 Readiness 与 Token Protocol v2 Runner Plan

1. 在修改前扩展保护清单，冻结 protocol v1、历史报告、Prompt、metadata、Schema、fixtures、Provider 配置和生产路径。
2. 新增 readiness asset snapshot 和单 ledger runner，只直接调用 client 一次。
3. 新增 readiness CLI，分离 offline prepare/status 与双重授权 attempt。
4. 新增 protocol v2 A/B runner，在任何目录创建前验证 readiness。
5. 将 protocol v2 五类记账接入 smoke、paired runs、汇总和 manifest。
6. 仅将 real、安全有效输出加入盲评；fallback 只保留私有审计状态。
7. 新增独立 v2 CLI，并对真实 smoke/pilot/full 增加显式授权门禁。
8. 用 fake client 覆盖 readiness 状态机、timeout/network/retry/fallback、pair 准入、预算及 hash 漂移。
9. 执行专项、全量离线、迁移、compileall、diff、socket guard 和 129 文件哈希复核。
10. 输出验证报告后停止，不执行真实 readiness 或 A/B。
