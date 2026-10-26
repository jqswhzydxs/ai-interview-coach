# Phase 2.4D-E-A Protocol v4 Plan

## 1. 实施顺序

1. 对 v3 readiness、ab1、盲评、报告、生产 Agent、Prompt v0.2、Schema、metadata v2、fixtures 和既有协议代码建立实施前 SHA-256 基线。
2. 新增只用于实验的 DeepSeek reasoning-effort client，固定 thinking enabled，并强制 high/low 显式注入。
3. 新增纯离线 protocol v4 记账与机器可读预注册，延续 protocol v2 的五类记账语义。
4. 新增独立 readiness v4 runner/CLI，保证单 ledger、两次上限、单 attempt 单 call、无 retry/fallback 和双重授权。
5. 新增独立 A/B v4 runner/CLI，在任何目录写入前验证 readiness、Provider/model 和资产哈希。
6. 加入请求不变量、状态机、预算、账务、隐私和盲评合同测试。
7. 生成 Spec、Plan、Tasks、Risk Analysis、Command Guide、Offline Validation Report 和机器可读预注册。
8. 执行专项、历史协议回归、全量离线、迁移、compileall、diff-check、socket guard 和冻结资产复核。

## 2. 隔离边界

v4 使用新的模块名、协议版本、ledger 版本、报告文件名和锁文件。它只读取既有冻结资产，不修改 v1/v2/v3 runner、历史目录或生产默认 Agent。正式 v4 目录只能由未来明确授权的命令创建，本阶段仅写入离线交付目录。

## 3. 状态机

Readiness 流程为 `prepare → attempt(≤2) → passed|blocked`。A/B 流程为 `prepare → smoke → pilot → full → finalize`，其中每一步只执行所指定阶段。Readiness 未 passed 时，A/B 构造在 `mkdir` 前失败；Full 不会因 Pilot 通过而自动执行。

## 4. 验证策略

请求层使用 `httpx.MockTransport` 观察最终 HTTP body；业务层使用 fake client 驱动成功、timeout、network、fallback、usage unknown、预算耗尽和盲评导入路径。全套 pytest 由 socket guard 清除真实凭据并拦截真实网络。所有 fake token/质量数据只验证计算逻辑，不形成实验结论。
