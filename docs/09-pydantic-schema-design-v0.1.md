# Pydantic Schema 设计 v0.1

## 1. 设计目标

Pydantic Schema 用于统一：

1. Agent 结构化输出。
2. API 请求与响应。
3. 数据库存储到 `jsonb` 的结构。
4. 测试和评测基准。

第一版采用 Pydantic v2。

## 2. 通用类型

### 2.1 EvidenceRef

用于标记结论来源。

字段：

1. `source_type`：`resume`、`jd`、`experience`、`answer`、`inferred`。
2. `source_id`：可选，数据库 ID。
3. `quote`：可选，原文片段。
4. `summary`：来源说明。

### 2.2 ScoreItem

字段：

1. `name`：评分项名称。
2. `score`：得分。
3. `max_score`：满分。
4. `reason`：原因。

### 2.3 ActionItem

字段：

1. `title`。
2. `priority`：`high`、`medium`、`low`。
3. `description`。
4. `expected_time`：可选。

## 3. ResumeProfile

字段：

1. `basic_info`：基本信息。
2. `education`：教育背景列表。
3. `skills`：技能列表。
4. `projects`：项目经历列表。
5. `work_experiences`：实习或工作经历列表。
6. `awards`：奖项、证书、竞赛等。
7. `backend_tags`：后端能力标签。
8. `questionable_points`：可追问点。
9. `risk_points`：表达风险点。

项目经历建议字段：

1. `name`。
2. `role`。
3. `background`。
4. `tech_stack`。
5. `responsibilities`。
6. `highlights`。
7. `metrics`。
8. `evidence_refs`。

## 4. JDProfile

字段：

1. `job_title`。
2. `company_name`：可选。
3. `job_level`：可选。
4. `core_responsibilities`。
5. `hard_requirements`。
6. `bonus_points`。
7. `tech_keywords`。
8. `backend_dimensions`。
9. `interview_focuses`。
10. `evidence_refs`。

后端能力维度建议：

1. `language`。
2. `web_framework`。
3. `database`。
4. `cache`。
5. `middleware`。
6. `system_design`。
7. `engineering_practice`。
8. `communication`。

## 5. ExperienceProfile

字段：

1. `source_summary`。
2. `frequent_questions`。
3. `frequent_topics`。
4. `follow_up_patterns`。
5. `jd_related_points`。
6. `resume_related_points`。
7. `evidence_refs`。

## 6. MatchReport

字段：

1. `overall_score`：0-100。
2. `summary`。
3. `matched_strengths`。
4. `missing_capabilities`。
5. `expression_issues`。
6. `risk_points`。
7. `resume_suggestions`。
8. `preparation_priorities`。
9. `evidence_refs`。

每条建议建议包含：

1. `target_section`：简历位置。
2. `problem`。
3. `suggestion`。
4. `example_rewrite`。
5. `evidence_refs`。

## 7. InterviewQuestion

字段：

1. `question_id`。
2. `module`：`self_intro`、`professional`、`behavior_project`。
3. `question_text`。
4. `purpose`。
5. `difficulty`：`basic`、`medium`、`hard`。
6. `source_type`：`resume`、`jd`、`experience`、`inferred`、`mixed`。
7. `source_refs`。
8. `jd_keywords`。
9. `answer_framework`。
10. `star_template`。
11. `scoring_anchors`。
12. `follow_up_questions`。
13. `preparation_advice`。
14. `sort_order`。

## 8. QuestionBank

字段：

1. `self_intro_questions`。
2. `professional_questions`。
3. `behavior_project_questions`。
4. `total_count`。

校验规则：

1. 总题量不少于 25。
2. 每个模块不少于 8 道。
3. `question_id` 在同一个题库内唯一。

## 9. PrepManual

字段：

1. `bonus_points`：不少于 8 条。
2. `red_flags`：不少于 6 条。
3. `resume_alignment_tips`。
4. `speaking_tactics`。
5. `reverse_question_tactics`。

加分点字段：

1. `title`。
2. `recommended_expression`。
3. `jd_match_detail`。
4. `metric_expression_tip`。
5. `related_resume_section`。

雷点字段：

1. `title`。
2. `bad_expression`。
3. `negative_impression`。
4. `better_expression`。

## 10. InterviewPrepPackage

字段：

1. `overview`。
2. `jd_breakdown`。
3. `match_report`。
4. `resume_suggestions`。
5. `preparation_priorities`。
6. `question_bank`。
7. `prep_manual`。
8. `recommended_questions`。
9. `action_items`。
10. `rendered_markdown`：可选。

展示顺序必须遵守：

```text
备战总览 -> JD 拆解 -> 差距分析 -> 简历建议 -> 准备优先级 -> 题库 -> 手册 -> 先练 3 题 -> 行动清单
```

## 11. AnswerEvaluation

字段：

1. `question_id`：可选。
2. `question_text`。
3. `user_answer`。
4. `total_score`。
5. `dimension_scores`。
6. `overall_comment`。
7. `strengths`。
8. `improvement_points`。
9. `risks`。
10. `improved_answer`。
11. `follow_up_questions`。
12. `next_practice_suggestion`。
13. `memory_update`。

分项评分：

1. 相关性：20 分。
2. 技术准确性：25 分。
3. 项目具体性：20 分。
4. 结构性：15 分。
5. 表达力：10 分。
6. 风险控制：10 分。

## 12. MemoryItem

字段：

1. `memory_type`：`weakness`、`strength`、`preference`、`target_role`、`project_pattern`。
2. `category`。
3. `content`。
4. `evidence`。
5. `confidence`。
6. `source_type`。
7. `source_id`：可选。
8. `status`：`active`、`archived`、`rejected`。

## 13. Schema 版本管理

每个 Agent 输出对象建议带：

1. `schema_version`。
2. `generated_at`。
3. `agent_name`。
4. `prompt_version`。

这样后续 Prompt 或 schema 变化时，可以回溯旧数据。

