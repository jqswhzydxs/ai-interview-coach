# Phase 2.4B：QuestionBank 配对式真实 A/B Spec v0.1

## 1. 实验目标

只比较 Phase 2.4A 保留的两个 QuestionBank 实现：

- baseline：`QuestionBankAgent` + `question_bank_agent_v0.1` + 最终 `QuestionBank` Schema；
- candidate：`QuestionBankDraftAgent` + `question_bank_draft_agent_v0.1` + `QuestionDraftBank` + deterministic assembler。

实验不运行 Resume、JD、Experience、Matching、Evaluation、Memory Agent，不修改生产默认 Agent，不切换运行时基线。

## 2. 冻结输入与唯一变量

实验使用 `tests/fixtures/question_bank_ab_inputs_v1.json` 中三套脱敏、合成、结构化上游输入。每套包含 `resume_profile`、`jd_profile`、`experience_profiles`、`match_report` 和 `preparation_goal`，不包含原始简历/JD文本。

同一个 runner、provider client、model、temperature=0.2、max attempts=2、120 秒单次绝对截止时间和运行窗口内交替执行两个 variant。唯一协议变量是模型输出契约及候选 assembler。

## 3. 配对计划

- 3 cases × 5 pairs × 2 variants = 30 次 QuestionBank Agent 执行。
- pilot 是正式 pair 1，不额外增加样本。
- full 只续跑 pair 2–5。
- 奇数 pair：baseline → candidate。
- 偶数 pair：candidate → baseline。
- 每次记录实际全局 sequence、pair 内 order、开始和结束时间。

## 4. 分阶段门禁

1. `smoke`：一次最小 provider JSON smoke。
2. `pilot`：三个 case 各执行 pair 1，共 6 次。
3. pilot 只有在 6 次均得到最终合法 8/8/9 QuestionBank、无跨栈、无实质重复时才通过；fallback 允许通过 pilot，但必须显式记录。
4. `full`：pilot passed 后续跑剩余 24 次。
5. `finalize`：对盲评包完成评分后汇总 real-only 与 user-visible 质量并判定门槛。

任一阶段失败、超时、资产变更或预算停止后，状态为明确的 `incomplete_*`/`invalidated_*`，不能静默恢复或把不完整实验标记为完成。

## 5. 截止、并发与预算

- Agent 直接在当前 asyncio task 中等待，不创建后台 task。
- `asyncio.timeout` 对每次 Agent 执行实施不超过 120 秒的绝对截止时间；取消向下传播到 provider 请求。
- 项目级 `storage/reports/.question-bank-ab.lock` 使用原子独占创建，阻止并发验收进程。
- 默认最大 provider calls=61：1 次 smoke + 30 次执行 × 最多 2 attempts。
- 默认最大 total tokens=250,000；每次响应后更新 manifest，超过预算立即停止并输出不完整报告。
- 成功响应缺少 total token usage 时停止，因为无法证明 token 预算；无响应的失败调用单独计数，不伪造 usage。

## 6. 资产冻结

首次 smoke 前记录下列 SHA-256：

- baseline/candidate Agent 与 BaseAgent；
- baseline/candidate Prompt；
- final/draft Schema；
- assembler；
- 冻结输入文件。

pilot/full 每次执行前及阶段结束后复核。任何变化立即停止为 `invalidated_assets`。

## 7. 每次执行记录

每次记录 variant、case、pair、实际顺序、real/fallback、真实 provider calls、retry、failure types、wall-clock latency、input/output/total tokens、最终 Schema、严格计数、candidate assembler、技术栈边界、精确/近重复检查和输出指纹。

报告不保存 provider `raw_text` 或完整结构化响应。问题文本及用于评分的 metadata 只进入独立盲评包；主报告不包含完整上游输入或完整 QuestionBank。

## 8. 盲评

问题文本包隐藏 variant、pair 和执行顺序。每份输出按 1–5 评分：

- 个性化；
- 技术正确性与技术栈边界；
- 主题覆盖与实质多样性；
- 面试训练价值；
- 表达清晰度。

metadata 使用独立盲评包，对 25 道题逐题评价 purpose、source、framework、anchors、follow-up 和 advice 与题目的适配度。完成评分后才按 submission id 解盲汇总。

## 9. 通过门槛

- candidate real success ≥ 90%；
- 每 case candidate real ≥ 4/5；
- candidate 跨栈和重复 run 均为 0；
- candidate output tokens 相对 baseline 至少下降 40%；
- candidate p95 ≤ 90 秒，max ≤ 120 秒；
- candidate user-visible 综合质量 ≥ 4/5；
- candidate user-visible metadata 适配度 ≥ 3.5/5。

real-only 和包含 fallback 的 user-visible 质量必须分别报告；任一门槛失败即候选不通过。

## 10. 安全

- 不记录或打印 API key、Authorization header。
- 不把完整结构化上游输入复制到报告。
- 不保存 raw provider response。
- `SAVE_FULL_LLM_LOGS=false` 是真实入口的强制条件。
- 不硬编码 provider 价格。

