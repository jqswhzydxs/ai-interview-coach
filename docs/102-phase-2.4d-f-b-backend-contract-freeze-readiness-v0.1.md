# Phase 2.4D-F-B Backend Contract Freeze Readiness

## 结论

后端 API 与 degraded/fallback 合约已具备进入 Phase 2.5 契约冻结设计的条件。该结论不依赖 Prompt v0.3 晋升，也不授权切换生产 Agent。

建议冻结的对外语义：

| 合约字段/语义 | 后端来源 | 前端处理 |
|---|---|---|
| `source_quality` | evaluation/source context | 默认展示来源质量 |
| `score_available` | evaluation response | 为 false 时不得展示精确分数 |
| `evaluation_mode` | `standard` / `degraded` | 默认展示当前评价模式 |
| `fallback_reason` | Agent run detail | 作为结构化降级原因展示 |
| nullable score contract | degraded evaluation | 使用无分数状态，不伪造 0 分 |
| memory safety | degraded evaluation write guard | 降级结果不得污染长期记忆 |

现有后端实现和测试已经覆盖 standard/degraded 分支、fallback reason、source quality 传播、无分数语义、API 序列化、数据库迁移与长期记忆写入阻断。本阶段不修改这些实现，只记录可冻结范围。

## 冻结边界

- Phase 2.5 可以冻结 API Schema、degraded/fallback 语义和 Mock 数据合同。
- QuestionBank 最终 API Schema 和生产默认 Agent 保持现状。
- Prompt v0.3 的状态是 `research_candidate_not_promoted`，不得写入默认配置或 Mock 的产品假设。
- 真实生产 Agent 切换继续禁止。
- 任何模型研究变化必须通过独立项目和后续 API 兼容审查，不阻塞前端契约开发。

状态：`ready_for_phase_2_5_contract_freeze`，等待 Phase 2.5 明确授权。
