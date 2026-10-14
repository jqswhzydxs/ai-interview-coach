# 项目开发原则 Constitution v0.1

## 1. 适用范围

本 Constitution 用于约束 AI Interview Coach Agent 第一阶段 MVP 的开发实现。

依据文档：

1. `docs/00-project-handoff-summary.md`
2. `docs/01-prd-v0.2.md`
3. `docs/02-agent-system-design-v0.1.md`
4. `docs/03-interview-generation-spec-v0.1.md`
5. `docs/04-single-answer-evaluation-spec-v0.1.md`
6. `docs/05-database-schema-design-v0.1.md`
7. `docs/07-tech-stack-and-project-structure-v0.1.md`
8. `docs/08-api-design-v0.1.md`
9. `docs/09-pydantic-schema-design-v0.1.md`
10. `docs/10-agent-prompts-and-routing-v0.1.md`
11. `docs/14-first-phase-mvp-implementation-plan-v0.1.md`
12. `docs/15-first-phase-mvp-tasks-v0.1.md`

本文件只整理已确定的工程原则，不新增业务范围。

## 2. 范围原则

1. 第一阶段只服务后端开发岗位方向。
2. 第一阶段核心闭环是完整面试备战包生成和单题模拟回答评分。
3. 第一阶段先做后端 API，不做正式前端。
4. 第一阶段不做自动联网搜索面经。
5. 第一阶段不做招聘网站爬虫、自动投递、支付、企业 HR 端、多人协作。
6. 第一阶段不直接处理音频文件，只处理用户已经转写好的文本。
7. 真实面试转写复盘不进入第一条 MVP 主线，作为后续能力处理。
8. 质量评测后台不进入第一阶段实现，只保留规则校验和固定样例测试。

## 3. 技术栈原则

1. Python 版本使用 Python 3.11。
2. 包管理使用 `uv + pyproject.toml`。
3. 后端框架使用 FastAPI。
4. ORM 使用 SQLAlchemy 2.x。
5. 数据库迁移使用 Alembic。
6. 数据库使用 PostgreSQL。
7. 数据校验使用 Pydantic v2。
8. 文件解析使用 PyMuPDF、python-docx、Markdown 和纯文本处理。
9. 第一阶段报告导出使用 Markdown，不做 PDF 导出。
10. Agent 编排先实现轻量 Harness，不强绑定 LangGraph 或 Agents SDK。
11. LLM 调用通过 `LLMClient` 抽象，业务代码不得直接绑定具体模型供应商。
12. 国产模型优先适配 DeepSeek，其次预留 Kimi Provider。

## 4. 架构原则

1. `api` 层只处理 HTTP 请求、响应和常见错误，不直接写业务流程。
2. `services` 层负责编排业务流程、数据库读写和调用 Harness。
3. `agents` 层负责 Agent 能力、Prompt 加载、LLMClient 调用和 mock/stub 实现。
4. `schemas` 层负责 Pydantic 结构化对象，是 API、Agent 输出、JSONB 存储和测试的共同契约。
5. `db/models` 层负责 SQLAlchemy ORM 模型。
6. `tools` 层放文件解析、Markdown 渲染、文本脱敏、hash 等无状态工具。
7. Harness 负责任务调度、Agent 运行日志、schema 校验、失败重试、结果入库和记忆更新。
8. Harness 不负责直接生成业务内容。

## 5. 数据库原则

1. 数据库采用 PostgreSQL。
2. 第一阶段采用关系表 + JSONB 的混合设计。
3. 高频查询字段单独建列，复杂 Agent 输出优先放 JSONB。
4. MVP 首轮必建 `users`、`source_documents`、`resumes`、`resume_profiles`、`job_descriptions`、`jd_profiles`、`interview_experiences`、`experience_profiles`、`interview_prep_packages`、`prep_package_experiences`、`match_reports`、`interview_questions`、`prep_manuals`、`recommended_questions`、`answer_evaluations`、`memory_items`、`agent_runs`、`agent_run_steps`。
5. 首轮不建 `interview_reviews` 和 `quality_evaluations`。
6. 第一阶段不做登录注册，但保留 `users` 表并使用默认用户。
7. 默认用户由应用启动时检查并创建。
8. 上传文件保存到本地 `storage/uploads`。
9. 导出报告保存到本地 `storage/reports`。
10. `UPLOAD_DIR` 和 `REPORT_DIR` 允许通过环境变量覆盖。
11. 文本 hash 使用 SHA-256。
12. 原始材料集中保存在 `source_documents`，Agent 日志默认只保存摘要。
13. 手机号和邮箱至少在 Agent 输入与日志摘要中脱敏；数据库原文是否脱敏可后续加强，首轮默认保留原文以保证可追溯。

## 6. API 原则

1. API 基础路径为 `/api/v1`。
2. 第一阶段不做登录注册接口。
3. 第一阶段使用默认用户，客户端暂不传 `user_id`。
4. 成功响应使用统一结构：

```json
{
  "data": {},
  "message": "ok",
  "request_id": "..."
}
```

5. 错误响应使用统一结构：

```json
{
  "error": {
    "code": "...",
    "message": "...",
    "details": {}
  }
}
```

6. 第一阶段至少支持错误码：`VALIDATION_ERROR`、`NOT_FOUND`、`AGENT_FAILED`、`INTERNAL_ERROR`。
7. 每个请求都生成 `request_id`，并写入日志和响应。
8. 列表接口分页使用 `limit + offset`。
9. 文件上传大小限制为 5MB。
10. 备战包生成第一版采用同步接口，同时保留 `status` 和 `agent_run_id`。
11. 同步生成接口建议超时时间为 120 秒。

## 7. Schema 原则

1. Pydantic Schema 是 API、Agent、数据库 JSONB 和测试之间的唯一结构化契约。
2. Agent 输出必须解析为 Pydantic Schema 后才能入库。
3. 所有 Agent 输出建议包含 `schema_version`、`generated_at`、`agent_name`、`prompt_version`。
4. `QuestionBank` 必须不少于 25 道题。
5. 题库三个模块每个不少于 8 道题。
6. 同一题库内 `question_id` 必须唯一。
7. 每道题必须包含来源依据、JD 关键词、高分回答框架、STAR 模板和评分锚点。
8. `PrepManual` 的回答加分点不少于 8 条。
9. `PrepManual` 的回答雷点不少于 6 条。
10. `AnswerEvaluation` 使用 100 分制。
11. 单题评分维度固定为：相关性 20 分、技术准确性 25 分、项目具体性 20 分、结构性 15 分、表达力 10 分、风险控制 10 分。
12. `EvidenceRef.quote` 可以保存必要短片段，但日志和摘要中优先保存 summary，减少敏感信息暴露。

## 8. Agent 与 Prompt 原则

1. 第一阶段先使用 mock/stub Agent 打通 API、数据库、Schema、Harness 和报告导出闭环。
2. 真实 LLM 接入必须通过 `LLMClient`。
3. `LLM_PROVIDER` 支持 `mock`、`deepseek`、`kimi`。
4. DeepSeek 作为默认优先接入 Provider，Kimi 作为后续 Provider。
5. 具体模型名通过 `LLM_MODEL` 配置。
6. API key 环境变量使用 `DEEPSEEK_API_KEY` 和 `KIMI_API_KEY`。
7. Prompt 正文独立文件化，放在 `app/agents/prompts/*.md`。
8. Prompt 文件名必须包含版本号，例如 `resume_analyzer_v0.1.md`。
9. 每次修改 Prompt 都应更新版本号。
10. 默认只保存 Prompt 和模型响应摘要。
11. 开发环境可通过 `SAVE_FULL_LLM_LOGS=true` 保存完整 Prompt 和模型响应。
12. Agent 输出 schema 校验失败时自动重试一次。
13. 数量约束不达标时，带错误原因重试一次。
14. 多次失败时写入 `agent_runs` 失败状态，并返回明确错误。
15. Agent 不得编造用户没有写过的项目经历。
16. Agent 不得建议用户虚构学历、工作经验或项目成果。
17. 面经只能标注为参考材料，不能说成确定真题。
18. 材料不足时必须标注“基于综合推断”。

## 9. 文件与报告原则

1. 第一条 MVP 垂直切片先支持纯文本简历和纯文本 JD。
2. PDF、DOCX、Markdown 文件解析属于同一 MVP 范围，但可以在文本闭环跑通后补齐。
3. Markdown 报告必须按以下顺序输出：

```text
备战总览
JD 核心要求拆解
简历-JD 差距分析
简历优化建议
面试准备优先级
岗位专属面试题库
面试备战要点手册
推荐先练的 3 道题
下一步行动清单
```

4. Markdown 每次导出生成新文件。
5. 报告文件名包含 `prep_package_id` 和时间戳。
6. 导出后更新 `interview_prep_packages.rendered_markdown`。

## 10. 记忆原则

1. 长期记忆保存在 `memory_items`。
2. Memory Agent 不应把单次偶然失误直接写为长期问题。
3. 高置信度记忆更新可以自动写入。
4. 低置信度记忆更新只保存在评分结果中作为建议。
5. 同类问题连续低分，或证据明确且置信度高时，才写入长期薄弱点。
6. 记忆必须包含 evidence、confidence、source_type 和 source_id。
7. 记忆不得凭空推断敏感个人信息。

## 11. 测试原则

1. 每个可实现任务必须有对应验收标准和测试方式。
2. Schema 约束必须有单元测试。
3. API 主路径必须有集成测试。
4. MVP 主闭环必须有端到端测试。
5. 第一阶段准备 2 到 3 组固定验收样例。
6. 固定样例不得包含真实个人隐私。
7. 使用 mock Agent 也必须能跑通完整闭环。
8. MVP 完成前至少通过：

```text
uv run pytest tests/unit
uv run pytest tests/integration
uv run pytest tests/e2e
```

9. 题库数量、模块数量、手册条数、评分字段完整性必须纳入自动测试。
10. 第一阶段不要求实现 `quality_evaluations` 入库。

## 12. MVP 垂直切片原则

建议优先实现以下最小闭环：

```text
纯文本简历 + 纯文本 JD
↓
保存 source_documents
↓
创建 resume / job_description
↓
mock 生成 ResumeProfile / JDProfile
↓
mock 生成完整备战包
↓
查询备战包
↓
导出 Markdown
↓
选择一道题提交回答
↓
mock 生成评分
↓
查询评分与 Agent 日志
```

这条切片优先验证：

1. API 路由。
2. 数据库模型。
3. Pydantic Schema。
4. Harness 调度。
5. Agent 运行日志。
6. 题库和评分结构约束。
7. Markdown 报告导出。

## 13. 冲突处理结论

### 13.1 真实面试复盘

文档中 PRD 提到面试转写复盘，但交接摘要、数据库设计、后续优化和实现计划均倾向后置。

结论：

第一阶段不实现真实面试复盘主线，`interview_reviews` 首轮不建表。

### 13.2 文件输入支持顺序

文档中已确认第一版支持 PDF、DOCX、Markdown、纯文本，但早期 PRD 曾提到可先支持文本。

结论：

产品范围保留四类输入；实现顺序上，第一条垂直切片先打通纯文本输入，再补 PDF、DOCX、Markdown 解析。

### 13.3 数据库表范围

部分摘要文档未列出 `prep_package_experiences`，数据库设计文档已补充该关联表。

结论：

以数据库设计、实现计划和任务清单为准，MVP 必建 `prep_package_experiences`。

### 13.4 质量评测

系统设计强调评测，数据库设计保留 `quality_evaluations`，但后续优化和实现计划均将评测后台后置。

结论：

第一阶段只做规则校验和固定样例测试，不建 `quality_evaluations`。

## 14. 当前仍需确认项

以下事项不阻塞第一条 mock 垂直切片，但在真实 LLM 或生产化前需要确认：

1. DeepSeek 具体默认模型名称。
2. Kimi 具体备用模型名称。
3. 真实 LLM API 的超时和重试策略。
4. 内容疑似编造的自动检测规则。
5. 降级输出的具体格式。
6. 高置信度自动写入记忆的阈值。
7. 固定验收样例的最终内容。

## 15. 执行顺序原则

优先顺序：

1. 项目脚手架、配置、健康检查。
2. 通用 Schema、统一响应、request_id、文本 hash 和脱敏工具。
3. 数据库连接、ORM 模型、Alembic 迁移、默认用户。
4. LLMClient、mock Agent、Harness、Prompt 文件加载。
5. 文本材料、简历、JD 创建和解析。
6. mock 备战包生成、查询、题库查询、Markdown 导出。
7. mock 单题评分、记忆策略、Agent 日志查询。
8. 固定样例、单元测试、集成测试、端到端测试。
