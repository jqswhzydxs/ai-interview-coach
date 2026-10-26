# Phase 2.4D-B Provider 稳定性与 Token 记账协议 v2 Risk Analysis

| 风险 | 影响 | 控制 |
|---|---|---|
| 失败 attempt usage 覆盖最终成功 response usage | 有效 output-token 被误判或污染 | 两套字段独立；成功值只来自最终成功 response |
| 把 unknown 当 0 | 低估费用并错误通过预算 | 无已知值时 lower bound 保存 `null`；billing 单独标记 incomplete |
| billing 不完整却报告精确总费用 | 财务结论失真 | 报告显示大写 warning；total-token 只做 lower-bound audit |
| fallback 内容进入 Prompt 评价 | 对 v0.2 质量和长度产生假证据 | real/safe/usage 三重准入；fallback 必须排除 |
| readiness 输出混入 A/B | 破坏 paired token 统计 | readiness 使用独立 scope、ledger 和调用计数 |
| 失败后连续创建目录重试 | 规避预注册次数上限 | readiness 只允许一个持久 ledger；两次失败转 blocked |
| 多层 retry 放大调用 | 超出调用预算 | `BaseAgent` 仍为唯一 retry owner；每次 call 前消费硬预算 |
| 添加 `max_tokens` 改变唯一变量 | 旧新结果不可比 | v2 固定为 null；任何修改建立新协议并完整重跑 |
| 把 network 分类当作根因 | 错误修复代理/TLS/Provider | 审计明确 `insufficient_evidence`，只记录可观察类别 |
| 默认 client 每次新建连接影响稳定性 | 连接复用缺失可能增加变异 | 记录为后续独立工程假设；本阶段冻结 client，不做因果声明 |
| 代理/TLS/HTTP2 来源未固化 | 环境差异难复现 | 新真实实验前 readiness 记录有效配置来源的脱敏快照；本阶段不读取或输出密钥 |
| 修改历史运行或冻结资产 | 审计链失效 | 实施前/后 110 文件逐一 SHA-256 比较，专项测试固定关键旧文件 hash |

当前最大限制是缺少 Provider 侧和底层 transport 证据。run1 的 ReadTimeout 与 run3 的 RemoteProtocolError 能证明失败类型和时间顺序，不能证明服务端、网络、代理、TLS 或连接复用中的具体根因。
