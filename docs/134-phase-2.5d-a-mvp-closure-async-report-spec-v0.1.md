# Phase 2.5D-A MVP 缺口收口、异步工作流与 Markdown 合同 Spec v0.1

## 1. 状态与范围

本阶段目标状态为 `awaiting_phase_2_5d_b_implementation_authorization`。本阶段只完成只读审计、架构决策、proposed contract 和实施计划，不实现代码、数据库迁移、Worker、前端改动或新 Prompt。

本阶段没有 Provider call，没有真实网络访问，也不改变当前同步 API 行为。

## 2. 冻结基线

| 资产 | Phase 2.5D-A 开始时 SHA-256 / 状态 |
|---|---|
| Phase 2.5A OpenAPI | `e983971aec77ddaf246efbb80637134f4fd41bfb9302fa2f3d06122430977304` |
| Phase 2.5C local integration manifest | `2d61326fd5c158391e7c7ac28449643029c98169300778a5bc926ebf8dc04bfd` |
| 当前 `frontend/package-lock.json` | `48e80128e017f21c2938ee714bf580abd02e5a82a63b629aeb672b398205c285` |
| production `QuestionBankAgent` | `cefd190638efe3b1a4c4ce967907c10ef9b183cf47cf40b827d42ae816912bda` |
| Phase 2.4 protected-assets manifest | `4e157fc3548beacff5856976e24d10544c5773eae04106a2952ceb72ffacb901` |
| Prompt v0.1 | `125a90d896d481b616955da5aebf7a5bdfb32be252c9ced0f47ed71c7ba4cde3` |
| Prompt v0.2 | `f62170fcfab44a74c153f1c0af5195acf227ab2c8d2acce28178792890e82c4e` |
| Prompt v0.3 | `c47e886be0d40abd5f42241eee9b8f6aa89d16c95036ca546da4f47d5ad18b7e` |
| 当前迁移 head | `c72e3f4a5b6c`，本阶段不新增迁移 |
| 当前生产默认 Agent | `QuestionBankAgent` |
| 当前长任务 API | 同步等待 Agent 完成后返回 |

## 3. 事实源

审计以以下内容为事实源：

1. `docs/01-prd-v0.2.md`。
2. `docs/13-first-phase-mvp-feature-spec-v0.1.md`。
3. `docs/11-development-roadmap-v0.1.md`。
4. Phase 2.5A 冻结 OpenAPI 和 API contract matrix。
5. 当前 SQLAlchemy model、FastAPI route/service、React 页面/API client 和自动化测试。
6. Phase 2.5C local integration manifest 与验证报告。

历史 release note 只证明当时实现状态。若历史声明与当前代码或更晚冻结合同不一致，以当前实现和冻结合同为准，并记录 `document_conflict`。

## 4. 审计结论

当前系统已经实现并验证材料输入、Resume/JD/面经结构化解析、MatchReport、8/8/9 题库、单题评价、degraded/no-score 安全语义、条件式长期记忆写入、AgentRun 查询以及本机 React 闭环。

当前 MVP 仍不能声明全部完成，主要缺口为：

1. 完整备战包的九章节没有作为一个完整资源返回或展示。
2. 没有正式的备战要点手册数据合同和持久化结果。
3. 推荐先练 3 题虽入库，但选择逻辑较弱，且当前 API/前端只暴露计数，没有返回推荐列表与原因。
4. `rendered_markdown` 列已存在，但没有 renderer、生成合同或下载 API。
5. 长耗时 POST 在 HTTP 请求内同步执行；AgentRun 不是持久化工作队列。
6. 长期记忆能安全写入，但没有读取 API，也没有证据证明它已进入后续题目推荐。
7. 默认用户、无认证、无资源所有权校验的模式只适用于本机或受控私有演示。

## 5. Phase 2.5D-B 拟解决的范围

在获得单独授权后，Phase 2.5D-B 可以实现：

1. 数据库持久化 `workflow_jobs` 与独立 Worker。
2. 新增显式异步 job endpoint，保留现有同步 endpoint。
3. 以资源 ID 为主的 job payload、lease/heartbeat/recovery、幂等与取消。
4. 完整备战包读取合同，补齐手册、推荐题、行动清单的确定性组装。
5. 确定性 Markdown materialization、查看与下载。
6. React 从同步 submit 迁移到 `202 → job → polling → resource`。
7. 新 OpenAPI/Mock/Zod/Playwright 版本，不覆盖 Phase 2.5A。

鉴权、多用户隔离、Docker、CI/CD、云部署和真实 Provider staging 不包含在 Phase 2.5D-B 默认范围内，除非另行授权。

## 6. 验收原则

1. 现有同步 endpoint 的请求和响应保持兼容。
2. 新异步合同必须可在 Provider 不可用时正确表达 `degraded` 成功结果。
3. Worker 至少一次执行不得造成重复业务资源。
4. 用户重复提交与 Worker retry 分别记账。
5. 报告只从已持久化业务数据生成，Provider calls 增量为 0。
6. Job 和报告中不保存 Prompt、CoT、原始 Provider 响应、原始异常正文或服务端绝对路径。
7. 无认证模式仍禁止公网部署。

## 7. 本阶段停止点

文档与机器可读 decision manifest 完成并验证后停止，状态写为 `awaiting_phase_2_5d_b_implementation_authorization`。该状态不授权创建迁移、安装队列依赖、启动 Worker 或修改前后端。
