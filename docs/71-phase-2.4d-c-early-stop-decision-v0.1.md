# Phase 2.4D-C 提前停止决策记录

决策日期：2026-10-22。

## 决策

`decision_status = stopped_for_engineering_futility`

停止 ab1 的后续数据采集，不执行 Full、blind review 或 finalize。Prompt v0.2 不晋升，生产默认 Agent 不变。

## 依据

- 3 个 paired Pilot 的 baseline output tokens 合计 9,271，candidate 合计 10,197；candidate 增加 9.988%，方向与至少降低 10% 的目标相反。
- candidate 平均 output tokens 为 3,399，高于 1,800 目标。
- candidate 可见题目字符已减少 58.372%，但 output tokens 没有下降；继续只扩大同一 Prompt-only 实验缺少工程收益依据。
- candidate P95 为 106,529 ms，高于最终 90 秒门槛。
- candidate 出现一次 timeout 后 retry，最终 response usage 完整，但该 execution billing usage incomplete。

## 正式门禁状态

`formal_final_gate_status = not_evaluable`

本记录不是预注册 Full 的完成记录，也不是正式统计拒绝。当前只有 3 个 comparable pair，少于正式要求的 12 个；Full、盲评和 finalize 均未执行。ab1 原报告仍保持 `pilot_passed / completion_status=not_started`，本记录不会覆盖或重新解释其原始状态。

## 冻结确认

- ab1 全目录保持只读；
- readiness ledger 保持只读；
- Prompt v0.1/v0.2、metadata v2、Schema、fixtures、模型及生成参数保持不变；
- 没有创建 Prompt v0.3；
- 没有访问 Provider；
- 没有切换生产 `QuestionBankAgent`。

机器可读决定见 `storage/reports/question-bank-token-phase-2-4d-c-offline-20261022/early-stop-decision.json`。
