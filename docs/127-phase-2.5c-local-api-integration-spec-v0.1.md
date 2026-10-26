# Phase 2.5C Local API Integration Spec v0.1

## 目标与状态

目标状态为 `phase_2_5c_local_api_integration_complete`。本阶段验证 React SPA 经 loopback HTTP 调用真实 FastAPI，并在隔离 SQLite 和隔离上传目录中完成业务读写；LLM 始终使用 mock Provider。

## 强制运行边界

- `APP_ENV=test`
- `LLM_PROVIDER=mock`
- `RUN_REAL_LLM_ACCEPTANCE=false`
- `SAVE_FULL_LLM_LOGS=false`
- DeepSeek、Kimi 等真实凭据在子进程环境中清空。
- 不读取或改写仓库 `.env`；数据库和上传目录使用运行级临时路径。
- 只允许 `localhost`、`127.0.0.1` 和 `::1` socket；非 loopback 连接立即失败并记账。
- production `QuestionBankAgent`、Prompt、模型实验和历史实验目录只读。

## 冻结基线

| 资产 | SHA-256 / 状态 |
|---|---|
| Phase 2.5A OpenAPI | `e983971aec77ddaf246efbb80637134f4fd41bfb9302fa2f3d06122430977304` |
| Phase 2.5B package-lock 历史值 | `e736f0835ff16e7718d299fc0c774115c0925b3d2cbcf00ff0d645fd163fa11a` |
| production QuestionBankAgent 文件 | `cefd190638efe3b1a4c4ce967907c10ef9b183cf47cf40b827d42ae816912bda` |
| Prompt v0.1 | `125a90d896d481b616955da5aebf7a5bdfb32be252c9ced0f47ed71c7ba4cde3` |
| Prompt v0.2 | `f62170fcfab44a74c153f1c0af5195acf227ab2c8d2acce28178792890e82c4e` |
| Prompt v0.3 | `c47e886be0d40abd5f42241eee9b8f6aa89d16c95036ca546da4f47d5ad18b7e` |
| Phase 2.4 protected-assets manifest | `4e157fc3548beacff5856976e24d10544c5773eae04106a2952ceb72ffacb901` |
| 当前生产默认 | `QuestionBankAgent`，保持不变 |

## 前端真实链路

文本/上传文档、Resume/JD/可选 Experience 创建与解析、PrepPackage 创建与读取、25 题读取、真实 question DB ID 练习、Evaluation 创建/读取/历史和 AgentRun 读取全部经类型化 API client。所有响应经 Zod 运行时校验；real 模式不发送 Mock header 或读取 scenario 参数。

## 同步与轮询语义

现有 create/parse/prep/evaluation POST 在 Agent 完成后才响应。等待期间只显示不确定进度、取消入口和超时恢复，不伪造后台步骤。取得 `agent_run_id` 后只在状态为 pending/running 时轮询，terminal 状态、路由离开、取消或超时立即停止；GET 可按 Retry-After 或有上限退避恢复，POST 永不自动重放。

## CORS 与上传

CORS 使用环境变量精确 allowlist，禁止 wildcard，credentials 默认关闭。上传只允许 `.pdf`、`.docx`、`.txt`，默认 10 MiB，可由环境变量覆盖；服务端依据扩展名、受控 MIME 和解析结果裁决，422 不保留残余文件且不回显内容。

## 合同停止规则

当前 OpenAPI 必须重新生成并与 Phase 2.5A 哈希比较。任何漂移先分类为兼容或破坏性并停止，不覆盖冻结快照。不得用 `z.unknown()` 或宽松 Schema 隐藏不兼容。
