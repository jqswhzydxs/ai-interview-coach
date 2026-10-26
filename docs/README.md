# AI Interview Coach Agent 文档索引

当前有效文档建议按以下顺序阅读：

1. `00-project-handoff-summary.md`：项目交接摘要，适合复制到另一台电脑后快速恢复上下文。
2. `01-prd-v0.2.md`：产品需求文档，定义目标用户、MVP 范围、输入输出和验收标准。
3. `02-agent-system-design-v0.1.md`：Agent 系统设计，定义 Harness、多 Agent 分工、工作流、结构化对象、记忆和评测。
4. `03-interview-generation-spec-v0.1.md`：完整面试备战包生成规格，定义题库和备战手册的生成要求。
5. `04-single-answer-evaluation-spec-v0.1.md`：单题模拟回答评分规格，定义评分维度、输出格式、追问和记忆更新规则。
6. `05-database-schema-design-v0.1.md`：数据库表设计，定义材料、备战包、题库、评分、记忆、日志和评测相关表。
7. `06-pre-implementation-checklist-v0.1.md`：编码前确认清单，说明正式写代码前还建议补齐哪些工程设计文件。
8. `07-tech-stack-and-project-structure-v0.1.md`：技术栈与项目结构，确认 FastAPI、SQLAlchemy、Alembic、PostgreSQL、轻量 Harness 和目录组织。
9. `08-api-design-v0.1.md`：API 设计，定义材料上传、简历/JD/面经解析、备战包生成、单题评分和报告导出接口。
10. `09-pydantic-schema-design-v0.1.md`：Pydantic Schema 设计，定义 Agent 结构化输出和 API 返回对象。
11. `10-agent-prompts-and-routing-v0.1.md`：Agent Prompt 与路由设计，定义各 Agent 输入输出、Prompt 版本、路由和失败处理。
12. `11-development-roadmap-v0.1.md`：开发路线图，定义从脚手架到 Agent 日志的里程碑。
13. `12-future-improvements-v0.1.md`：后续改进与优化清单，记录 MVP 后可以增强的方向。

历史草稿：

1. `AI-Interview-Coach-Agent-PRD-v0.1.md`：早期需求草稿，保留用于追溯，不作为当前开发依据。

当前 MVP 决策：

1. 第一版优先服务后端开发岗位。
2. 第一版支持完整面试备战包生成。
3. 第一版同时支持单题模拟回答评分。
4. 简历支持 PDF、DOCX、Markdown、纯文本。
5. 面经由用户手动粘贴，不做自动联网搜索。
6. 面试录音第一版只处理转写后的文本。
7. 完整面试备战包按“备战总览 -> JD 拆解 -> 差距分析 -> 简历建议 -> 准备优先级 -> 题库 -> 手册 -> 先练 3 题 -> 行动清单”的顺序展示。
8. 第一版使用 PostgreSQL，暂不做登录注册，使用默认用户。
9. 上传文件保存到本地目录，数据库保存 `file_path` 和提取文本。
10. 第一版支持 Markdown 报告导出，真实面试转写复盘和质量评测后台后置。
11. 第一版先做后端 API，不做正式前端。
12. 第一版采用轻量 Harness 自主管理多 Agent 调度，后续可替换为 OpenAI Agents SDK 或 LangGraph。

## Phase 2.4C：确定性 metadata 校准

- [Phase 2.4B 最终决策](39-phase-2-4b-final-decision-record-v0.1.md)：Candidate 不通过，不晋升；AI 盲评来源及 baseline 数量异常。
- [Spec](40-phase-2-4c-metadata-calibration-spec-v0.1.md)
- [Plan](41-phase-2-4c-metadata-calibration-plan-v0.1.md)
- [Tasks](42-phase-2-4c-metadata-calibration-tasks-v0.1.md)
- [Risk Analysis](43-phase-2-4c-metadata-calibration-risk-analysis-v0.1.md)
- [离线验证报告](44-phase-2-4c-offline-validation-report-v0.1.md)
- [Metadata review finalizer](45-phase-2-4c-metadata-review-finalizer-v0.1.md)

Metadata v2 仅作为离线候选；生产默认仍为 QuestionBankAgent，等待新的独立 metadata 盲评。
13. 后续优化方向单独维护在 `12-future-improvements-v0.1.md`。

## Phase 2.5B：Mock-first 前端脚手架

- [Spec](118-phase-2.5b-mock-frontend-spec-v0.1.md)
- [Plan](119-phase-2.5b-mock-frontend-plan-v0.1.md)
- [Tasks](120-phase-2.5b-mock-frontend-tasks-v0.1.md)
- [Risk Analysis](121-phase-2.5b-mock-frontend-risk-analysis-v0.1.md)
- [Frontend Architecture](122-phase-2.5b-frontend-architecture-v0.1.md)
- [Mock Runtime Guide](123-phase-2.5b-mock-runtime-guide-v0.1.md)
- [Accessibility Validation](124-phase-2.5b-accessibility-validation-v0.1.md)
- [Security Validation](125-phase-2.5b-security-validation-v0.1.md)
- [Offline Validation Report](126-phase-2.5b-offline-validation-report-v0.1.md)

当前状态为 `mock_scaffold_complete`；开发与测试默认只使用 MSW，不代表已经完成真实 API 联调或生产 Agent 切换。

## Phase 2.5C：本机真实 API 联调与浏览器基线

- [Spec](127-phase-2.5c-local-api-integration-spec-v0.1.md)
- [Plan](128-phase-2.5c-local-api-integration-plan-v0.1.md)
- [Tasks 与验证记录](129-phase-2.5c-tasks-and-validation-record-v0.1.md)
- [Risk Analysis](130-phase-2.5c-risk-analysis-v0.1.md)
- [Local Integration Runbook](131-phase-2.5c-local-integration-runbook-v0.1.md)
- [Browser / Visual QA Report](132-phase-2.5c-browser-visual-qa-report-v0.1.md)
- [Offline Validation Report](133-phase-2.5c-offline-validation-report-v0.1.md)

本阶段只联调本机 FastAPI、隔离 SQLite 与 loopback HTTP；Provider calls 为 0，生产默认 Agent 保持不变。
