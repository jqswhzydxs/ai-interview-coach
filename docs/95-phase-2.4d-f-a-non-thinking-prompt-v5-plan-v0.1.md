# Phase 2.4D-F-A Protocol v5 Plan

1. 在修改前冻结 v1–v4、生产 Agent、Prompt v0.2、Schema、metadata v2 和 fixtures 的 SHA-256。
2. 新建 Prompt v0.3，并用确定性测试约束证据、覆盖、训练价值、禁止虚构、8/8/9 和 only-question-text 合同。
3. 新建显式 Prompt v0.2/v0.3 绑定及 non-thinking 实验 client；普通 Provider client 与生产路径保持不变。
4. 新建纯离线 protocol v5 记账、readiness runner/CLI 和 A/B runner/CLI，使用新版本、目录、报告名与锁。
5. 对 readiness 前置校验、请求单变量、阶段授权、预算、deadline、retry/fallback、usage unknown、盲评和隐私做离线测试。
6. 生成机器可读预注册和 Spec、Plan、Tasks、Risk Analysis、Command Guide、Offline Validation Report。
7. 执行 v5 专项、v1–v4 回归、全量离线、迁移、compileall、diff-check、socket guard 与冻结资产复核。

Readiness 状态机为 `prepare → attempt(≤2) → passed|blocked`；A/B 状态机为 `prepare → smoke → pilot → full → finalize`。每个命令只执行指定阶段。正式目录仅可由未来明确授权的命令创建，本次只写入离线交付目录。
