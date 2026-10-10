# 编码前确认清单 v0.1

## 1. 目的

这份清单用于判断项目是否可以从需求和系统设计阶段进入编码阶段。

当前结论：核心业务、Agent 工作流、报告结构、单题评分、数据库设计已经基本清楚，可以开始进入技术设计和项目脚手架阶段。正式写业务代码前，还建议补齐少量工程文件。

## 2. 已确认文档

以下文档已经可以作为开发依据：

1. `01-prd-v0.2.md`：产品需求和 MVP 范围。
2. `02-agent-system-design-v0.1.md`：Harness、多 Agent、记忆、评测和工作流设计。
3. `03-interview-generation-spec-v0.1.md`：完整面试备战包生成规格。
4. `04-single-answer-evaluation-spec-v0.1.md`：单题模拟回答评分规格。
5. `05-database-schema-design-v0.1.md`：数据库表设计。

## 3. 编码前建议补齐的文件

### 3.1 技术栈与项目结构文档

建议新增：

```text
docs/07-tech-stack-and-project-structure-v0.1.md
```

需要确认：

1. 后端框架：建议 FastAPI。
2. ORM：建议 SQLAlchemy 2.x。
3. 数据库迁移：建议 Alembic。
4. 数据库：已确认 PostgreSQL。
5. 前端：如果第一阶段只做后端 API，可先不建前端。
6. Agent SDK：需要确认使用 OpenAI Agents SDK、LangGraph，还是先写轻量 Harness。
7. 文件存储目录：建议 `storage/uploads` 和 `storage/reports`。

### 3.2 API 设计文档

建议新增：

```text
docs/08-api-design-v0.1.md
```

第一版需要确认的 API：

1. 上传或粘贴简历。
2. 创建 JD。
3. 粘贴面经。
4. 生成完整面试备战包。
5. 查询备战包详情。
6. 查询题库。
7. 提交单题回答并评分。
8. 查询历史评分记录。
9. 导出 Markdown 报告。

### 3.3 Pydantic Schema 设计文档

建议新增：

```text
docs/09-pydantic-schema-design-v0.1.md
```

需要定义：

1. `ResumeProfile`
2. `JDProfile`
3. `ExperienceProfile`
4. `MatchReport`
5. `InterviewQuestion`
6. `QuestionBank`
7. `PrepManual`
8. `InterviewPrepPackage`
9. `AnswerEvaluation`
10. `MemoryItem`

说明：这份文档很重要，因为它会直接影响 Agent 结构化输出、API 返回值和数据库 `jsonb` 字段。

### 3.4 Prompt 与 Agent 配置文档

建议新增：

```text
docs/10-agent-prompts-and-routing-v0.1.md
```

需要确认：

1. 每个 Agent 的职责边界。
2. 每个 Agent 的输入和输出 schema。
3. 每个 Prompt 的版本号。
4. Harness 如何选择 Agent。
5. 输出不符合 schema 时如何重试。
6. 是否需要人工确认某些记忆更新。

### 3.5 开发里程碑文档

建议新增：

```text
docs/11-development-roadmap-v0.1.md
```

建议里程碑：

1. 项目脚手架与数据库迁移。
2. 文件解析与材料入库。
3. Resume/JD/面经结构化解析。
4. 完整面试备战包生成。
5. 单题模拟回答评分。
6. Markdown 报告导出。
7. Agent 运行日志与基础评测。

## 4. 可以暂时不确认的文件

以下内容可以进入编码后再补：

1. 前端视觉设计。
2. 登录注册设计。
3. 真实面试转写复盘详细设计。
4. 质量评测后台设计。
5. pgvector/RAG 详细方案。
6. 部署到云服务器的完整方案。

## 5. 当前推荐下一步

我建议下一步先确认并生成：

```text
docs/07-tech-stack-and-project-structure-v0.1.md
```

原因：

1. 它决定项目目录怎么建。
2. 它决定依赖怎么选。
3. 它决定先做 CLI、API，还是 Web。
4. 它会直接影响后续代码结构。

推荐默认方案：

1. 后端：FastAPI。
2. ORM：SQLAlchemy 2.x。
3. 迁移：Alembic。
4. 数据库：PostgreSQL。
5. 数据校验：Pydantic v2。
6. 文件解析：PyMuPDF、python-docx、Markdown 纯文本处理。
7. Agent 编排：先实现轻量 Harness，保留替换为 OpenAI Agents SDK 或 LangGraph 的接口。
8. 第一阶段先做后端 API + Markdown 报告导出，前端后置。

