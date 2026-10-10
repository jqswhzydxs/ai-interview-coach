# Agent Prompt 与路由设计 v0.1

## 1. 设计目标

第一版采用轻量 Harness 管理多 Agent 工作流。

目标：

1. 明确每个 Agent 的职责边界。
2. 明确 Agent 输入与输出 schema。
3. 保留 Prompt 版本。
4. 对结构化输出做校验。
5. 失败时可重试或降级。

## 2. Harness 职责

Harness 负责：

1. 接收业务任务。
2. 读取数据库材料。
3. 调用对应 Agent。
4. 保存 Agent 运行日志。
5. 校验输出 schema。
6. 将结构化结果写入数据库。
7. 组装最终报告。
8. 调用 Memory Agent 更新长期记忆。

Harness 不负责具体内容生成。

## 3. Agent 列表

### 3.1 Document Parser

输入：

1. 文件路径或粘贴文本。
2. 文档类型。

输出：

1. 标准化文本。
2. 文档元信息。

说明：这个模块可以先作为工具，不一定调用大模型。

### 3.2 Resume Analyzer Agent

输入：

1. 简历文本。

输出：

1. `ResumeProfile`。

职责：

1. 提取技能、项目、经历。
2. 标注后端能力。
3. 识别可追问点和风险点。

### 3.3 JD Analyzer Agent

输入：

1. JD 文本。

输出：

1. `JDProfile`。

职责：

1. 拆解岗位职责。
2. 提取硬性要求、加分项、技术关键词。
3. 识别后端能力维度。

### 3.4 Experience Analyzer Agent

输入：

1. 用户粘贴的面经或历史面试记录。
2. 可选 JDProfile。

输出：

1. `ExperienceProfile`。

职责：

1. 提取高频问题。
2. 提取高频知识点。
3. 提取追问模式。

### 3.5 Matching Agent

输入：

1. `ResumeProfile`。
2. `JDProfile`。
3. 可选 `ExperienceProfile`。

输出：

1. `MatchReport`。

职责：

1. 生成匹配度。
2. 说明优势和差距。
3. 给出简历修改建议。
4. 给出准备优先级。

### 3.6 Question Bank Agent

输入：

1. `ResumeProfile`。
2. `JDProfile`。
3. `MatchReport`。
4. 可选 `ExperienceProfile`。
5. 可选 `MemoryItem` 列表。

输出：

1. `QuestionBank`。

职责：

1. 生成不少于 25 道题。
2. 保证三个模块每个不少于 8 道题。
3. 为每题生成 `question_id`、高分框架、STAR 模板、评分锚点。

### 3.7 Prep Manual Agent

输入：

1. `ResumeProfile`。
2. `JDProfile`。
3. `MatchReport`。
4. `QuestionBank`。

输出：

1. `PrepManual`。

职责：

1. 生成回答加分点。
2. 生成回答雷点。
3. 生成现场话术和反问建议。

### 3.8 Answer Evaluator Agent

输入：

1. 面试题。
2. 用户回答。
3. 题目评分锚点。
4. `ResumeProfile`。
5. `JDProfile`。

输出：

1. `AnswerEvaluation`。

职责：

1. 按 100 分制评分。
2. 给分项分数和扣分原因。
3. 生成改进版回答。
4. 生成追问和下一题建议。

### 3.9 Memory Agent

输入：

1. `AnswerEvaluation`。
2. 历史 `MemoryItem`。

输出：

1. 需要新增或更新的 `MemoryItem`。

职责：

1. 只记录有证据的长期倾向。
2. 不把单次偶然失误直接写成长期问题。
3. 标注置信度。

## 4. 工作流路由

### 4.1 生成完整面试备战包

```text
parse_resume
↓
parse_jd
↓
parse_experiences
↓
match_resume_to_jd
↓
generate_question_bank
↓
generate_prep_manual
↓
assemble_interview_prep_package
↓
render_markdown
```

### 4.2 单题模拟回答评分

```text
load_question
↓
load_resume_profile_and_jd_profile
↓
evaluate_answer
↓
update_memory
↓
save_answer_evaluation
```

## 5. Prompt 版本命名

建议格式：

```text
resume_analyzer_v0.1
jd_analyzer_v0.1
experience_analyzer_v0.1
matching_agent_v0.1
question_bank_agent_v0.1
prep_manual_agent_v0.1
answer_evaluator_v0.1
memory_agent_v0.1
```

每次改 Prompt，都应该更新版本号。

## 6. 输出校验规则

每个 Agent 输出后必须：

1. 解析为 Pydantic schema。
2. 校验必填字段。
3. 校验数量约束，例如题目不少于 25 道。
4. 校验不编造用户经历。
5. 保存原始输出摘要和校验结果。

## 7. 失败处理

建议策略：

1. schema 校验失败：自动重试一次。
2. 数量不达标：带着错误原因重试一次。
3. 内容疑似编造：标记为需要人工检查或降级输出。
4. 多次失败：保存失败状态到 `agent_runs`，返回明确错误。

## 8. Prompt 边界原则

所有 Agent 必须遵守：

1. 不编造用户没有写过的项目经历。
2. 不建议用户虚构学历、工作经验或项目成果。
3. 面经只能作为参考，不可说成确定真题。
4. 如果材料不足，必须标注“基于综合推断”。
5. 输出要有证据引用。

