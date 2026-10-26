# Phase 2.5D-A Async Workflow Architecture ADR v0.1

## ADR-025D-A-01

- 状态：`proposed_for_phase_2_5d_b`
- 决策：采用数据库持久化任务队列加独立 Worker。
- 实施授权：本阶段未授权。

## 1. 上下文

当前 resume/JD/experience parse、PrepPackage create 和 Evaluation create 都在 FastAPI 请求生命周期内等待 Agent 完成。Phase 2.5C 前端只能显示不确定进度和取消本地请求；响应返回的 AgentRun 通常已是 terminal。HTTP 断开、API 进程退出、Worker retry、用户取消和任务恢复没有独立持久化语义。

现有系统已经使用 SQLAlchemy、Alembic、PostgreSQL 设计和 SQLite 测试，并将 AgentRun、业务输入与业务结果写入数据库。MVP 要求优先控制部署成本和敏感数据复制。

## 2. 评价方法

评分为 1–5，5 表示最符合当前需求。持久性、崩溃恢复、至少一次/幂等和敏感数据边界权重为 2，其余权重为 1。总权重 14，满分 70。

| 维度 | 权重 | DB 持久化队列 + Worker | Celery/RQ + Redis | FastAPI BackgroundTasks | 进程内 asyncio task |
|---|---:|---:|---:|---:|---:|
| 任务持久性 | 2 | 5 | 5 | 1 | 1 |
| 进程崩溃恢复 | 2 | 5 | 5 | 1 | 1 |
| 至少一次执行与幂等 | 2 | 4 | 5 | 1 | 1 |
| PostgreSQL/SQLite 兼容 | 1 | 4 | 4 | 5 | 5 |
| 部署复杂度，分高表示简单 | 1 | 3 | 2 | 5 | 5 |
| 可观测性 | 1 | 4 | 5 | 2 | 1 |
| 取消与超时 | 1 | 4 | 4 | 1 | 2 |
| 敏感数据边界 | 2 | 5 | 4 | 3 | 2 |
| 单机 MVP 成本，分高表示低成本 | 1 | 4 | 2 | 5 | 5 |
| 后续水平扩展 | 1 | 4 | 5 | 1 | 1 |
| 加权总分 | 70 | **61** | **60** | **31** | **29** |
| 百分比 | 100% | **87.1%** | **85.7%** | **44.3%** | **41.4%** |

## 3. 方案分析

### 3.1 数据库持久化队列 + 独立 Worker

优点：

1. 与现有数据库事务、资源 ID 和 SQLAlchemy/Alembic 直接结合。
2. Job payload 可以只保存 domain resource ID，避免将完整简历、JD、面经或回答再复制到 Redis message。
3. API enqueue、idempotency record 和初始 domain resource 可以在同一事务提交。
4. 单机 MVP 只增加一个 Worker 进程，不增加 Redis 运维面。
5. PostgreSQL 可用 `FOR UPDATE SKIP LOCKED` 安全 claim；后续可增加多个 Worker。

限制：

1. 需要自行实现 claim、lease、heartbeat、backoff、dead-letter 状态和指标。
2. SQLite 不具备 PostgreSQL 同等级的并发 claim 能力，只能作为单 Worker 本地/测试兼容路径。
3. 水平扩展能力低于成熟的 Celery broker 生态。

### 3.2 Celery/RQ + Redis

优点是成熟的 Worker、重试、调度和监控生态，适合大量任务和多节点扩展。缺点是增加 Redis、队列序列化与第二份敏感 payload 生命周期；仍需数据库幂等和业务状态，不能只依赖 broker ack。当前单机 MVP 的运维成本略高于收益，因此作为规模化备选方案。

### 3.3 FastAPI BackgroundTasks

任务依附 API 进程，不提供可靠持久性、跨重启恢复、租约或完整取消。它适合短小的响应后副作用，例如发送非关键通知，不适合长时间真实 LLM 工作流。明确拒绝将其作为默认生产方案。

### 3.4 进程内 asyncio task

实现简单，但任务只存在内存中，进程退出即丢失；多 worker 环境无法统一 claim，刷新和重启后难以恢复。仅适用于测试或非关键临时工作，不进入正式合同。

## 4. 决策

Phase 2.5D-B 默认采用 PostgreSQL/数据库持久化队列加独立 Worker。SQLite 只支持单 Worker 的开发和自动化测试，不承诺多进程并发正确性。正式共享环境必须使用 PostgreSQL。

Celery/RQ + Redis 保留为后续吞吐量或调度复杂度达到阈值后的替代实现。更换队列基础设施不得改变对外 Workflow Job 合同。

## 5. 内部数据设计

建议新增 `workflow_jobs` 和 `workflow_job_attempts`：

### 5.1 workflow_jobs

- `id`
- `user_id`
- `workflow_type`
- `status`: queued/running/succeeded/failed/cancelled
- `outcome_mode`: nullable standard/degraded
- `progress_stage` 和受控 `progress_code`
- `input_resource_type`、`input_resource_id`
- `request_fingerprint`
- `idempotency_key_digest`，不保存原始 key
- `attempt_count`、`max_attempts`、`available_at`
- `lease_owner_id`、`lease_expires_at`、`heartbeat_at`
- `cancel_requested_at`
- `safe_failure_category`、`safe_failure_code`
- `result_resources_json`、关联 AgentRun ID
- `created_at`、`started_at`、`finished_at`、`updated_at`

Job payload 优先使用 `input_resource_type/id`。用户正文先进入已有或新建 domain input resource，再由 job 引用。Job 行不保存完整输入、完整输出、Prompt、CoT、Provider 原始响应或原始异常正文。

### 5.2 workflow_job_attempts

记录 Worker 层 attempt：attempt number、worker ID、claim/start/heartbeat/finish、结果状态和安全失败分类。它与 Provider retry 分开：

- `workflow_jobs.attempt_count` 表示 Worker 对整个 workflow 的执行次数。
- `AgentRun.retry_count` 表示 Agent/Provider 内部重试。
- 用户重新提交通过新的 Idempotency-Key 表达，不增加旧 job 的 attempt_count。

## 6. Claim、lease 与恢复

1. API 在事务中创建 input resource、job 和 idempotency record。
2. PostgreSQL Worker 用 `SELECT ... FOR UPDATE SKIP LOCKED` claim `queued` 且 `available_at <= now` 的任务。
3. claim 时将状态设为 `running`，设置有限 lease 并递增 Worker attempt。
4. Worker 周期性 heartbeat，续租不得超过任务绝对 deadline。
5. reaper 只回收 lease 已过期且 heartbeat 陈旧的任务；attempt 未达上限则重新 queued，达到上限则 failed。
6. Worker 每个可取消 stage 前检查 `cancel_requested_at`。
7. 已成功 job 永不重新 claim；业务结果以 `workflow_job_id` 唯一约束或 operation ledger 保证只写一次。
8. Worker 完成业务写入、result link 和 terminal 状态必须在可证明一致的事务边界内提交。

SQLite 测试路径使用进程级单 Worker 和原子状态条件更新；不得用它证明多 Worker claim 正确性。

## 7. 至少一次与副作用幂等

队列提供至少一次执行，不承诺 exactly-once。每个 stage 必须满足以下之一：

1. 纯读取或确定性计算，可安全重复。
2. 写入包含 `workflow_job_id + stage` 唯一键，重复执行读取已有结果。
3. 外部 Provider 调用前后有 attempt ledger；若调用结果未知，不自动假定未发生，也不把未知 usage 记为 0。

成功创建的 PrepPackage、Evaluation、Report 不得因 Worker 重启重复插入。若 job 在“外部调用成功、数据库提交前”崩溃，恢复逻辑必须用 stage ledger 与稳定 resource identity 决定重放或人工失败，而不是盲目再调用。

## 8. 取消与超时

- queued：取消立即变为 `cancelled`，不会被 claim。
- running：记录 cancellation request；在 stage 边界协作取消。已发出的 Provider HTTP 请求可尝试 Abort，但合同不承诺 Provider 已停止计费。
- terminal：取消返回冲突，不回滚已提交结果。
- deadline：每个 workflow 有绝对 deadline；超时属于安全 failure category。是否 Worker retry 由 workflow policy 决定。
- cancelled 和 failed 不返回业务成功链接；degraded 使用 `succeeded + outcome_mode=degraded`。

## 9. 可观测性与安全

Job 聚合一个或多个 AgentRun ID，但不复制 AgentRun 的敏感 summary。日志只允许 job ID、workflow type、stage、status、attempt、延迟、受控 failure category 和 request ID。Worker identity 使用非敏感实例 ID。

用户可见失败不包含堆栈、Provider 错误正文、请求正文、Prompt、响应或凭据。内部调试仍遵守现有安全日志策略。

## 10. 决策后果

正面后果是任务可刷新恢复、进程崩溃后可重试、前端不必维持长 HTTP、敏感正文不在队列中复制。成本是增加数据库模型、迁移、Worker lifecycle、reaper、幂等测试和运维监控。

本 ADR 只确认设计方向；实现必须等待 Phase 2.5D-B 授权。
