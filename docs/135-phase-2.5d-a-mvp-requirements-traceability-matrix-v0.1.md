# Phase 2.5D-A MVP Requirements Traceability Matrix v0.1

## 1. 状态定义

| 状态 | 含义 |
|---|---|
| `implemented_and_verified` | 当前实现、对外路径与自动化证据均存在 |
| `partially_implemented` | 有模型、存储或局部 UI，但未满足完整业务验收 |
| `missing` | 需求明确，当前没有可用实现或合同 |
| `intentionally_deferred` | 文档明确排除或推迟，不能计入已完成 MVP |
| `document_conflict` | 不同事实源对范围或合同有冲突，需要正式决策 |

## 2. 需求追踪矩阵

| ID | 需求 | 主要来源 | 当前证据 | 状态 | 缺口或决策 |
|---|---|---|---|---|---|
| MVP-01 | 健康检查与基础服务 | Roadmap M1 | `GET /health`、集成测试 | `implemented_and_verified` | 无 |
| MVP-02 | 文本材料入库 | PRD 4.3；Feature 4 | `POST /documents/text`、真实 API E2E | `implemented_and_verified` | 敏感正文仍需鉴权后才能公网使用 |
| MVP-03 | PDF/DOCX/TXT 安全上传 | Feature 5.1；Phase 2.5C | `POST /documents/upload`、10 MiB/类型/残留清理测试 | `implemented_and_verified` | 当前冻结策略为 `.pdf/.docx/.txt` |
| MVP-04 | Markdown 文件上传 | PRD 4.3；Feature 4.1；Phase 2.5C 上传冻结策略 | 文本 endpoint 可承载 Markdown；`.md` 文件上传被当前白名单拒绝 | `document_conflict` | 需在未来合同版本决定恢复 `.md` 文件或明确仅支持粘贴 Markdown；本阶段不改 |
| MVP-05 | Resume 创建与结构化解析 | Feature 5.1；Roadmap M4 | create/parse endpoint、profile model、集成/E2E | `implemented_and_verified` | 当前 parse 同步等待 Agent |
| MVP-06 | JD 创建与结构化解析 | Feature 5.2；Roadmap M4 | create/parse endpoint、profile model、集成/E2E | `implemented_and_verified` | 当前 parse 同步等待 Agent |
| MVP-07 | 可选面经创建与结构化解析 | Feature 5.3；Roadmap M4 | create/parse endpoint、ExperienceProfile、E2E | `implemented_and_verified` | 不联网搜索，符合边界 |
| MVP-08 | Resume-JD 匹配与证据 | PRD 5.1；Feature 5.4 | `MatchReport`、匹配 Agent、持久化 source/evidence | `implemented_and_verified` | prep detail endpoint 未完整返回报告，计入 MVP-13 的组装缺口 |
| MVP-09 | 8/8/9 岗位题库 | PRD 5.2；Feature 5.5 | 25 题、三个模块、Schema、DB、API、真实 E2E | `implemented_and_verified` | production Agent 保持既有默认 |
| MVP-10 | 题目 purpose/difficulty/source/keywords/framework/STAR/anchors/follow-up/advice | PRD 5.2；Feature 5.5 | Question schema/model/API 与校验测试 | `implemented_and_verified` | 无 |
| MVP-11 | 面试备战要点手册 | PRD 5.3；Feature 5.6；Roadmap M5 | 没有 Prep Manual Agent、手册 schema、DB 字段或 API 资源 | `missing` | 推荐用持久化 MatchReport、priority、question metadata、action items 确定性组装，不增加 Prompt |
| MVP-12 | 推荐先练 3 题 | PRD 5.0；Feature 5.7 | DB 保存 3 条 `RecommendedQuestion` | `partially_implemented` | 当前固定取排序前 3 题、理由通用；prep detail 只返回 count，前端未展示推荐列表/入口 |
| MVP-13 | 完整九章节备战包 | PRD 5.0；Feature 5.7 | overview、MatchReport、priority、questions、recommended rows、action item 分散存在 | `partially_implemented` | 缺手册；detail API 只返回概览和计数；前端只呈现题库，没有九章节顺序 |
| MVP-14 | 简历改进建议 | PRD 5.1；完整包第 4 节 | MatchReport 中有 `resume_suggestions` 并持久化 | `partially_implemented` | 未由完整包 API/前端独立展示 |
| MVP-15 | 准备优先级 | 完整包第 5 节 | MatchReport priorities 写入 `priority_plan_json` | `partially_implemented` | 当前没有结构化读取/展示合同，ActionItem 信息不足 |
| MVP-16 | 下一步行动清单 | 完整包第 9 节 | DB 有 `action_items_json`，当前只生成一条通用项 | `partially_implemented` | 需基于持久化缺口/优先级确定性生成、去重和排序 |
| MVP-17 | Markdown 报告生成 | Feature 5.7/10/11；Roadmap M7 | DB 有 nullable `rendered_markdown`，无 renderer/生成服务/API | `missing` | Phase 2.5D-B 应实现确定性 renderer，Provider 增量 0 |
| MVP-18 | Markdown 下载 | Roadmap M7 | OpenAPI 16 个 operation 中无报告 endpoint | `missing` | proposed contract 提供查看、materialize 与 download，不泄露绝对路径 |
| MVP-19 | Markdown 是否属于 MVP | PRD 8.4 仍写“待确认”；Feature 10.6/11.13 与 Roadmap M7 写已确定 | 文档结论不一致 | `document_conflict` | 本 ADR 采用更具体、更新的 Feature/Roadmap：保留 Markdown；PDF 继续 deferred |
| MVP-20 | 从题库提交单题回答 | PRD 5.4；Feature 5.8 | Evaluation API、React practice、真实 E2E | `implemented_and_verified` | 当前 POST 同步 |
| MVP-21 | 手动题目评分 | Feature 4.2/5.8 | 后端支持 `custom_question_text` | `partially_implemented` | 当前 React 没有独立自定义题入口 |
| MVP-22 | 标准评价与改进反馈 | Feature 5.8 | 六维分、总分、反馈、改写、追问、下一题；测试与 UI | `implemented_and_verified` | 无 |
| MVP-23 | degraded/no-score/fallback 安全语义 | Phase 2.4/2.5A 冻结合同 | nullable score、memory block、前端与视觉测试 | `implemented_and_verified` | 新 job/report 合同必须继承 |
| MVP-24 | 评价历史 | Phase 1 API；Phase 2.5 | list/get endpoint、History 页面、E2E | `implemented_and_verified` | 当前无用户隔离过滤，公网禁用 |
| MVP-25 | 长期记忆写入 | Feature 5.9；Roadmap M6 | 高置信 standard 结果写入；degraded/fallback 阻断 | `implemented_and_verified` | 写入安全已验证 |
| MVP-26 | 长期记忆读取并用于下一轮推荐 | Feature 5.9 | 无 memory read endpoint；题库生成未读取 MemoryItem | `partially_implemented` | 不能声称训练闭环已使用长期记忆；需另行设计读取/应用策略 |
| MVP-27 | AgentRun 日志和详情 | Roadmap M8 | AgentRun/steps/observability、GET endpoint、React 页面 | `implemented_and_verified` | AgentRun 是执行记录，不是工作队列 |
| MVP-28 | 用户可恢复的真实异步进度 | Phase 2.5C proposal | 前端能轮询 pending/running AgentRun，但 create/parse/prep/evaluation 返回前已完成 | `partially_implemented` | 当前“进度”主要是同步等待 UI；需 workflow job |
| MVP-29 | 服务端取消、heartbeat、lease、崩溃恢复 | Phase 2.5D 目标 | 当前 model/API 均无对应语义 | `missing` | proposed async contract 定义 |
| MVP-30 | 面试转写复盘报告 | PRD 3.4/5.5；Feature 5.10；Release note | 只有面经资料解析，没有逐题复盘/下一轮计划 Agent | `intentionally_deferred` | 历史文档范围有张力；现 release baseline 明确未实现，本阶段不重开 |
| MVP-31 | 自动联网搜索、音频、支付、HR、多协作 | PRD 4.4；Feature 6 | 当前无这些能力 | `intentionally_deferred` | 符合 MVP 边界 |
| MVP-32 | PDF 报告 | Release note future scope | 当前无实现 | `intentionally_deferred` | Markdown 先行，不把 PDF 混入 2.5D-B |
| MVP-33 | 默认用户 | Roadmap M2 | lifespan 幂等创建、固定 `DEFAULT_USER_ID`、测试 | `implemented_and_verified` | 只适合单用户本机/私有演示 |
| MVP-34 | 认证与多用户资源隔离 | Feature 6 明确不做登录注册 | 无身份认证；若干 list/get 未按 caller user 过滤 | `intentionally_deferred` | 在实现前禁止公网部署 |
| MVP-35 | React 主要本机闭环 | Phase 2.5B/C | 创建、题库、练习、评价、历史、AgentRun；真实 E2E | `implemented_and_verified` | 页面存在不等于完整九章节备战包已完成 |
| MVP-36 | 本机/私有部署安全边界 | Phase 2.5A/C | exact CORS、上传限制、敏感日志边界、loopback E2E | `implemented_and_verified` | 仅证明本机合同联调，不等于 production ready |

## 3. 重点结论

### 3.1 完整备战包

当前为 `partially_implemented`。底层数据散落在 package、MatchReport、question、recommendation 和 action JSON 中；没有一个满足九章节顺序的读取合同，也没有手册。因此不能使用“已有题库页面”替代完整备战包验收。

### 3.2 备战要点手册

当前为 `missing`。建议保留 MVP 要求，通过确定性规则从持久化事实组装。若来源不足以形成 8 条加分点或 6 条雷点，生成器必须记录 completeness 缺口，不能复制或编造内容。

### 3.3 推荐先练 3 题

当前只完成持久化骨架。Phase 2.5D-B 应采用稳定评分规则选择，至少考虑优先级、MatchReport gap、题目 module/difficulty/source 和去重，并在 API 返回 `question_db_id/rank/reason/related_weaknesses`。

### 3.4 Markdown

实现缺失，但范围文档存在冲突。Phase 2.5D-A 决定沿用 Feature Spec 与 Roadmap 的更具体结论：Markdown 是 MVP 收口项；PDF 不属于本阶段。

### 3.5 AgentRun 和长期记忆

AgentRun 查询与观测已完成，但不能承担 durability、lease、cancel 或 crash recovery。长期记忆安全写入已完成，读取和用于后续训练仍未完成。

## 4. MVP 完成判定

在 MVP-11、MVP-13、MVP-17、MVP-18、MVP-29 未完成前，项目状态不得表述为“第一阶段 MVP 全部完成”。Phase 2.5D-B 可收口其中的完整包、手册、Markdown 和异步工作流；鉴权、多用户隔离及真实面试复盘仍需独立范围决策。
