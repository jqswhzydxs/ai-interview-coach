# Phase 2.4D-F-B Frontend Entry Recommendation

## 建议

建议下一阶段开始前端 Mock 和 API 契约开发。该建议本身不启动前端实现；需等待 Phase 2.5 前端契约冻结与 Mock 脚手架设计授权。

前端与模型研究解耦：

- Mock 必须基于当前生产 API 合约，而不是 Prompt v0.3 已晋升的假设。
- 生产默认 `QuestionBankAgent` 保持不变。
- 模型研究结果未来只能通过兼容的后端接口进入，前端不绑定 Prompt 版本或 thinking 参数。
- 不因前端开发而重新开启连续 Prompt 微调或真实 Provider 实验。

## 默认展示要求

前端应默认展示或明确表达：

1. `source_quality`；
2. `score_available`；
3. `evaluation_mode`；
4. 降级原因，由后端结构化 `fallback_reason` 映射为用户可读信息。

当 `score_available=false` 或 `evaluation_mode=degraded` 时，界面不得展示伪造的 0 分或精确分数；应展示无分数状态、来源质量和降级原因。Mock 至少覆盖 standard、upstream fallback、evaluator fallback 和 memory-write blocked 等合同场景。

## 后续模型研究边界

不创建 Prompt v0.4，不继续为通过既有门禁而反复重跑。若未来继续模型研究，必须以独立的新模型/人工评审项目重新立项，并与 Phase 2.5 前端工作分开排期、数据和验收。

推荐状态：`allow_phase_2_5_frontend_mock_and_api_contract_development`；生产 Agent 切换仍为禁止。
