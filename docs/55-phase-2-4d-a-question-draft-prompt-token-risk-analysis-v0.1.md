# Phase 2.4D-A QuestionDraft Prompt Token Risk Analysis

日期：2026-10-21。

| 风险 | 控制与证据 | 剩余限制 |
| --- | --- | --- |
| 把 2.4B 的 2067.4615 当作新 baseline | 协议声明只用新运行中同 case/pair 的 v0.1；报告固定 `immutable_historical_result_not_rewritten` | 真实 Token 结果只能在 2.4D-B 获得 |
| 除 Prompt 外发生漂移 | 同一 Agent 类/共享 client；common asset、input、双 Prompt hash；每 pair 比较去除 Prompt 后的完整 request 指纹 | Provider 服务端非确定性仍存在，需配对和交替顺序控制 |
| v0.1/v0.2 或 metadata 串用 | prompt_variant 必填且白名单；exact metadata v2 类型、版本与实例绑定；每 run 记录两者 | 有权限任意篡改进程内对象的调用者不在实验威胁模型内 |
| Prompt hash 在实验中变化 | manifest 建立哈希，每阶段、每 Agent 构造及运行前后复核；变化立即拒绝 | D-B 必须使用新空目录建立当时 manifest |
| 短文本删除必要技术约束 | v0.2 明确禁止；原跨栈、重复、证据和 assembler 检查保留；独立正文与 metadata 盲评门禁 | 规则检查不能证明任意自然语言问题的完整性 |
| 字符长度冒充 Token 改善 | 长度指标标为 diagnostic-only；Token 门禁只读取完整 Provider usage | Provider Tokenizer 或计费口径变化仍需记录 model/provider |
| 缺失 usage 被当作 0 | 任一 attempt 不完整则 run 聚合为 unknown/null，另存已知下界；完成 pair 后停止预算不可证明的实验 | unknown 会降低样本并可能使门禁不可评价，这是有意的 fail-closed 行为 |
| 少量 pair 得出节省结论 | 至少 12 个双方 real、安全且 usage 完整 pair；不足时绝对/相对门禁均 not_evaluable | 15 pair 仍是有限样本，跨模型结论不可外推 |
| deadline 破坏配对 | 取消仅传播至当前 variant；仍运行 pair mate，再决定停止 | 超时 variant 无法进入 comparable pair |
| fallback 混入 real Token/质量 | execution_mode、失败、assembler applied 单独记录；Token comparable 只收双方 real、安全输出 | fallback 保持用户安全，但不计优化成功 |
| 盲评身份泄露 | 随机 submission ID 与随机盲序；packet 去除 variant/case/pair/Prompt/指纹；private map 隔离 | 文风可能让 evaluator 猜测版本，无法完全消除 |
| AI evaluator 被误称人工 | finalizer 强制记录真实 type/identifier/independence；报告原样展示 | AI 评分局限仍需在最终决策中保留 |
| 调用或 Token 预算失控 | 62 次硬调用上限、250k 已知 Token 上限；每 attempt 原子审计；unknown 后停止 | 失败响应无 usage 时只能知道调用数，不能知道真实 Token |
| 历史资产或生产被改写 | 独立 run dir、路径重叠拒绝、开工/终检哈希、生产路由回归；无默认开关 | 工作树已有大量用户未提交内容，必须继续逐文件保护 |
| 真实执行被 D-A 误启动 | CLI 要求未来专用 flag 与 real acceptance 环境双门禁；D-A 仅执行 prepare | 有权限直接调用 Python service 的操作者仍须遵守授权边界 |
| degraded evaluation/长期记忆回退 | 不改相关代码并运行完整离线回归 | 离线 fake Provider 不代表真实故障分布 |

本阶段不声称 Token 门禁通过。离线 runner 中 fake usage 只验证计算和控制流，不能作为任何产品或模型效率结果。
