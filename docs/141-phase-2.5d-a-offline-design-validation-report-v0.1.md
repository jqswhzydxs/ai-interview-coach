# Phase 2.5D-A Offline Design Validation Report v0.1

## 1. 最终状态

`awaiting_phase_2_5d_b_implementation_authorization`

本阶段只新增设计文档和机器可读 decision manifest。没有修改应用代码、前端代码、数据库迁移、package lock、Prompt、Agent 或历史实验资产。

## 2. 审计覆盖

已对照检查：

- PRD v0.2。
- 第一阶段 MVP Feature Spec。
- Development Roadmap。
- Phase 2.5A OpenAPI 的 16 个 operation。
- 当前 11 类核心 ORM model。
- FastAPI route/service/AgentRun/Memory 实现。
- React route、API client、processing/AgentRun 页面和测试。
- Phase 2.5C local integration manifest 与 510 项后端、30 项 Vitest、15 项 Playwright 既有证据。

Traceability matrix 共 36 项：

| 状态 | 数量 |
|---|---:|
| `implemented_and_verified` | 18 |
| `partially_implemented` | 8 |
| `missing` | 4 |
| `intentionally_deferred` | 4 |
| `document_conflict` | 2 |

因此没有将现有前端页面或 Phase 2.5C 本机 E2E 解释为 MVP 已全部完成。

## 3. 设计决策验证

| 检查 | 结果 |
|---|---|
| 长任务不使用 BackgroundTasks 作为默认生产方案 | passed |
| 四种异步方案按 10 个维度评分 | passed |
| DB queue + 独立 Worker 的推荐有当前栈证据 | passed；61/70 |
| SQLite 限定为单 Worker 本地/测试 | passed |
| Job payload 优先只保存资源 ID | passed |
| Worker retry、Provider retry、用户重提区分 | passed |
| lease/heartbeat/reaper/crash recovery | passed |
| 至少一次执行和业务写入幂等 | passed |
| degraded 表达为 succeeded outcome | passed |
| Idempotency-Key、Location、Retry-After | passed |
| 取消和 absolute deadline | passed |
| Markdown 不新增 Provider/Prompt | passed |
| stable sections/hash/atomic write/download | passed |
| 不返回绝对路径 | passed |
| 前端 refresh 只 GET、不重放 POST | passed |
| OpenAPI/Zod/MSW/Playwright/visual 版本化 | passed |
| 默认用户公网部署 gate | passed |

## 4. 关键结论

1. 完整备战包、手册、推荐 3 题的产品化和 Markdown 导出仍是 MVP 缺口。
2. AgentRun 是执行可观测记录，不是 durable workflow queue。
3. 推荐数据库持久化队列加独立 Worker；Redis/Celery 是规模化备选。
4. 推荐新增显式 `/workflow-jobs`，迁移期保留现有同步 API。
5. 不推荐 `Prefer: respond-async` 作为首版，因为它使同一路径出现两套成功响应模型。
6. 备战手册应确定性组装；来源不足时显式 incomplete/degraded，不重复或编造。
7. Markdown 是收口项，PDF 继续 deferred。
8. 无认证/default-user 模式只允许本机或受控私有演示。

## 5. 离线边界

- Provider calls：0。
- 真实网络请求：0。
- 新依赖安装：0。
- 新数据库迁移：0。
- Worker 启动：0。
- 代码/前端改动：0。
- Phase 2.5A 快照覆盖：0。

## 5.1 验证执行结果

| 检查 | 结果 |
|---|---|
| decision manifest JSON 解析与 deliverable 路径 | passed；8 个文档均存在 |
| traceability matrix 计数 | passed；36 项，状态分布 18/8/4/4/2 |
| async/report 必需合同字段 | passed |
| 新增文档 trailing whitespace | passed |
| Phase 2.4 共 30 个冻结资产逐文件哈希 | passed；1 test |
| Phase 2.5A、2.5C、package-lock、Agent、Prompt 哈希 | unchanged |
| migration 文件数量与 SHA-256 | unchanged；3 个 migration |
| `git diff --check` | passed；只有既有 Windows LF/CRLF 提示，无 whitespace error |

## 6. 冻结资产复核

完成设计文件后复核以下值保持不变：

- Phase 2.5A OpenAPI：`e983971aec77ddaf246efbb80637134f4fd41bfb9302fa2f3d06122430977304`。
- Phase 2.5C manifest：`2d61326fd5c158391e7c7ac28449643029c98169300778a5bc926ebf8dc04bfd`。
- package-lock：`48e80128e017f21c2938ee714bf580abd02e5a82a63b629aeb672b398205c285`。
- production QuestionBankAgent：`cefd190638efe3b1a4c4ce967907c10ef9b183cf47cf40b827d42ae816912bda`。
- Phase 2.4 protected-assets manifest：`4e157fc3548beacff5856976e24d10544c5773eae04106a2952ceb72ffacb901`。
- migration head 及三个 migration 文件不变。

## 7. 下一步

机器可读 decision manifest 位于 `contracts/architecture/phase-2.5d-a-v0.1/decision-manifest.json`，SHA-256 为 `c3962c481bfa88108fa21d71a3fad05213f5420a19bd60dabf31e9f2529df862`。

等待用户明确授权 Phase 2.5D-B。授权前不得创建 migration、Worker、异步 endpoint、Markdown renderer 或前端迁移实现。
