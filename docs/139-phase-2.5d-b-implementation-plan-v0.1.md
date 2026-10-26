# Phase 2.5D-B Implementation Plan v0.1

## 1. 状态

状态：`proposal_only`。本计划不授权实施。Phase 2.5D-B 必须由用户单独授权后开始。

## 2. 实施顺序

### B1：冻结、迁移与队列核心

1. 再次验证 Phase 2.5A、2.5C、package-lock、Prompt、Agent、实验和迁移哈希。
2. 创建新的 migration，只新增 workflow job、attempt、idempotency 和必要的 report artifact/domain input 表或字段。
3. 实现 PostgreSQL claim/lease/heartbeat/reaper；SQLite 实现仅用于单 Worker 测试。
4. 建立 workflow registry、严格 payload ref schema、绝对 deadline、cancel 和安全失败分类。
5. 测试至少一次执行、崩溃恢复、lease 竞争、幂等业务写入和失败脱敏。

### B2：异步 Workflow

1. 为 resume/JD/experience parse 建 workflow handler。
2. 为 prep package generation 建组合 workflow，按持久化 stage 更新 progress。
3. 为 answer evaluation 建 workflow，并把用户回答先保存为受控 domain resource。
4. 保留当前同步 route 和 service 行为，新增 `/workflow-jobs`。
5. 明确 Worker retry、Provider retry 和用户重新提交三类计数。

### B3：完整备战包收口

1. 设计并实现完整 prep package read model。
2. 补齐 MatchReport、resume suggestions、priority、question bank、推荐 3 题、手册和 action items。
3. 推荐题使用稳定、可解释、去重的确定性规则；不得默认取前 3 题。
4. 手册按 8/6 规则检查 completeness；来源不足时 degraded，不编造。
5. 保持 QuestionBank 最终 API Schema 和生产 Agent 不变。

### B4：Markdown 报告

1. 实现版本化 deterministic renderer 和 source snapshot hash。
2. 实现 artifact idempotency、兼容 `rendered_markdown` 回写和原子文件缓存。
3. 实现 materialize/view/download endpoint。
4. 验证章节顺序、escaping、source quality、hash、Content-Disposition 和路径不泄露。
5. 证明 renderer Provider calls 为 0。

### B5：前端迁移

1. 提交页面完成便宜的 domain resource 创建后，只执行一次 Workflow Job POST。
2. 导航到 `/workflow-jobs/:workflowJobId`；URL 只保存 job ID。
3. job 页面 GET 恢复，queued/running 按 Retry-After bounded polling。
4. terminal 立即停止；session polling 超时只停止客户端轮询，不自动取消服务端 job。
5. failed/cancelled/degraded 使用独立状态和恢复动作。
6. result resource link 驱动跳转；不得在前端猜测资源 ID。
7. 新增完整备战包和 Markdown 查看/下载页面。

### B6：合同与验证

1. 创建 `phase-2.5d-b-v0.1` OpenAPI、Mock scenario、Zod 和生成类型。
2. 保持 Phase 2.5A 快照只读；记录兼容性 diff。
3. 添加 Worker 单元/集成/崩溃恢复、同步回归、前端组件和 Playwright 测试。
4. 更新视觉基线，覆盖 queued/running/succeeded/degraded/failed/cancelled/report incomplete。
5. 执行全量离线、迁移 upgrade/downgrade、compileall、diff-check、socket guard 和冻结哈希。

## 3. 前端状态机

```text
editing
  -> submitting_domain_resources
  -> submitting_job
  -> queued
  -> running
  -> succeeded_standard -> result
  -> succeeded_degraded -> degraded result
  -> failed -> retry decision
  -> cancelled
```

规则：

1. Job POST mutation retry=0；双击锁与 Idempotency-Key 同时生效。
2. 不自动重放 POST；任何再次提交必须来自明确用户动作并使用新的 Idempotency-Key。
3. 页面刷新只 GET job，不重新发送 POST。
4. polling 只在 queued/running；interval 尊重 Retry-After，缺失时从 2 秒指数退避到 10 秒。
5. 网络失败退避上限 15 秒；连续失败达到客户端门槛后暂停并显示手动恢复，不改变服务端 job。
6. cancellation 是显式用户操作；离开路由只停止本地 polling，不自动取消 job。
7. 浏览器只在 URL/session 内保存 job ID 和非敏感 navigation state；不在 localStorage 保存正文。
8. outcome degraded 不进入 error route，仍允许查看结果并显示来源说明。

## 4. 新合同的版本化影响

| 资产 | Phase 2.5D-B 动作 |
|---|---|
| OpenAPI | 新建快照与兼容性报告，不覆盖 Phase 2.5A |
| generated TypeScript | 从新快照生成；旧同步类型继续存在 |
| Zod | 新增严格 Job/Report schema，不使用 `z.unknown()` 掩盖响应 |
| MSW | 新增 queued/running/standard/degraded/failed/cancelled/idempotent replay/lease recovery 场景 |
| Playwright | 新增刷新恢复、取消、无 POST 重放、Retry-After、报告查看/下载 |
| visual baseline | 新目录或新版本名称；不覆盖 Phase 2.5C 基线 |
| package-lock | 若没有新增依赖应保持不变；任何变化单独记录 |

## 5. 推荐 API 迁移流程

1. Backend 先发布 additive job/report endpoint。
2. 前端通过显式环境或 build-time contract version 选择 async flow；不使用容易误开的全局生产 Agent 开关。
3. 同步 API 回归持续运行。
4. async E2E 稳定后，默认前端转到 async，但 backend sync endpoint 暂不删除。
5. 若要改变现有 route 语义，在后续 `/api/v2` 进行。

## 6. 数据迁移注意事项

1. 新表 migration 先 expand，不删除或修改当前字段。
2. `rendered_markdown` 保留为兼容缓存。
3. 历史 package 不自动生成报告；用户显式 materialize 时再创建 artifact。
4. 历史 AgentRun 不回填成 WorkflowJob。
5. 所有 downgrade 必须只删除新表/约束，不损坏既有业务数据。

## 7. 测试清单

- enqueue/idempotency same key same input。
- same key different input 409。
- user duplicate submit 与 Worker retry 分离。
- queued cancel、running cooperative cancel、terminal cancel conflict。
- lease expiry/reclaim、max attempt、stale heartbeat。
- crash before/after business commit。
- success resource exactly once。
- degraded 为 succeeded outcome。
- safe failure category 与无异常正文。
- payload 只含 resource refs。
- Markdown 稳定 bytes/hash/order/escaping。
- report underflow 不凑数且 degraded。
- atomic write 与无残留 temp。
- Content-Disposition/ETag/no absolute path。
- React refresh restore、terminal stop、route leave abort GET。
- no automatic POST replay。
- score unavailable/fallback/memory blocked 语义回归。
- provider calls=0 的报告生成测试。

## 8. 实施门禁

Phase 2.5D-B 完成不能自动授权公网部署。无认证/default user 模式仍只允许本机或受控私有演示。正式公网门禁见 Risk Analysis。
