# Phase 2.4B 最终决策记录

日期：2026-10-20（Asia/Singapore）

**结论：Candidate 不通过，不晋升生产基线。生产默认仍为 QuestionBankAgent。**

评分来源：AI（Codex assistant）离线盲评，不是人工评分。正文先评分并冻结，再评 metadata。原始评分不修改。

## 最终门禁

| 门禁 | 状态 | 观测值 |
| --- | --- | --- |
| candidate_real_success_gte_90pct | pass | 1.0 |
| each_case_real_success_gte_4_of_5 | pass | {"backend_go_case": 5, "backend_java_case": 5, "backend_python_case": 5} |
| cross_stack_runs_eq_0 | pass | 0 |
| duplicate_runs_eq_0 | pass | 0 |
| output_token_reduction_gte_40pct | not_evaluable | null |
| candidate_average_output_tokens_lte_1800 | fail | 2067.4615 |
| output_token_efficiency_gate | not_evaluable | "none" |
| candidate_p95_lte_90s | pass | 46051 |
| candidate_max_lte_120s | pass | 46051 |
| user_visible_quality_gte_4 | pass | 4.2667 |
| metadata_fit_gte_3_5 | fail | 2.6347 |

Candidate 15/15 real，正文综合质量 4.2667/5；Schema、assembler、严格 8/8/9、技术栈边界、重复检查均为 15/15 通过。metadata_fit=2.6347/5，低于 3.5，构成明确失败门禁。

Token 相对效率只有 1 个可比较 pair，少于 3，不能判为通过。绝对输出均值 2067.4615（13 个 usage 完整执行）高于 1800，但该替代阈值未启用为 gating。Token 效率保留未解决状态，由独立阶段处理；2.4C 不修改模型输出链路。

## 27 题异常归属

`submission-34d60ed744aa45f7` 对应 baseline、backend_python_case、pair 4、real，题数分布为 {'self_intro': 9, 'professional': 9, 'behavior_project': 9}。最终 Schema 的宽松最小数量允许其解析，但独立 strict_count 检查失败。它不属于 Candidate，不能据此否定 Candidate 的 15/15 数量合规结果。

该 submission 的历史盲评模板仅有 25 个 metadata 评分槽，完成评分只覆盖位置 1–25；第 26–27 题未进入 metadata 均值。这个 baseline 评分限制不影响 Candidate 的 375 题统计，也不能作为 Candidate 晋升依据。

## 后续决策

只批准独立的确定性 assembler metadata v2 离线校准与新的匿名 metadata 盲评。结构及确定性检查不等同于语义质量门槛；未取得新的独立盲评分数前，不宣布 metadata_fit 达标。

run2 目录及其 manifest、报告、盲评包、原评分全部只读。本记录保存在目录之外，不重新 finalize，不启动真实 A/B。
