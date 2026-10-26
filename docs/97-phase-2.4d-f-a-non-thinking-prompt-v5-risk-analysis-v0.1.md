# Phase 2.4D-F-A Protocol v5 Risk Analysis

| 风险 | 后果 | 协议控制 | 剩余限制 |
|---|---|---|---|
| Prompt 外字段漂移 | 不再是单变量实验 | exact request payload 归一化后逐字段指纹比较 | 只能证明客户端发送内容 |
| Provider 忽略 non-thinking | Token 行为偏离设计 | 实验 client 明确发送 `thinking.type=disabled`，MockTransport 捕获最终 body | 服务端语义只能由未来 readiness 验证 |
| 误发送 `reasoning_effort` | 引入第二变量 | client 不提供该参数；runner 拒绝 payload 中该字段 | Provider 可能有未公开默认行为 |
| v0.3 通过冗长文字换取质量 | Token 或延迟失败 | 绝对 output-token 与延迟门禁保持；长度只诊断 | Prompt 效果必须由真实实验决定 |
| 个性化导致虚构 | 安全与可信度回退 | Prompt 证据边界、assembler 与 evidence safety 门禁 | 盲评仍需检查细微事实偏移 |
| 覆盖提升造成重复 | 25 题训练价值下降 | 实质多样约束与重复检查 | 语义重复仍需独立评审判断 |
| v3/v4 样本混用 | 可比性失效 | 新协议、ledger、目录、锁、manifest；历史 samples reused=false | 人工搬运仍由哈希审计发现 |
| readiness 失败后重建 ledger | 绕过两次限制 | 单 ledger、blocked 终态、命令指南明确禁止 | 依赖执行者使用冻结路径 |
| timeout/retry 的失败 usage 未知 | 账单低估 | 成功 usage 与 billing completeness 分开；known lower bound | Provider 不返回时无法恢复总账单 |
| fallback 混入结论 | Token/质量失真 | 永久排除 Token 与盲评，单列可靠性 | fallback 仍消耗 call budget |
| max_tokens=null | 无法证明总 Token 上界 | 62-call 硬停止；known-token 下界审计 | 改 max_tokens 必须新协议完整重跑 |
| usage details 缺失 | 无法分解 Token 组成 | 只存白名单显式数字，缺失为 unknown | 禁止减法推算 visible/reasoning tokens |
| 盲评身份误标 | 审计结论失真 | evaluator 类型必填并原样保存 | 独立性仍需评审流程保证 |
| 放宽门槛迎合结果 | 错误晋升 v0.3 | 门禁冻结；任一必需失败即拒绝 | 新门槛只能属于新协议 |
| Pilot 后自动 Full | 未授权扩大调用 | 阶段独立命令和授权 flag | 仍需用户逐阶段授权 |

离线 fake client 结果只验证状态机与计算逻辑，不构成 Provider、Token 或质量结论。
