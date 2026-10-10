# AI Interview Coach Agent 项目交接摘要

## 1. 项目主题

项目名称暂定：

```text
AI Interview Coach Agent
```

GitHub 仓库名建议：

```text
ai-interview-coach-agent
```

项目定位：

面向在校大学生和社会求职者的简历岗位匹配与模拟面试 Agent 系统。第一版优先服务后端开发岗位。

项目目标不是做一个泛聊天机器人，而是完成真实求职准备闭环：

```text
简历 + JD + 可选面经
↓
简历-JD 差距分析
↓
岗位专属面试题库
↓
面试备战要点手册
↓
单题模拟回答评分
↓
记录薄弱点并进入下一轮训练
```

## 2. 已确认的 MVP 决策

1. 第一版优先后端开发岗位。
2. 第一版做完整面试备战包生成。
3. 第一版同时做单题模拟回答评分。
4. 简历支持 PDF、DOCX、Markdown、纯文本。
5. JD 由用户粘贴或输入。
6. 面经由用户手动粘贴，不做自动联网搜索。
7. 面试录音第一版只处理转写后的文本。
8. 第一版先做后端 API，不做正式前端。
9. 第一版支持 Markdown 报告导出。
10. 真实面试转写复盘和质量评测后台后置。

## 3. 完整面试备战包展示顺序

最终报告按以下顺序展示：

```text
1. 备战总览
2. JD 核心要求拆解
3. 简历-JD 差距分析
4. 简历优化建议
5. 面试准备优先级
6. 岗位专属面试题库
7. 面试备战要点手册
8. 推荐先练的 3 道题
9. 下一步行动清单
```

设计原则：

先告诉用户“现在该怎么办”，再给证据，最后进入训练。

## 4. 技术方案

第一版默认技术栈：

1. 后端框架：FastAPI。
2. ORM：SQLAlchemy 2.x。
3. 数据库迁移：Alembic。
4. 数据库：PostgreSQL。
5. 数据校验：Pydantic v2。
6. 文件解析：PyMuPDF、python-docx、Markdown 纯文本处理。
7. Agent 编排：先写轻量 Harness。
8. 报告导出：Markdown。
9. 前端：后置。

Agent 编排后续可替换或升级为：

1. OpenAI Agents SDK。
2. LangGraph。

## 5. 数据库设计决策

数据库使用 PostgreSQL。

第一版保留 `users` 表，但暂不做登录注册，使用默认用户。

上传文件保存到本地目录：

```text
storage/uploads
storage/reports
```

数据库保存：

1. 文件路径。
2. 提取文本。
3. 文件元信息。
4. Agent 结构化输出。
5. Agent 运行日志。
6. 用户长期记忆。

核心表包括：

1. `users`
2. `source_documents`
3. `resumes`
4. `resume_profiles`
5. `job_descriptions`
6. `jd_profiles`
7. `interview_experiences`
8. `experience_profiles`
9. `interview_prep_packages`
10. `match_reports`
11. `interview_questions`
12. `prep_manuals`
13. `recommended_questions`
14. `answer_evaluations`
15. `memory_items`
16. `agent_runs`
17. `agent_run_steps`

延后表：

1. `interview_reviews`
2. `quality_evaluations`

## 6. Agent 分工

第一版 Agent / 模块：

1. Document Parser：文件解析。
2. Resume Analyzer Agent：简历结构化解析。
3. JD Analyzer Agent：JD 结构化解析。
4. Experience Analyzer Agent：面经结构化解析。
5. Matching Agent：简历-JD 匹配分析。
6. Question Bank Agent：生成岗位专属题库。
7. Prep Manual Agent：生成面试备战要点手册。
8. Answer Evaluator Agent：单题模拟回答评分。
9. Memory Agent：更新用户长期记忆。

Harness 负责：

1. Agent 调度。
2. 状态管理。
3. 工具调用。
4. 输出 schema 校验。
5. 失败重试。
6. 运行日志。
7. 记忆更新。

## 7. 单题评分规则

单题评分采用 100 分制：

1. 相关性：20 分。
2. 技术准确性：25 分。
3. 项目具体性：20 分。
4. 结构性：15 分。
5. 表达力：10 分。
6. 风险控制：10 分。

输出内容：

1. 总分。
2. 分项评分。
3. 表现好的地方。
4. 需要改进的地方。
5. 技术错误或表达风险。
6. 改进版回答。
7. 可能追问。
8. 下一题建议。
9. 记忆更新建议。

## 8. 当前文档清单

当前有效文档位于 `docs/`：

1. `00-project-handoff-summary.md`：项目交接摘要。
2. `01-prd-v0.2.md`：产品需求文档。
3. `02-agent-system-design-v0.1.md`：Agent 系统设计。
4. `03-interview-generation-spec-v0.1.md`：完整面试备战包生成规格。
5. `04-single-answer-evaluation-spec-v0.1.md`：单题评分规格。
6. `05-database-schema-design-v0.1.md`：数据库表设计。
7. `06-pre-implementation-checklist-v0.1.md`：编码前确认清单。
8. `07-tech-stack-and-project-structure-v0.1.md`：技术栈与项目结构。
9. `08-api-design-v0.1.md`：API 设计。
10. `09-pydantic-schema-design-v0.1.md`：Pydantic Schema 设计。
11. `10-agent-prompts-and-routing-v0.1.md`：Agent Prompt 与路由设计。
12. `11-development-roadmap-v0.1.md`：开发路线图。
13. `12-future-improvements-v0.1.md`：后续改进与优化清单。

历史草稿：

1. `AI-Interview-Coach-Agent-PRD-v0.1.md`

## 9. 下一步开发建议

下一步可以正式进入代码阶段。

推荐从里程碑 1 开始：

```text
1. 创建 FastAPI 项目脚手架
2. 配置 pyproject.toml
3. 配置 .env.example
4. 配置 PostgreSQL 连接
5. 配置 SQLAlchemy 和 Alembic
6. 创建 /health 接口
```

完整开发路线：

```text
1. 项目脚手架
2. 数据库模型与迁移
3. 文件解析与材料入库
4. Resume / JD / 面经结构化解析
5. 完整面试备战包生成
6. 单题模拟回答评分
7. Markdown 报告导出
8. Agent 运行日志
```

## 10. GitHub 仓库填写建议

Repository name：

```text
ai-interview-coach-agent
```

Description：

```text
AI-powered interview prep agent for backend developers: resume-JD matching, personalized question bank, answer evaluation, memory, and Markdown reports.
```

Visibility：

```text
Public
```

初始化选项：

```text
Add README: Off
Add .gitignore: No .gitignore
Add license: No license 或 MIT License
```

推荐为了后续本地推送更省事：

```text
README Off
.gitignore No
License No license
```

后续在本地统一添加 README、.gitignore 和 LICENSE。

