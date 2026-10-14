# MVP 第一阶段 Feature Spec：面试问题生成与单题评价 v0.1

## 1. Feature 概述

本 feature spec 定义 MVP 第一阶段的一条核心用户闭环：

```text
用户输入目标岗位 / 简历 / 准备目标
↓
系统生成岗位相关面试问题
↓
用户选择或输入一道题并提交单题答案
↓
系统给出结构化评价、改进建议和下一题建议
```

本规格基于现有 PRD 和设计文档整理，不新增未确认功能。

来源文档：

1. `docs/01-prd-v0.2.md`
2. `docs/02-agent-system-design-v0.1.md`
3. `docs/03-interview-generation-spec-v0.1.md`
4. `docs/04-single-answer-evaluation-spec-v0.1.md`
5. `docs/08-api-design-v0.1.md`
6. `docs/09-pydantic-schema-design-v0.1.md`
7. `docs/10-agent-prompts-and-routing-v0.1.md`
8. `docs/16-project-constitution-v0.1.md`

## 2. 范围

### 2.1 本 Feature 包含

1. 用户提交简历。
2. 用户提交目标岗位 JD。
3. 用户填写或选择准备目标。
4. 系统解析简历和 JD。
5. 系统生成岗位相关面试问题。
6. 用户选择系统生成的问题，或手动输入一道问题。
7. 用户提交该题答案。
8. 系统输出结构化单题评价。
9. 系统给出改进版回答、可能追问和下一题练习建议。

### 2.2 本 Feature 不包含

1. 自动联网搜索面经。
2. 招聘网站爬虫。
3. 自动投递。
4. 正式前端页面。
5. 登录注册。
6. 支付。
7. 企业 HR 端。
8. 多人协作。
9. 实时语音面试。
10. 直接处理音频文件。
11. PDF 报告导出。
12. 真实面试复盘主线。

## 3. 用户故事

### US-001 输入求职材料

作为求职者，我希望输入目标岗位 JD、我的简历和当前准备目标，以便系统知道我想准备什么岗位。

验收标准：

1. 用户可以提交简历文本或上传简历文件。
2. 用户可以粘贴目标岗位 JD。
3. 用户可以填写准备目标，例如“准备后端开发实习一面”。
4. 系统保存原始材料和提取文本。
5. 系统不自动联网搜索补充材料。

### US-002 生成岗位面试问题

作为求职者，我希望系统基于岗位和简历生成面试问题，以便我进行针对性练习。

验收标准：

1. 系统生成不少于 25 道题。
2. 题目分为 3 个模块：自我介绍定制题、后端岗位专业能力题、行为经历与项目深挖题。
3. 每个模块不少于 8 道题。
4. 每道题包含 `question_id`、问题正文、考察目的、难度、来源依据、JD 核心匹配关键词、高分回答框架、STAR 模板、评分锚点。
5. 行为经历与项目深挖题包含 1 到 2 个连环追问。
6. 项目追问必须基于用户简历中的真实项目或经历。
7. 如果材料不足，系统必须标注“基于综合推断”。

### US-003 提交单题答案

作为求职者，我希望选择一道题并提交自己的回答，以便获得针对这道题的反馈。

验收标准：

1. 用户可以从题库中选择一道题提交回答。
2. 用户也可以手动输入一道题和答案。
3. 如果选择题库题目，系统应加载题目评分锚点、简历画像和 JD 画像。
4. 用户答案以文本形式提交。

### US-004 获得结构化评价

作为求职者，我希望系统按照明确标准评价我的单题回答，以便知道哪里好、哪里需要改。

验收标准：

1. 系统输出总分，采用 100 分制。
2. 系统输出分项评分。
3. 系统说明表现好的地方。
4. 系统说明需要改进的地方。
5. 系统指出技术错误或表达风险。
6. 系统给出高分回答框架。
7. 系统给出改进版回答。
8. 系统给出可能的面试官追问。
9. 系统给出下一题练习建议。
10. 系统给出记忆更新建议。

## 4. 输入规格

### 4.1 必需输入

1. 简历。
   - 支持 PDF。
   - 支持 DOCX。
   - 支持 Markdown。
   - 支持纯文本。
2. 目标岗位 JD。
   - 支持用户粘贴文本。
   - 支持用户粘贴 Markdown。
3. 准备目标。
   - 文本输入。
   - 用于说明用户当前准备方向和面试阶段。

### 4.2 单题评价输入

1. 题目。
   - 可以来自系统生成的题库。
   - 可以由用户手动输入。
2. 用户答案。
   - 文本输入。
3. 推荐上下文。
   - 简历画像 `ResumeProfile`。
   - JD 画像 `JDProfile`。
   - 题目评分锚点。
   - 题目来源依据。

### 4.3 可选输入

1. 用户手动粘贴的面经。
2. 用户历史薄弱点。

可选输入只能增强题目生成和评分，不应成为系统自动联网搜索的入口。

## 5. 输出规格

### 5.1 面试问题输出

系统应输出 `QuestionBank`。

题库模块：

1. `self_intro_questions`：自我介绍定制题。
2. `professional_questions`：后端岗位专业能力题。
3. `behavior_project_questions`：行为经历与项目深挖题。

每道题字段：

1. `question_id`
2. `module`
3. `question_text`
4. `purpose`
5. `difficulty`
6. `source_type`
7. `source_refs`
8. `jd_keywords`
9. `answer_framework`
10. `star_template`
11. `scoring_anchors`
12. `follow_up_questions`
13. `preparation_advice`
14. `sort_order`

数量约束：

1. 总题量不少于 25 道。
2. 每个模块不少于 8 道。
3. 同一题库内 `question_id` 唯一。

### 5.2 单题评价输出

系统应输出 `AnswerEvaluation`。

字段：

1. `question_id`
2. `question_text`
3. `user_answer`
4. `total_score`
5. `dimension_scores`
6. `overall_comment`
7. `strengths`
8. `improvement_points`
9. `risks`
10. `improved_answer`
11. `follow_up_questions`
12. `next_practice_suggestion`
13. `memory_update`

评分维度：

1. 相关性：20 分。
2. 技术准确性：25 分。
3. 项目具体性：20 分。
4. 结构性：15 分。
5. 表达力：10 分。
6. 风险控制：10 分。

总分为 100 分。

## 6. 工作流

### 6.1 问题生成工作流

```text
保存简历材料
↓
保存 JD 材料
↓
保存准备目标
↓
解析 ResumeProfile
↓
解析 JDProfile
↓
可选解析 ExperienceProfile
↓
生成 MatchReport
↓
生成 QuestionBank
↓
推荐先练的 3 道题
```

说明：

1. 第一阶段可以用 mock Agent 打通流程。
2. 真实 LLM 调用必须通过 `LLMClient`。
3. Agent 输出必须通过 Pydantic Schema 校验后入库。

### 6.2 单题评价工作流

```text
加载题目或接收自定义题目
↓
加载用户答案
↓
加载 ResumeProfile 和 JDProfile
↓
加载题目评分锚点
↓
生成 AnswerEvaluation
↓
生成记忆更新建议
↓
保存评分结果
```

说明：

1. 单题评价不得脱离题目、JD 和简历上下文。
2. 改进版回答不得编造用户没有写过的经历。
3. 记忆更新不得把单次偶然失误直接写成长期问题。

## 7. API 需求

### 7.1 材料与解析

需要支持：

1. `POST /api/v1/documents/upload`
2. `POST /api/v1/documents/text`
3. `POST /api/v1/resumes`
4. `POST /api/v1/resumes/{resume_id}/parse`
5. `POST /api/v1/jobs`
6. `POST /api/v1/jobs/{job_description_id}/parse`

### 7.2 问题生成

需要支持：

1. `POST /api/v1/prep-packages`
2. `GET /api/v1/prep-packages/{prep_package_id}`
3. `GET /api/v1/prep-packages/{prep_package_id}/questions`

说明：

虽然接口命名使用 `prep-packages`，本 feature 的验收重点是其中的面试问题生成和推荐先练题。

### 7.3 单题评价

需要支持：

1. `POST /api/v1/evaluations`
2. `GET /api/v1/evaluations/{answer_evaluation_id}`
3. `GET /api/v1/evaluations`

## 8. 数据持久化需求

需要写入或读取以下数据对象：

1. `source_documents`
2. `resumes`
3. `resume_profiles`
4. `job_descriptions`
5. `jd_profiles`
6. `interview_experiences`
7. `experience_profiles`
8. `interview_prep_packages`
9. `match_reports`
10. `interview_questions`
11. `recommended_questions`
12. `answer_evaluations`
13. `memory_items`
14. `agent_runs`
15. `agent_run_steps`

本 feature 不要求实现：

1. `interview_reviews`
2. `quality_evaluations`

## 9. 质量约束

### 9.1 个性化

1. 问题必须围绕后端开发岗位。
2. 专业能力题必须对应 JD 核心职责或技术关键词。
3. 项目深挖题必须对应简历中的真实项目或经历。
4. 不输出大量通用泛化题。

### 9.2 证据性

1. 每道题必须包含来源依据。
2. 差距分析和题目推荐应尽量引用简历、JD 或面经来源。
3. 如果不是直接来自材料，必须标注为综合推断。

### 9.3 安全边界

1. 不编造用户没有写过的项目经历。
2. 不建议用户虚构学历、工作经验或项目成果。
3. 不把用户粘贴的面经说成确定真题。
4. 不自动联网搜索。

### 9.4 可执行性

1. 每道题必须有高分回答框架。
2. 每道题必须有评分锚点。
3. 单题评价必须说明扣分原因。
4. 改进版回答应能直接作为用户下一次练习的参考。
5. 下一题建议应围绕当前薄弱点。

## 10. 验收标准

### 10.1 问题生成验收

1. 给定简历和 JD，系统能生成题库。
2. 题库总数不少于 25 道。
3. 三个模块每个不少于 8 道。
4. 题目包含标准字段。
5. 行为经历与项目深挖题包含 1 到 2 个追问。
6. 项目追问不编造简历外经历。
7. 推荐先练 3 道题。

### 10.2 单题评价验收

1. 用户可以提交题库题目的答案。
2. 用户可以提交自定义题目和答案。
3. 系统输出总分和分项分数。
4. 系统解释扣分原因。
5. 系统指出至少 1 条具体改进建议。
6. 系统生成至少 1 个合理追问。
7. 系统给出下一题练习方向。
8. 改进版回答不编造用户经历。

### 10.3 技术验收

1. Agent 输出通过 Pydantic Schema 校验。
2. Agent 运行记录写入 `agent_runs`。
3. Agent 步骤记录写入 `agent_run_steps`。
4. 使用 mock Agent 也能跑通完整流程。
5. 单元测试覆盖题库数量和评分维度。
6. 集成测试覆盖问题生成和单题评价 API。
7. 端到端测试覆盖“输入简历 + JD -> 生成题库 -> 提交答案 -> 获得评价”。

## 11. 非目标

以下内容不作为本 feature 的验收条件：

1. Web 前端页面。
2. PDF 报告导出。
3. 真实语音输入。
4. 自动联网搜索。
5. 登录注册。
6. 企业端管理。
7. 真实面试复盘报告。
8. 质量评测后台。
