# Phase 2.4A：QuestionBank 最小草稿协议 Spec v0.1

## 1. 证据与目标

最终真实验收中 question-bank 只有 2/9 次真实成功、7/9 次 fallback、8/9 次发生重试，平均延迟 331.904 秒；Prompt v0.2 A/B 虽把真实成功提高到 3/9，但 question-bank 总 token 增加 9.19%，Java 从 2/3 real 回退为 0/3，候选已拒绝并回滚。

因此本阶段不继续通过扩写 Prompt 让模型直接生成完整 `QuestionBank`，而是降低单次响应协议复杂度：模型只生成 25 道问题核心文本，确定性字段由后端 assembler 补齐。本阶段只做离线代码与 fake-provider 验证，不能把结果解释为真实 provider 已改善。

## 2. 基线与候选并存

- 基线保持 `QuestionBankAgent` + `question_bank_agent_v0.1` + 最终 `QuestionBank` Schema，运行时引用不变。
- 新增独立候选 `QuestionBankDraftAgent` + `question_bank_draft_agent_v0.1`。
- 两个类可在同一 Python 进程中分别实例化；不修改全局 Prompt 指针，不通过覆盖类属性切换。
- acceptance runner 通过构造参数注入 question-bank agent factory；默认 factory 仍为基线。
- 不修改 API、数据库表和最终持久化结构。

## 3. 内部最小草稿协议

内部 Schema 不对外暴露：

```text
QuestionDraft
└── question_text: 非空字符串

QuestionDraftBank
├── self_intro_questions: 恰好 8 个 QuestionDraft
├── professional_questions: 恰好 8 个 QuestionDraft
└── behavior_project_questions: 恰好 9 个 QuestionDraft
```

模型不负责以下可确定计算字段：

- `question_id`、`module`、`sort_order`、`total_count`；
- `purpose`、`difficulty`；
- `source_type`、`source_refs`、`jd_keywords`；
- `answer_framework`、`star_template`；
- `scoring_anchors`、`follow_up_questions`、`preparation_advice`。

内部 Schema 使用 `extra=forbid`，数量必须严格为 8/8/9。最终输出仍必须完整通过现有 `QuestionBank` Schema，不放宽任何最终字段或业务约束。

## 4. 单次调用与重试边界

候选每个 provider attempt 只发送一个 `QuestionDraftBank` 请求，不能按三个模块拆成三个请求。Phase 2.1 的 `BaseAgent` 仍是唯一重试所有者，最多 2 个 attempt，即最多 1 次重试；Harness 和 acceptance runner 不重试。

`BaseAgent.run_with_fallback` 增加可选的成功输出 transform：provider 响应先通过 Draft Schema，再在同一个 attempt 内由 assembler 转换成最终 QuestionBank。transform/assembler 失败按 schema failure 处理并进入原重试/fallback 流程，不增加另一层调用循环。

## 5. Deterministic Assembler

assembler 的输入为已验证的 `QuestionDraftBank` 和当前完整上下文，输出为最终 `QuestionBank`。职责：

1. 再次确认严格 8/8/9 和总数 25。
2. 按列表确定 module，并生成连续的 `self-01..08`、`pro-01..08`、`beh-01..09`。
3. 对 Unicode、大小写、空白、标点和纯编号后缀做规范化，确保 25 道问题唯一。
4. 拒绝只靠编号或极小文本变化制造的近重复问题。
5. 技术栈只允许使用 resume/JD 结构化字段中出现的已知技术；matching 只影响考察重点，不能引入新技术事实。
6. 从当前 resume/JD/experience 上下文确定 source refs；不得接受模型自报的 source metadata。
7. 复用 Phase 2.3 已验证的确定性元数据模板，生成回答框架、评分锚点、追问和建议。
8. 对组装结果执行最终 `QuestionBank.model_validate()`，并复核 module、ID、sort order、来源非空和文本唯一性。

## 6. 失败与 fallback

下列任一情况视为候选 schema failure：

- Draft JSON/Schema 不合法；
- 不是严格 8/8/9；
- 规范化后文本重复或近重复；
- 出现上下文外已知技术栈；
- 证据来源不可生成；
- 组装后的最终 QuestionBank 不通过现有 Schema。

重试耗尽后，调用当前 `QuestionBankAgent._rule_based_question_bank(input_data)`，即 Phase 2.3 已验证的上下文安全 fallback。AgentRun 继续显式记录 `execution_mode=fallback`、schema failure、真实调用数、重试数和 fallback reason，不隐藏降级。

mock 模式不模拟模型质量，直接使用同一个 Phase 2.3 安全 fallback 并记录 `execution_mode=mock`；assembler 的成功和失败由 fake-real-provider 测试覆盖。

## 7. 非目标与不可变项

- 不修改 provider client、model、temperature、timeout、重试次数。
- 不修改 Resume、JD、Experience、Matching、Evaluation、Memory Agent。
- 不修改基线 Prompt v0.1 或已拒绝的 v0.2 资产。
- 不修改外部 API、数据库和前端。
- 不调用真实 provider。

## 8. 验收标准

1. 基线与候选在同一进程各自构建请求，prompt_version 和 response Schema 互不污染。
2. 成功候选恰好调用 fake provider 1 次，返回完整且可持久化的 QuestionBank。
3. Draft 输出契约的字段数量和序列化 Schema 大小显著小于最终 QuestionBank 契约。
4. assembler 对三个 sample cases 生成 8/8/9、25 道规范化唯一问题，无跨技术栈。
5. 计数错误、重复题、串栈、无证据和最终 Schema 错误均显式重试，耗尽后进入原安全 fallback。
6. acceptance runner 可通过显式 factory 分别运行基线和候选，默认仍为基线。
7. 本机 `.env` 保留时全量离线测试通过，pytest 报告真实 socket 尝试为 0。
