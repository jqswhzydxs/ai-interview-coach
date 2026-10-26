# Phase 2.4D-E-B Pilot Futility Analysis

分析日期：2026-10-24（Asia/Singapore）。本报告只读取冻结的 protocol v4 Pilot report 与脱敏 audit。未调用 Provider，未运行 Full，未生成盲评，未执行 finalize，也未修改 readiness ledger、ab1 manifest、report 或 audit。

## 1. 门禁解释

v4 原始状态保持 `pilot_passed`，Full 保持 `not_started`。Pilot 的执行门禁已经通过：candidate 在 Go、Java、Python 各有一次 real safe 输出，6 个最终输出的 Schema、assembler、8/8/9、技术栈、重复和 evidence 检查全部通过。

正式 Full 门禁仍为 `not_evaluable`。当前只有 3 个 comparable pairs，低于预注册的 12 个；报告中的正式 candidate 平均 Token、paired reduction、质量和最终 verdict 都没有可评价结果。以下 Token 数值只能作 Pilot 描述性工程判断，不能表述为完成 Full 或正式统计拒绝。

## 2. 逐 Pair 结果

| 技术栈 | Arm | Input | Output | Total | Reasoning | Visible completion | 延迟 | Retry | Billing | 平均题长 | 超上限 |
|---|---|---:|---:|---:|---:|---|---:|---:|---|---:|---:|
| Go | high baseline | 1037 | 2940 | 3977 | 2167 | unknown | 24.325s | 0 | complete | 36.64 | 0 |
| Go | low candidate | 958 | 2171 | 3129 | 1457 | unknown | 23.977s | 1 | incomplete | 90.88 | 9 |
| Java | high baseline | 1017 | 1872 | 2889 | 1224 | unknown | 17.117s | 0 | complete | 35.28 | 0 |
| Java | low candidate | 938 | 7365 | 8303 | 6674 | unknown | 52.719s | 0 | complete | 89.64 | 7 |
| Python | high baseline | 1049 | 11399 | 12448 | 10497 | unknown | 77.447s | 0 | complete | 49.92 | 0 |
| Python | low candidate | 970 | 4714 | 5684 | 3894 | unknown | 39.416s | 0 | complete | 114.16 | 22 |

Go candidate 的第一次 Provider attempt 为 network/`ConnectError`，usage 三字段全部未知；第二次 attempt 成功。因此成功响应的 output tokens=2171 可进入 pair 比较，但该 execution 的 billing usage 为 incomplete，总账单只能表达为已知下界。

三个 pair 的描述性 output-token reduction 分别约为 Go 26.16%、Java -293.43%、Python 58.65%。技术栈之间方向和幅度不一致，尤其 Java candidate 出现 7365 output tokens；这支持“波动较大”的工程判断，但样本量不足以推出技术栈因果结论。

## 3. Token 与绝对门槛

Baseline high 的 3 次 output tokens 总计 16211；candidate low 总计 14250、平均 4750。聚合描述性 paired reduction 为 12.0967%，但正式字段保持 `not_evaluable`。

15 次 candidate 若要达到平均≤1800，总 output tokens 必须≤27000。Pilot 已使用 14250，剩余 12 次只有 12750 的额度，即平均必须≤1062.5；当前 Pilot 最小单次为 2171。未来样本低于 1062.5 在数学上并非不可能，但相对当前三个观测形成明显的工程性无效轨迹，继续 Full 的信息价值不足以抵消调用成本。

## 4. Reasoning 与可见题目长度

Baseline/candidate reasoning tokens 分别总计 13888/12025。Candidate 三次为 1457、6674、3894，范围 5217，population standard deviation 约 2131.37。`reasoning_effort=low` 没有在 Pilot 中形成稳定而接近绝对门槛的 reasoning 消耗。

Candidate 75 道题平均 98.2267 字符，38 道超过各模块建议上限；baseline 平均 40.6133 字符，candidate 描述性增加约 141.86%。这说明 low arm 的可见题目更长，同时总 Token 仍远高于绝对门槛。字符长度只作诊断，不能替代真实 Provider Token，也不能替代盲评质量。

Provider 未返回 visible completion tokens。分析保留 `unknown/null`，没有用 `output_tokens - reasoning_tokens` 推算，也没有把缺失值填为 0。

## 5. 可靠性边界

Candidate P95/max 均为 52.719 秒，Pilot 内满足延迟阈值。所有最终输出均为 real safe，内容检查失败数为 0。Go 的失败 attempt 使账单总量只能作为下界；它不改变成功响应 Token 可比较性，但必须继续单列于 execution reliability 与 billing completeness。

来源 report SHA-256：`4a34c4914c7e97cd1015f989763a6d8946f4ed58a395f828fe055a51e4294896`。来源 audit SHA-256：`1635c3d17065924cdbde58a8c2952baf80b31c8b6e4e2b1859927eaba12d3c46`。
