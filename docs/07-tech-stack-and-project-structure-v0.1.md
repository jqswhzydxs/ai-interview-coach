# 技术栈与项目结构 v0.1

## 1. 当前默认方案

第一版按“后端 API 优先”的方式开发，暂不做正式前端。

默认技术栈：

1. 后端框架：FastAPI。
2. ORM：SQLAlchemy 2.x。
3. 数据库迁移：Alembic。
4. 数据库：PostgreSQL。
5. 数据校验：Pydantic v2。
6. 文件解析：PyMuPDF、python-docx、Markdown 纯文本处理。
7. Agent 编排：先实现轻量 Harness，自己管理多 Agent 调度。
8. 报告导出：第一版导出 Markdown。
9. 前端：后置，第一阶段用 API 文档和 Markdown 报告验证业务闭环。

## 2. 为什么先只做后端 API

第一版项目最核心的价值不在页面，而在：

1. 文件解析。
2. 简历、JD、面经结构化。
3. 多 Agent 编排。
4. 完整备战包生成。
5. 单题回答评分。
6. 运行日志和记忆沉淀。

先做后端 API 可以更快验证核心能力，也更方便后续接 Web 前端、CLI 或桌面端。

## 3. 推荐项目目录

```text
ai-interview-coach/
  app/
    api/
      v1/
        routes/
          documents.py
          resumes.py
          jobs.py
          experiences.py
          prep_packages.py
          questions.py
          evaluations.py
          reports.py
    core/
      config.py
      logging.py
      security.py
    db/
      base.py
      session.py
      models/
        user.py
        source_document.py
        resume.py
        job_description.py
        interview_experience.py
        prep_package.py
        question.py
        evaluation.py
        memory.py
        agent_run.py
    schemas/
      resume.py
      job_description.py
      experience.py
      prep_package.py
      question.py
      evaluation.py
      memory.py
      agent.py
    services/
      document_service.py
      resume_service.py
      job_service.py
      prep_package_service.py
      evaluation_service.py
      report_service.py
    agents/
      harness.py
      base.py
      resume_analyzer.py
      jd_analyzer.py
      experience_analyzer.py
      matching_agent.py
      question_bank_agent.py
      prep_manual_agent.py
      answer_evaluator.py
      memory_agent.py
      prompts/
    tools/
      file_parser.py
      markdown_renderer.py
      validators.py
    main.py
  alembic/
  storage/
    uploads/
    reports/
  tests/
    unit/
    integration/
  docs/
  pyproject.toml
  alembic.ini
  .env.example
  README.md
```

## 4. 分层说明

### 4.1 api 层

负责 HTTP 接口，不直接写业务逻辑。

主要职责：

1. 接收请求。
2. 调用 service。
3. 返回统一响应。
4. 处理常见错误。

### 4.2 service 层

负责业务流程编排。

例如：

1. 保存上传材料。
2. 调用文件解析工具。
3. 创建数据库记录。
4. 调用 Harness 执行 Agent 工作流。
5. 组装最终报告。

### 4.3 agents 层

负责 Agent 能力。

第一版先写轻量 Harness，不强绑定具体框架。后续可以替换为 OpenAI Agents SDK 或 LangGraph。

### 4.4 schemas 层

负责 Pydantic 结构化对象。

这些 schema 同时服务：

1. API 请求与响应。
2. Agent 结构化输出。
3. 数据库 JSONB 字段。
4. 测试与评测。

### 4.5 db/models 层

负责 SQLAlchemy ORM 模型。

ORM 表结构以 `05-database-schema-design-v0.1.md` 为准。

## 5. 文件存储约定

第一版使用本地文件存储：

```text
storage/uploads
storage/reports
```

`storage/uploads` 保存：

1. PDF 简历。
2. DOCX 简历。
3. Markdown 简历。
4. 后续可能上传的其他材料。

`storage/reports` 保存：

1. 完整面试备战包 Markdown。
2. 后续可能导出的 PDF。

数据库保存：

1. 文件路径。
2. 提取文本。
3. 文件元信息。
4. 文本 hash。

## 6. 环境变量

建议 `.env.example` 包含：

```text
APP_ENV=local
APP_NAME=ai-interview-coach
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/interview_coach
UPLOAD_DIR=storage/uploads
REPORT_DIR=storage/reports
DEFAULT_USER_ID=00000000-0000-0000-0000-000000000001
OPENAI_API_KEY=
LLM_MODEL=
```

## 7. 第一版不引入的内容

1. 登录注册。
2. 复杂前端。
3. 云对象存储。
4. 语音实时转写。
5. 自动联网搜索面经。
6. pgvector/RAG。
7. 质量评测后台。

这些都放入后续优化文档。

