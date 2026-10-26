# Phase 2.4D-D-B Offline Validation Report v0.1

## 范围

本阶段仅实现离线、只读的 finalize 后分析。没有 Provider 请求、Prompt/Schema/metadata v2/生产配置变更，没有创建或执行新的 readiness，也没有创建真实 A/B 目录。

新增实现：

- `app/services/question_draft_reasoning_final_analysis.py`：冻结证据校验、解盲聚合、五维/技术栈/模块/相关性统计、timeout 记账和下一协议建议；
- `scripts/analyze_question_draft_reasoning_v3_final.py`：离线生成四个确定性 JSON；
- `tests/integration/test_question_draft_reasoning_final_analysis.py`：7 项专项覆盖。

## 验证结果

| 检查 | 结果 |
|---|---|
| 专项测试 | 7 passed |
| 全量离线测试 | 416 passed, 1 skipped |
| Smoke 跳过原因 | 真实 LLM smoke 默认禁用 |
| Socket guard | real socket attempts = 0 |
| compileall | passed |
| git diff --check | passed |
| 冻结资产哈希 | 189/189 unchanged |
| 生产默认 Agent | `QuestionBankAgent` / `question_bank_agent_v0.1` unchanged |
| Provider calls | 0 |

全量测试中的唯一 warning 为 Starlette `TestClient` 的既有 deprecation warning，与本阶段改动无关。

## 专项覆盖

- 冻结 v3 verdict、AI evaluator、Token 与质量事实匹配；
- 五个正文维度的 baseline/candidate 均值和差值；
- Go、Java、Python 分组和 15 pair 的 1/1/13；
- 三模块计数、metadata 分布和长度/评分相关性；
- baseline timeout 后成功、失败 attempt usage unknown、billing 下界与成功响应可比较语义；
- 推荐协议严格只改变 `reasoning_effort`，禁止放宽质量门槛；
- 输出确定性、脱敏，并拒绝写入 readiness/ab1；
- 生产默认 Agent 与 189 个实施前保护文件保持不变。

## 产物

- `storage/reports/question-bank-token-phase-2-4d-d-b-offline-20261023/final-decision-record.json`
- `storage/reports/question-bank-token-phase-2-4d-d-b-offline-20261023/quality-regression-analysis.json`
- `storage/reports/question-bank-token-phase-2-4d-d-b-offline-20261023/next-single-variable-recommendation.json`
- `storage/reports/question-bank-token-phase-2-4d-d-b-offline-20261023/phase-2.4d-d-b-analysis.json`
- `storage/reports/question-bank-token-phase-2-4d-d-b-offline-20261023/protected-assets-before.json`
- `storage/reports/question-bank-token-phase-2-4d-d-b-offline-20261023/protected-assets-after.json`
- `storage/reports/question-bank-token-phase-2-4d-d-b-offline-20261023/offline-validation-report.json`

结论：离线收口通过；Protocol v3 的产品结论仍为失败，Candidate 不晋升。等待 Phase 2.4D-E-A 离线协议实现授权。
