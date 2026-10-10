# 开发路线图 v0.1

## 1. 开发目标

第一版目标不是做一个大而全的平台，而是做出一个可演示、可放简历、可解释技术细节的 Agent 项目。

核心验收：

1. 用户可以输入简历、JD、可选面经。
2. 系统可以生成完整面试备战包。
3. 用户可以选择一道题提交回答。
4. 系统可以输出单题评分和改进建议。
5. 系统记录 Agent 运行日志和用户长期记忆。
6. 系统可以导出 Markdown 报告。

## 2. 里程碑 1：项目脚手架

目标：

1. 创建 FastAPI 项目结构。
2. 配置 Pydantic Settings。
3. 配置日志。
4. 配置 `.env.example`。
5. 创建基础健康检查接口。

验收：

1. 服务可以启动。
2. `/health` 返回正常。
3. 项目目录符合技术栈文档。

## 3. 里程碑 2：数据库模型与迁移

目标：

1. 配置 PostgreSQL。
2. 接入 SQLAlchemy 2.x。
3. 接入 Alembic。
4. 建立 MVP 必建表。
5. 初始化默认用户。

验收：

1. Alembic 可以生成和执行迁移。
2. 数据库中存在默认用户。
3. 核心表可以正常创建。

## 4. 里程碑 3：文件解析与材料入库

目标：

1. 支持 PDF 文本提取。
2. 支持 DOCX 文本提取。
3. 支持 Markdown 和纯文本。
4. 保存文件到 `storage/uploads`。
5. 保存提取文本到 `source_documents`。

验收：

1. 上传 PDF 简历后能提取文本。
2. 粘贴 JD 后能入库。
3. 粘贴面经后能入库。

## 5. 里程碑 4：结构化解析

目标：

1. 实现 Resume Analyzer Agent。
2. 实现 JD Analyzer Agent。
3. 实现 Experience Analyzer Agent。
4. 输出符合 Pydantic schema。

验收：

1. 简历能生成 `ResumeProfile`。
2. JD 能生成 `JDProfile`。
3. 面经能生成 `ExperienceProfile`。
4. 结果写入数据库。

## 6. 里程碑 5：完整面试备战包生成

目标：

1. 实现 Matching Agent。
2. 实现 Question Bank Agent。
3. 实现 Prep Manual Agent。
4. 组装 `InterviewPrepPackage`。
5. 保存题库、手册、差距分析和推荐先练题。

验收：

1. 题库不少于 25 道。
2. 三个模块每个不少于 8 道。
3. 报告顺序符合 PRD。
4. 每道题有 `question_id` 和评分锚点。

## 7. 里程碑 6：单题模拟回答评分

目标：

1. 实现 Answer Evaluator Agent。
2. 支持从题库选择题目评分。
3. 支持用户手动输入题目评分。
4. 评分结果写入 `answer_evaluations`。
5. Memory Agent 生成记忆更新建议。

验收：

1. 输出总分和分项评分。
2. 输出扣分原因。
3. 输出改进版回答。
4. 输出追问和下一题建议。
5. 可写入长期记忆。

## 8. 里程碑 7：Markdown 报告导出

目标：

1. 将备战包渲染为 Markdown。
2. 保存到 `storage/reports`。
3. 将 Markdown 保存到 `rendered_markdown`。
4. 提供导出 API。

验收：

1. 导出的 Markdown 顺序正确。
2. 报告能直接阅读。
3. 包含题库、手册和行动清单。

## 9. 里程碑 8：运行日志与基础评测

目标：

1. 每次 Agent 工作流记录 `agent_runs`。
2. 每个 Agent 步骤记录 `agent_run_steps`。
3. 保存 prompt_version。
4. 增加基础规则校验。

验收：

1. 可以查看一次备战包生成的 Agent 执行链路。
2. 可以定位失败步骤。
3. 可以统计题库数量、字段完整性、评分字段完整性。

## 10. 推荐开发顺序

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

## 11. 第一版完成标志

满足以下条件可以认为 MVP 完成：

1. 可以用真实简历和真实 JD 生成一份完整备战包。
2. 可以导出 Markdown 报告。
3. 可以选择报告中的题目进行单题评分。
4. 可以在数据库中看到材料、备战包、题库、评分、记忆和 Agent 运行日志。
5. 有至少 2-3 组样例材料用于演示。

