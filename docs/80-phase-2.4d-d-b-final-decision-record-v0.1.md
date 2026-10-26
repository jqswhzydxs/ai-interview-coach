# Phase 2.4D-D-B Final Decision Record v0.1

## 决策

- Protocol v3 最终结论为 `fail`。
- `thinking.type=disabled` 不接入生产。
- Prompt v0.2、`QuestionBankMetadataAssemblerV2` 与 non-thinking 的组合不晋升。
- 生产默认 `QuestionBankAgent` 保持 `question_bank_agent_v0.1`，本阶段没有切换默认实现或配置。
- 不进入前端开发阶段。
- 下一状态为等待 Phase 2.4D-E-A 离线协议实现授权。

该决策直接应用 Protocol v3 已注册的规则：任一必需门禁失败即拒绝 Candidate。它没有重新 finalize、改写门禁或重新解释历史结果。

## 冻结证据

以下源证据在分析前纳入 SHA-256 基线，并在分析及验证后逐文件复核：

- readiness v3 ledger；
- ab1 manifest；
- audit executions 与 private blinding map；
- blind review packet 与 template；
- completed review；
- JSON/Markdown 最终报告。

本阶段只读取这些资产。独立输出位于 `storage/reports/question-bank-token-phase-2-4d-d-b-offline-20261023`。未创建 Prompt、readiness ledger 或真实实验目录。

## 最终门禁证据

| 指标 | 结果 | 门禁 |
|---|---:|---|
| Candidate real safe | 15/15 | 通过 |
| Candidate 平均 output tokens | 680.5333 | 通过 `<=1800` |
| paired output-token reduction | 81.5009% | 通过 `>=10%` |
| Candidate P95 / max latency | 10.012s / 10.012s | 通过 |
| Candidate metadata fit | 3.8160 | 通过 `>=3.5` |
| Candidate text quality | 3.7733 | **失败** `<4.0` |
| Candidate 相对 baseline 正文质量 | -0.6000 | **失败**，下降超过 0.2 |
| 配对正文质量 | 1 win / 1 tie / 13 loss | 支持退化判断 |

完成的独立盲评 evaluator 类型明确为 **AI**，identifier 为 `codex-independent-v3-review-20261023`；不得表述为人工评审。

## Timeout 与 Token 结论边界

Baseline 的 Go pair 3 首次 attempt timeout，第二次获得 real、安全有效的成功响应。成功响应 usage 三字段完整：input 1037、output 3785、total 4822，因此该 pair 符合已注册的成功响应 Token 比较规则。

失败 attempt usage 未知，整次执行的 billing usage 为 incomplete，input/output/total 4822 只能作为已知 Token 下界。这个缺口不改变 Protocol v3 对最终成功响应 output tokens 的比较结论，也不能被解释为完整账单成本。

## 机器记录

- `storage/reports/question-bank-token-phase-2-4d-d-b-offline-20261023/final-decision-record.json`
- `storage/reports/question-bank-token-phase-2-4d-d-b-offline-20261023/phase-2.4d-d-b-analysis.json`

