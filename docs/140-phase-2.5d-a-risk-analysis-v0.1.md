# Phase 2.5D-A Risk Analysis v0.1

## 1. 风险登记

| 风险 | 影响 | 设计控制 | Phase 2.5D-B 停止条件 |
|---|---|---|---|
| 至少一次执行造成重复 PrepPackage/Evaluation | 重复数据、额外 Provider 成本 | originating job 唯一键、stage ledger、事务化 finalization | 无法证明 crash/retry 下结果只写一次 |
| 用户双击与 Worker retry 混淆 | 重复 job 或错误 attempt 指标 | Idempotency-Key、request fingerprint、独立 attempt 模型 | 同一 key 可生成多个 job |
| API 进程承担长任务 | 重启丢任务 | 独立 Worker、持久化 queue | 使用 BackgroundTasks/内存 task 作为正式路径 |
| SQLite 多 Worker 误用 | claim 竞争、重复执行 | SQLite 只允许单 Worker 测试；生产 PostgreSQL | 用 SQLite 并发测试结果宣称 production safety |
| lease/heartbeat 错误回收活任务 | 并发执行同一任务 | lease token、条件更新、stale heartbeat 门槛 | 两个 Worker 同时拥有有效 lease |
| Provider 成功但 DB 提交前崩溃 | 重复调用、账单不完整 | provider attempt ledger、稳定 stage ID、未知 usage 保留 unknown | 恢复逻辑盲目重放外部调用 |
| 取消被描述为 Provider 未计费 | 误导用户 | cooperative cancel；明确已发请求可能继续 | UI 声称强取消外部 Provider |
| degraded 被标成 failed | 丢失安全可用结果 | `status=succeeded + outcome_mode=degraded` | degraded 进入通用错误页或写入不可信分数 |
| Job payload 复制敏感正文 | 扩大泄露面 | payload 仅 resource ID；正文存在受控 domain record | workflow_jobs/日志出现完整简历、JD、回答 |
| 失败字段泄露异常或密钥 | 安全事件 | allowlist category/code、request ID；不持久化 exception message | API/日志含原始异常、Prompt、response、secret |
| 手册为满足 8/6 而编造或重复 | 内容质量和诚信失败 | 去重、evidence、completeness/degraded | 无来源条目被生成或同义重复凑数 |
| Markdown 注入/raw HTML | 浏览器 XSS 或恶意链接 | escape、raw HTML disabled、link scheme allowlist | viewer 执行用户 HTML/script |
| 报告文件路径泄露或逃逸 | 服务器信息泄露/任意写 | ASCII 名称、resolved root、相对 storage key、原子写 | API 返回绝对路径或可写出 report root |
| GET 隐式生成报告 | 不可预期副作用 | materialize 使用显式 POST；GET 只读 | GET 触发写入或 Provider call |
| 旧同步合同被破坏 | Phase 2.5A/2.5C 回归 | additive endpoint、新快照、同步回归 | 原 endpoint response/status 改变 |
| 前端刷新自动重放 POST | 重复业务/成本 | job ID deep link、刷新只 GET | reload 产生新 job |
| 轮询无限运行 | 资源浪费、糟糕 UX | terminal stop、bounded interval、客户端暂停门槛 | terminal 后仍 polling |
| 固定默认用户公开使用 | 任意人读取/覆盖他人数据 | 本机/私有演示 gate | 未有 auth/ownership 即公网部署 |
| 本机 E2E 被解释为 production ready | 错误上线决策 | 单独 deployment gate | 以 loopback 结果替代安全/容量/恢复验收 |

## 2. 部署门禁

当前系统使用固定 `DEFAULT_USER_ID`，没有登录、认证、会话、租户或资源 ownership enforcement。评价列表、资源详情和生成接口依赖默认用户或直接按 ID 读取。因此：

1. 当前模式只允许 localhost 或访问受控的私有演示环境。
2. 在增加认证、授权、每次查询/写入的用户隔离、对象级访问校验和安全测试之前，禁止公网部署。
3. CORS allowlist 不是身份认证，无法替代授权。
4. 随机 UUID 不是访问控制。
5. 下载报告同样必须在公网前加入 ownership 校验和审计。

## 3. 非本阶段事项

以下工作不属于 Phase 2.5D-A，也不因本 ADR 获得授权：

- Docker 或容器编排。
- CI/CD。
- 云部署。
- Redis/Celery 安装。
- 真实 Provider staging。
- 鉴权和多用户实现。
- production QuestionBankAgent 切换。
- Prompt 或模型实验。

## 4. production readiness 判定

即使 Phase 2.5D-B 完成，项目仍只能声明“异步 MVP 合同和本机实现已验证”。要声明 production ready，至少还需：

1. 身份认证与资源隔离。
2. PostgreSQL 多 Worker claim/lease 压力和故障测试。
3. secret management、备份恢复和审计策略。
4. 受控真实 Provider staging 与成本/配额/故障门禁。
5. 部署、监控、告警和数据保留政策。

Phase 2.5C 本机 E2E 只证明 loopback 合同联调，不满足以上门禁。
