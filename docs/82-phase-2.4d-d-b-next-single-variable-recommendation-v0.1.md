# Phase 2.4D-D-B Next Single-Variable Recommendation v0.1

## 推荐

下一阶段优先验证 `reasoning_effort=low`，同时保持 thinking enabled。建议建立全新协议，严格采用：

- Baseline：`thinking.type=enabled` + `reasoning_effort=high`；
- Candidate：`thinking.type=enabled` + `reasoning_effort=low`；
- 唯一组间变量：`reasoning_effort`；
- 两侧共同冻结 Prompt v0.2、`QuestionBankMetadataAssemblerV2`、Schema、`deepseek-v4-pro`、temperature、max_tokens、retry、fallback、deadline、fixtures、计数与顺序、安全检查和 API 合约。

Protocol v3 的 enabled arm 没有显式 `reasoning_effort=high`，不能充当新协议 Baseline。新协议必须建立新的预注册和 readiness，并从零完整重跑两侧；v3 Token 或质量数据不得混入。

本阶段只提出建议，没有实现请求参数、创建 ledger、访问 Provider 或建立真实实验目录。

## 方案比较

| 方案 | 处置 | 价值 | 主要风险 |
|---|---|---|---|
| thinking enabled + `reasoning_effort=low` | 优先 | 保留与 v3 较强正文质量同时出现的 thinking 条件，只改变推理强度，直接测试 Token/延迟 | 必须离线证明 Provider/SDK 不丢字段；质量仍可能下降 |
| 修改 Prompt | 延后 | 可针对个性化与训练价值补充约束 | 改变内容指令；Prompt-only 既有证据未实现 Token 目标；与 reasoning 变量同时改会破坏归因 |
| 确定性扩写 | 延后 | 可按规则补充结构 | 未必降低 Provider output tokens；新增重复、证据漂移和最终内容变换风险 |
| 放宽质量门槛 | **禁止** | 无 | 观察结果后改写预注册标准，会掩盖 0.6 均值下降及 13/15 pair loss |

## 为什么优先 reasoning_effort=low

Non-thinking 已证明可以大幅降低 output tokens 和延迟，但同时未通过正文质量门禁。保留 thinking、只降低 reasoning effort，是最直接的中间假设：测试能否保留一部分推理带来的内容质量，同时取得较温和的 Token 节省。这个判断是下一实验的工程假设，不是由 v3 相关性确定的因果结论。

新的离线实现至少需要证明两侧请求除 `reasoning_effort` 外完全一致、`thinking.type=enabled` 均被 Provider client 保留、`reasoning_effort` 未被 SDK 丢弃，并继续使用新的独立 readiness gate 与完整双臂重跑。所有现有正文、metadata、安全、可靠性和 Token 门禁保持不变。

机器记录见 `storage/reports/question-bank-token-phase-2-4d-d-b-offline-20261023/next-single-variable-recommendation.json`。

