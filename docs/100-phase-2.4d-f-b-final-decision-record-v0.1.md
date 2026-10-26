# Phase 2.4D-F-B Final Decision Record

## 正式决策

- Protocol v5 已完成并正式判定为 `fail`。
- Prompt v0.3 状态固定为 `research_candidate_not_promoted`，不接入生产、不删除、不覆盖，也不设为默认。
- 生产默认 `QuestionBankAgent` 继续使用 `question_bank_agent_v0.1`。
- 不事后放宽任何门禁，不追加第二评审，不重跑同一 v5 协议以寻找通过样本。
- 不创建 Prompt v0.4；当前连续 Prompt 微调路线停止。
- 后续模型研究如需继续，必须作为新的模型与人工评审项目重新立项，使用独立协议、数据和授权。

## 决策依据

Protocol v5 的 Candidate 15/15 real safe，平均 output tokens 为 788，P95/max latency 为 12.409 秒，正文综合质量为 4.16，metadata fit 为 3.896。这些门禁均通过。

以下三个必需门禁失败：

| 门禁 | 实际值 | 要求 | 结果 |
|---|---:|---:|---|
| 相对 Baseline 正文质量提升 | +0.1733 | ≥0.2 | 失败 |
| Technical correctness / stack boundary | 3.9333 | ≥4.0 | 失败 |
| Coverage / substantive diversity | 3.8667 | ≥4.0 | 失败 |

Personalization=4.4667、interview training value=4.5333、clarity=4.0 均通过。15 个配对正文结果为 10 win / 3 tie / 2 loss，但预注册规则要求全部必需门禁通过，因此多数配对获胜不能覆盖三个门禁失败。

独立评审的 evaluator 类型是 **AI**，identifier 为 `codex-independent-v5-review-20261024`。本记录不得将其描述为人工评审。

## 冻结与禁止事项

本阶段以 SHA-256 冻结 readiness v5、ab1、manifest、JSON/Markdown report、audit、private blinding map、盲评 packet/template、completed review、Prompt v0.2/v0.3、v5 实现和生产默认文件。分析只读取这些证据，没有重新 finalize、重新评分或写入源目录。

Prompt v0.3 保留为研究候选资产。任何未来工作不得借修改标签、增加评审或选择性重跑来改变 v5 的正式失败结论。

## 项目状态

模型研究与前端开发从此解耦。后端 API 与 degraded/fallback 合约可以进入 Phase 2.5 冻结设计；前端 Mock 和 API 契约开发可以在下一阶段授权后开始，但不得假设 Prompt v0.3 已晋升，也不得切换生产 Agent。

下一状态：`await_phase_2_5_frontend_contract_freeze_and_mock_scaffold_authorization`。
