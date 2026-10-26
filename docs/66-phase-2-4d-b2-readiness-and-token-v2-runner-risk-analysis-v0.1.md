# Phase 2.4D-B2 Readiness 与 Token Protocol v2 Runner Risk Analysis

| 风险 | 影响 | 控制 |
|---|---|---|
| readiness 复用 BaseAgent | 单 attempt 内发生 retry/fallback | 只调用 `_build_request`，直接调用 client 一次，从结构上绕开 `execute()` |
| authorization 缺失仍调用 Provider | 意外产生真实流量 | env、显式 flag、日志、Provider、credential、model 全部在调用前验证 |
| 首次失败后创建新 ledger | 绕过 2-attempt 上限 | Provider/model/assets 绑定到单一 ledger；terminal 状态幂等 |
| 中断后无法判断请求是否已发送 | 重复计费 | `active_attempt` 存在时失败关闭，不自动补发 |
| readiness 输出污染 A/B | Token 和质量统计偏差 | ledger scope 独立；A/B manifest 只保存 hash 和身份摘要 |
| passed ledger 被替换 | 在不同 Provider 或资产下运行 A/B | A/B 创建前校验内容，创建后固定整个 ledger SHA-256 |
| readiness 未通过仍生成目录 | 留下可误用的 prepared run | 构造函数在 `_load_or_initialize` 之前验证 ledger |
| 失败 response usage 污染成功 token | paired reduction 错误 | Agent trace 决定 attempt 成败；成功 response usage 独立保存 |
| HTTP 成功但 Schema/assembler 失败 | 被误算为安全 real | 内容检查独立，pair/盲评要求全部 passed |
| fallback 进入盲评 | 质量比较失真 | submission 只为 `_safe_real_run_v2` 创建 |
| usage unknown 被当作 0 | 低估成本 | lower bound 无观测值时为 null；billing 显著标 incomplete |
| call budget 在 retry 中越界 | 超出 62 calls | variant 前保守预留 2 calls，client 在每个 call 前再次硬检查 |
| 更改 max_tokens | 唯一变量被破坏 | v2 固定 null；修改必须新协议完整重跑 |
| v2 复用 v1 私有分析函数 | v1 文件未来漂移影响复现 | v1 helper 文件进入 v2 common asset hash，运行中漂移立即拒绝 |

本阶段的 fake client 测试只能证明状态机、记账和隔离行为，不能证明真实 Provider 稳定性。真实 readiness 仍需后续明确授权。
