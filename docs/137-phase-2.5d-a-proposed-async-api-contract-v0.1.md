# Phase 2.5D-A Proposed Async API Contract v0.1

## 1. 合同状态

本文件是 `proposed contract`，不修改 Phase 2.5A OpenAPI，不代表 endpoint 已存在。若 Phase 2.5D-B 获得授权，应生成新的 OpenAPI/Mock contract 版本并保留 Phase 2.5A 快照。

推荐兼容策略：在现有 `/api/v1` 下新增显式 Workflow Job endpoint，现有同步 endpoint 保持原语义。不要在同一 endpoint 上根据 `Prefer: respond-async` 返回两种不兼容 body，也不要在迁移期把现有 200/同步响应直接改为 202。

## 2. Workflow 类型

建议第一批支持：

- `resume_parse`
- `job_description_parse`
- `interview_experience_parse`
- `prep_package_generation`
- `answer_evaluation`

Markdown materialization 是确定性本地计算，默认走独立同步报告 endpoint，不占用 LLM Worker。若未来报告变得昂贵，可以新增 workflow type，但不得与本合同暗中混用。

## 3. 输入资源策略

`POST /api/v1/workflow-jobs` 使用按 `workflow_type` 判别的严格 oneOf request。Job 数据库 payload 只保留资源引用。

示意请求：

```json
{
  "contract_version": "phase-2.5d-v0.1",
  "workflow_type": "prep_package_generation",
  "input_resource": {
    "resource_type": "prep_package_request",
    "resource_id": "00000000-0000-4000-8000-000000000901"
  }
}
```

`prep_package_request` 应在 enqueue 事务内保存 resume/job/experience resource ID、准备目标和标题。完整简历、JD、面经正文继续只存在各自业务资源，不复制到 workflow_jobs。

`answer_evaluation` 应引用持久化的 `answer_submission_id`。用户回答属于业务数据，可以进入受访问控制的 submission/evaluation resource；不得复制进 job payload、日志或 idempotency fingerprint 明文。

## 4. 创建 Job

### 4.1 Request

```http
POST /api/v1/workflow-jobs
Idempotency-Key: <16-128 characters>
Content-Type: application/json
```

Idempotency-Key 必填。服务端只保存 key 的带服务端 secret digest，并以 `(user_id, workflow_type, key_digest)` 唯一。request fingerprint 由规范化后的非敏感 resource refs、workflow type 和 contract version 计算。

### 4.2 Response

```http
HTTP/1.1 202 Accepted
Location: /api/v1/workflow-jobs/00000000-0000-4000-8000-000000000902
Retry-After: 2
```

```json
{
  "data": {
    "workflow_job_id": "00000000-0000-4000-8000-000000000902",
    "contract_version": "phase-2.5d-v0.1",
    "workflow_type": "prep_package_generation",
    "status": "queued",
    "outcome_mode": null,
    "progress": {
      "stage": "queued",
      "stage_index": 0,
      "stage_count": 5,
      "message_code": "workflow_queued"
    },
    "attempt_count": 0,
    "cancellation_requested": false,
    "safe_failure": null,
    "created_at": "2026-10-26T00:00:00Z",
    "started_at": null,
    "heartbeat_at": null,
    "finished_at": null,
    "result_resources": [],
    "agent_run_ids": [],
    "links": {
      "self": "/api/v1/workflow-jobs/00000000-0000-4000-8000-000000000902",
      "cancel": "/api/v1/workflow-jobs/00000000-0000-4000-8000-000000000902/cancel"
    }
  },
  "meta": {
    "request_id": "safe-request-id"
  }
}
```

同一个 key 与同一个 fingerprint 重放时返回已有 job，并设置 `Idempotency-Replayed: true`；active job 返回 202，terminal job 返回 200。相同 key 配不同 fingerprint 返回安全的 409，且不创建第二个 job。

## 5. Job 读取

```http
GET /api/v1/workflow-jobs/{workflow_job_id}
```

状态只允许：

- `queued`
- `running`
- `succeeded`
- `failed`
- `cancelled`

`queued` 或 `running` 必须返回 `Retry-After`。建议初始 2 秒，服务端可在 1–10 秒内调整。terminal response 不返回 Retry-After。

### 5.1 outcome_mode

- 非 terminal：`null`
- 标准业务成功：`status=succeeded, outcome_mode=standard`
- 安全降级业务结果：`status=succeeded, outcome_mode=degraded`
- failed/cancelled：`null`

degraded 不得标为 failed。其 `result_resources` 仍可使用，并通过资源自身的 `source_quality`、`evaluation_mode`、`degradation_reasons` 或 `fallback_reason` 解释来源。

### 5.2 Progress

Progress 只表达已持久化 stage，不伪造 token streaming 或 Provider 内部推理：

```json
{
  "stage": "question_bank",
  "stage_index": 4,
  "stage_count": 5,
  "message_code": "generating_question_bank"
}
```

前端根据受控 `message_code` 映射用户文案。Job 不保存自由格式 Provider 消息。

### 5.3 Result resource links

```json
[
  {
    "rel": "prep_package",
    "resource_id": "00000000-0000-4000-8000-000000000903",
    "href": "/api/v1/prep-packages/00000000-0000-4000-8000-000000000903"
  }
]
```

只允许同源相对 API 路径。不得返回数据库 DSN、服务器文件路径或第三方 URL。

## 6. 安全失败合同

```json
{
  "category": "provider_timeout",
  "code": "workflow_dependency_timeout",
  "retryable_by_user": true
}
```

建议 category allowlist：

- `validation`
- `dependency_missing`
- `provider_timeout`
- `provider_network`
- `provider_rate_limit`
- `provider_auth`
- `schema`
- `deadline`
- `worker_crash_recovery_exhausted`
- `cancelled`
- `internal`

不得返回 exception message、堆栈、Prompt、请求/响应正文、Authorization、API key、CoT 或 reasoning content。HTTP error envelope 延续既有安全 `request_id` 语义。

## 7. AgentRun 关联

`agent_run_ids` 按产生顺序保存 UUID。Job 是跨 Agent 的工作流状态；AgentRun 是某个 Agent 执行和 Provider/fallback 可观测记录。两者不相互替代。

Worker retry 可能产生新的 AgentRun；不得覆盖历史 run。Provider retry 仍记录在对应 AgentRun。Job response 不返回 AgentRun 的 input/output summary 或 raw error。

## 8. 取消合同

```http
POST /api/v1/workflow-jobs/{workflow_job_id}/cancel
Idempotency-Key: <cancel-operation-key>
```

- queued：原子变为 cancelled，返回 200。
- running：记录 cancellation request，返回 202；Worker 在安全 stage 边界变为 cancelled。
- cancelled：幂等返回 200。
- succeeded/failed：返回 409 `workflow_already_terminal`。

取消不会删除输入资源、AgentRun 或审计记录。已发出的 Provider 请求尽力 abort，但合同不声称 Provider 已停止处理或计费。

## 9. Worker lease、heartbeat 和 timeout

这些字段主要属于内部 Worker 合同，不对浏览器暴露 `lease_owner_id`：

1. claim 获得固定 lease。
2. Worker 周期 heartbeat。
3. reaper 只处理 lease 过期任务。
4. 回收后若 `attempt_count < max_attempts`，设置新的 `available_at` 并 queued。
5. 超过 max attempts 后 failed，category 为受控恢复耗尽。
6. 任务有绝对 deadline；heartbeat 不能无限延长 deadline。

公开 job response 只返回最近 `heartbeat_at`，用于用户判断仍在运行，不返回 Worker 主机名或内部拓扑。

## 10. 幂等和业务写入

1. enqueue 幂等防止用户双击或网络重试创建多个 job。
2. Worker stage 幂等防止至少一次执行重复创建 PrepPackage、Evaluation 或 Report。
3. 每个 terminal 业务资源保存其 originating `workflow_job_id` 或等价唯一 operation key。
4. 已 succeeded 的 job 在 Worker 重启后不可重新进入 running。
5. 前端不得对 create job POST 自动 retry；用户主动重试必须生成新 key，并明确创建新 job。

## 11. 兼容方案比较

| 方案 | 兼容性 | OpenAPI 清晰度 | 迁移成本 | 决策 |
|---|---|---|---|---|
| 保留同步 API，不增加异步 | 最高 | 清晰 | 低 | 无法满足恢复/取消，不采用 |
| 新增显式 `/workflow-jobs` | 高；原 endpoint 不变 | 单一响应语义 | 中 | **推荐** |
| 原 endpoint + `Prefer: respond-async` | 表面兼容，但同一路径出现 200/202 双模型 | 较差 | 中 | 不推荐作为首版 |
| 全量 `/api/v2` | 最清晰的破坏性边界 | 高 | 高 | 等待删除旧 endpoint 或引入鉴权时采用 |

## 12. 迁移路径

1. 新增数据模型、Worker 和 `/workflow-jobs`，现同步 endpoint 保持不变。
2. 生成 `phase-2.5d-b-v0.1` OpenAPI/Mock snapshot，不覆盖 Phase 2.5A。
3. React 仅对新流程使用 async endpoint；现同步 API 保留回归测试。
4. 完成双路径观测期后标记同步长任务 endpoint deprecated，但不立即删除。
5. 若未来要把原路径改为 202、加入认证或重构资源所有权，使用 `/api/v2` 并提供正式迁移窗口。

## 13. 非授权声明

本文件不授权实现 endpoint、创建迁移、启动 Worker、安装 Redis/Celery 或访问 Provider。
