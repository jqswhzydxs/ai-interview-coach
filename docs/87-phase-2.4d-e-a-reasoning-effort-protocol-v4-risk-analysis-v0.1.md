# Phase 2.4D-E-A Protocol v4 Risk Analysis

| 风险 | 后果 | 协议控制 | 剩余限制 |
|---|---|---|---|
| `reasoning_effort` 被 SDK 丢弃或覆盖 | 实际实验没有形成单变量 | 实验 client 直接构造 HTTP JSON；MockTransport 验证最终 body | 真实 Provider 是否执行该语义只能由未来 readiness 证明 |
| baseline 依赖 Provider 默认 effort | baseline 条件随 Provider 默认漂移 | high 与 low 均必须显式发送 | Provider 后端语义仍可能在服务端变化 |
| thinking 或其他请求字段串用 | 引入第二变量 | 两侧 thinking 均显式 enabled；pair 保存归一化请求指纹 | 指纹证明发送内容一致，不能证明服务端内部完全一致 |
| v3 样本混入 v4 | 破坏随机化与可比性 | 新协议、目录、ledger、锁和 manifest；声明 v3 samples reused=false | 人工复制文件仍需冻结哈希审计发现 |
| readiness 失败后反复新建 ledger | 绕过两次尝试上限 | 单 ledger 规则、blocked 终态、A/B 前置校验 | 需要执行者遵循预注册路径和命令指南 |
| timeout/retry 导致账单 usage 不完整 | 成本被低估 | 成功 usage 与 billing completeness 分离；known lower bound 单列 | Provider 不返回失败 usage 时无法恢复真实账单总量 |
| fallback 被当作 candidate 输出 | Token 或质量指标失真 | fallback 标记并排除 Token 比较、submission 和盲评包 | fallback 仍计入可靠性失败 |
| max_tokens=null 无法给出可证明总 Token 上界 | 无硬 total-token budget | 62-call 硬停止；已知 Token 只作 lower-bound audit | 若未来引入 max_tokens，必须建立新协议并完整重跑 |
| 120 秒 deadline 与底层请求取消不完全一致 | 超时后仍有连接清理延迟 | runner 使用单 execution 绝对 deadline并分类记录 | Provider/传输层取消语义仍需真实 readiness 观察 |
| reasoning details 不存在 | 无法解释 Token 构成 | 只存白名单显式数字；缺失保持 unknown | 禁止通过 total-output 等字段反推 |
| 报告泄露 CoT 或敏感输入 | 隐私与安全风险 | response model 排除 raw/reasoning content；audit/report 不保存完整输入或响应 | 盲评包仍含完成评审所需的最小 evidence context |
| low-effort 降低正文质量 | Token 达标但不可用 | 保持质量≥4.0、下降≤0.2、metadata fit≥3.5 等全部门禁 | 真实结论须完成 15 pairs 与独立盲评 |
| Pilot 通过后误跑 Full | 未经授权扩大真实调用 | 每阶段独立命令和授权 flag；无自动串联 | 仍需用户逐阶段明确授权 |
| 放宽门禁迎合结果 | 错误晋升 candidate | 门禁冻结于代码、manifest 和机器预注册；任一失败即拒绝 | 任何新门槛只能属于新协议 |

当前离线证据只能证明执行器合同、请求形状和计算逻辑，不能证明 DeepSeek 服务端稳定性、Token 改善或质量结果。不得把 fake client 结果表述为真实实验数据。
