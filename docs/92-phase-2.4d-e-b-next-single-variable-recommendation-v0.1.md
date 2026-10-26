# Phase 2.4D-E-B Next Single-Variable Recommendation

## 1. 方案比较

| 方案 | 收益 | 主要风险 | 结论 |
|---|---|---|---|
| 继续 v4 Full | 可让已注册 v4 门禁正式可评价 | 剩余 12 次 candidate 需平均≤1062.5，低于 Pilot 最小 2171；在盲评前继续消耗真实调用 | 因工程性无效停止 |
| 固定 `max_tokens` | 可建立单请求 output 上界 | 可能截断 JSON 或 25 题完整性；必须建立新协议并完整重跑 | 暂缓 |
| non-thinking + 新 Prompt | 固定低 Token/低延迟模式，只检验 Prompt 能否恢复质量 | 质量恢复尚未证实，仍需完整 paired run 与独立盲评 | **优先** |
| 确定性扩写 | 可在精简输出后补充受控细节 | 改变生成架构，可能产生模板化、重复或证据漂移，已不是 Prompt 单变量 | 暂缓 |
| 更换模型 | 可能获得新的 Token/质量前沿 | Provider 行为和可比性变化更大，需新 readiness 与完整数据 | 暂缓 |

任何方案都不得通过放宽正文质量≥4.0、相对下降≤0.2 或 metadata fit≥3.5 等门槛取得通过。

## 2. 推荐的新方向

下一协议优先采用严格 Prompt 单变量：

| 项目 | Baseline | Candidate |
|---|---|---|
| Thinking | `{"type":"disabled"}` | `{"type":"disabled"}` |
| Prompt | v0.2 | v0.3 |
| Prompt v0.3 目标 | — | personalization、coverage、training value |

两侧模型、Schema、metadata v2、fixtures、Provider 参数、重试、fallback、deadline、计数和安全检查必须完全相同。两侧必须重新完整运行；不得复用 v3 或 v4 样本。

选择这一方向的依据是：v3 的 non-thinking candidate 显示了显著 Token/延迟优势，但正文质量失败；下一实验可以把 non-thinking 固定为共同条件，只测试 Prompt 是否能恢复个性化、覆盖度与训练价值。该推断仍需新协议和独立盲评验证，不能把 v3 的 Token 或 v4 的质量/可靠性数据拼接成新结论。

## 3. 本阶段边界

本阶段没有创建 Prompt v0.3、runner、readiness ledger 或实验目录，也没有访问 Provider。这里只冻结策略选择，等待下一协议离线设计授权。
