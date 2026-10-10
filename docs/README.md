# AI Interview Coach Agent 文档索引

当前有效文档建议按以下顺序阅读：

1. `01-prd-v0.2.md`：产品需求文档，定义目标用户、MVP 范围、输入输出和验收标准。
2. `02-agent-system-design-v0.1.md`：Agent 系统设计，定义 Harness、多 Agent 分工、工作流、结构化对象、记忆和评测。
3. `03-interview-generation-spec-v0.1.md`：完整面试备战包生成规格，定义题库和备战手册的生成要求。
4. `04-single-answer-evaluation-spec-v0.1.md`：单题模拟回答评分规格，定义评分维度、输出格式、追问和记忆更新规则。
5. `05-database-schema-design-v0.1.md`：数据库表设计，定义材料、备战包、题库、评分、记忆、日志和评测相关表。
6. `06-pre-implementation-checklist-v0.1.md`：编码前确认清单，说明正式写代码前还建议补齐哪些工程设计文件。
7. `07-tech-stack-and-project-structure-v0.1.md`：技术栈与项目结构，确认 FastAPI、SQLAlchemy、Alembic、PostgreSQL、轻量 Harness 和目录组织。
8. `08-api-design-v0.1.md`：API 设计，定义材料上传、简历/JD/面经解析、备战包生成、单题评分和报告导出接口。
9. `09-pydantic-schema-design-v0.1.md`：Pydantic Schema 设计，定义 Agent 结构化输出和 API 返回对象。
10. `10-agent-prompts-and-routing-v0.1.md`：Agent Prompt 与路由设计，定义各 Agent 输入输出、Prompt 版本、路由和失败处理。
11. `11-development-roadmap-v0.1.md`：开发路线图，定义从脚手架到 Agent 日志的里程碑。
12. `12-future-improvements-v0.1.md`：后续改进与优化清单，记录 MVP 后可以增强的方向。

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
13. 后续优化方向单独维护在 `12-future-improvements-v0.1.md`。
