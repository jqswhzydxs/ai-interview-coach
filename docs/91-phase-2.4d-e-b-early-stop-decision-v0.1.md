# Phase 2.4D-E-B Early Stop Decision

## 正式记录

- 决策状态：`stopped_for_engineering_futility`
- Protocol v4 原始状态：`pilot_passed`
- Full：`not_started`
- Pilot 执行门禁：通过
- 正式 Full/Token/质量门禁：`not_evaluable`
- 正式统计拒绝：否
- low-effort candidate 晋升：否

本记录是独立离线决策，不回写 protocol v4 manifest、report、audit 或 readiness ledger。它明确停止后续 Full、盲评和 finalize。生产默认 `QuestionBankAgent` 保持不变。

## 决策依据

Candidate Pilot 平均 output tokens 为 4750。若 15 次最终均值要达到≤1800，剩余 12 次必须平均≤1062.5，而当前最小值为 2171。Candidate reasoning tokens 在 1457–6674 之间波动；75 道题平均 98.2267 字符，其中 38 道超过模块建议上限。Go candidate 还发生一次 usage 未知的 network failure，账单总量只有下界。

这些结果足以形成工程性提前停止判断，但不证明未来 12 次在数学上不可能达到目标，也不等于完成预注册 Full 或得到正式统计拒绝。正式门禁继续保持 `not_evaluable`。

## 禁止解释

不得把 12.0967% 描述性 reduction 写成正式 Token 门禁通过；不得把字符长度当作 Token 或质量替代指标；不得混用 v3/v4 数据；不得通过放宽正文质量门槛推进 candidate。
