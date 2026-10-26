# Phase 2.5A 前端 API 契约与 Mock 设计 Spec v0.1

## 目标与状态

本阶段把当前 FastAPI 对外接口、降级语义和 QuestionBank 最终结构冻结为可供前端实现使用的离线合同。状态为 `offline_contract_design_complete`；未创建前端脚手架，未安装 npm 依赖，Provider calls 为 0，生产 `QuestionBankAgent` 未改变。

技术栈推荐仍处于 `awaiting_explicit_user_confirmation`。只有用户确认后才能进入 Phase 2.5B。

## 冻结语义

前端必须直接遵守以下后端语义：

- `source_quality`：展示数据来源可信度；不得被客户端推测覆盖。
- `score_available`：为 `false` 时，`total_score` 必须为 `null`，维度分为空；界面显示“本次无法提供可信分数”。
- `evaluation_mode`：只区分当前合同中的 `standard` 与 `degraded`。
- `degradation_reasons`：评价级结构化降级原因。
- `execution_mode`：Agent 运行的 `mock`、`real` 或 `fallback` 模式。
- `fallback_reason`：Agent 运行级结构化原因；由前端映射为可理解文案，不展示原始异常。
- nullable score：`null` 表示不可用，不能转成 `0`。
- memory-write blocked：降级或不可信来源不得写入长期记忆；现有显式 `memory_update.write_decision=skip` 可展示为未写入。
- QuestionBank 最终 API Schema、题目稳定 ID、模块、顺序与 8/8/9 数量保持不变。

Prompt v0.3 的唯一允许状态为 `research_candidate_not_promoted`。Mock、路由和组件不得把它当成产品默认能力。

## 合同层级

1. `openapi.json` 是当前 FastAPI OpenAPI 的规范化快照。
2. 当前路由请求模型和路径参数以 OpenAPI/Pydantic 为准。
3. 运行时响应使用现有 `SuccessResponse` 或 `ErrorResponse` envelope。
4. 评价正文继续受 `AnswerEvaluation` 校验，题库继续受 `QuestionBank` 校验。
5. Mock 的 UI 控制字段位于 fixture harness 外层，不得混入后端 response body。

## 已知合同缺口

当前路由大多声明返回 `dict`，因此 OpenAPI 对成功响应只暴露通用 object；运行时实际结构比 OpenAPI 更严格。以下项目只记录为 proposal，本阶段不实施：

- 为现有 payload 补充显式 `response_model`；
- 在 OpenAPI 中声明运行时 `ErrorResponse`、404 和 502；
- 如果产品需要精确展示 guard 行为，新增结构化 memory-write outcome；
- 由后端冻结文件大小与 MIME 上限，再绑定客户端预校验；
- 明确创建接口的轮询或异步 job 语义。当前实现会等待 Agent 流程完成。

## 验收条件

- 16 个 OpenAPI operation 全量进入矩阵。
- 快照规范化、可重复生成并记录 SHA-256。
- 12 个必需 Mock 场景全部通过 OpenAPI 路径、请求 Pydantic、响应 envelope 和业务 Schema 校验。
- standard/degraded/fallback/memory-blocked 语义互不混用。
- 不包含真实个人数据、凭据、完整 Prompt、CoT 或原始 Provider 响应。
- 后端全量与迁移测试不回退；冻结实验资产哈希不变。

