# Phase 2.4D-F-B Failure Attribution Report

## 分析边界

本报告在 Protocol v5 finalize 后使用冻结 private blinding map 解盲。它没有重新评审、生成问题或访问 Provider。所有分组、长度和相关性只作描述性归因，不能证明 Prompt 文本或模型内部机制导致了评分变化。

Evaluator 类型为 **AI**，identifier 为 `codex-independent-v5-review-20261024`。

## 五个正文维度

| 维度 | Baseline | Candidate | Candidate - Baseline | Candidate 门禁 |
|---|---:|---:|---:|---|
| Personalization | 4.2000 | 4.4667 | +0.2667 | 通过 |
| Technical correctness / stack boundary | 3.8667 | 3.9333 | +0.0667 | **失败** |
| Coverage / substantive diversity | 3.7333 | 3.8667 | +0.1333 | **失败** |
| Interview training value | 4.1333 | 4.5333 | +0.4000 | 通过 |
| Clarity | 4.0000 | 4.0000 | 0.0000 | 通过 |

整体正文质量从 3.9867 提升至 4.1600，但增量 0.1733 未达到预注册的 0.2。结果说明 v0.3 恢复了 personalization 和 training value，并未把 technical correctness 与 coverage/diversity 提升到绝对门槛。

## Go、Java、Python 分组

| 技术栈 | Baseline text | Candidate text | 差值 | Candidate technical | Candidate coverage | Candidate metadata | Candidate output tokens | Candidate 平均延迟 | Candidate 平均字符 | W/T/L |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Go | 3.9600 | 4.0800 | +0.1200 | 4.0 | 4.0 | 3.824 | 802.2 | 10.157s | 36.608 | 3/2/0 |
| Java | 3.9200 | 4.0400 | +0.1200 | **3.8** | **3.6** | 3.896 | 800.6 | 11.193s | 39.488 | 3/0/2 |
| Python | 4.0800 | 4.3600 | +0.2800 | 4.0 | 4.0 | 3.968 | 761.2 | 10.401s | 39.008 | 4/1/0 |

Java 是主要描述性缺口：它是唯一 Candidate technical correctness 与 coverage/diversity 都低于 4.0 的技术栈，也是全部两次 pair loss 的来源。该观察支持定位后续研究问题，但不能据此断言 Java 内容、问题长度或 Prompt 某一条规则构成确定因果。

## 15 个 pair

| Stack | Pair | Baseline | Candidate | 差值 | 结果 |
|---|---:|---:|---:|---:|---|
| Go | 1 | 4.0 | 4.2 | +0.2 | win |
| Go | 2 | 4.0 | 4.0 | 0.0 | tie |
| Go | 3 | 4.0 | 4.2 | +0.2 | win |
| Go | 4 | 4.0 | 4.0 | 0.0 | tie |
| Go | 5 | 3.8 | 4.0 | +0.2 | win |
| Java | 1 | 3.8 | 4.2 | +0.4 | win |
| Java | 2 | 3.8 | 4.0 | +0.2 | win |
| Java | 3 | 4.0 | 3.8 | -0.2 | loss |
| Java | 4 | 4.0 | 4.4 | +0.4 | win |
| Java | 5 | 4.0 | 3.8 | -0.2 | loss |
| Python | 1 | 4.0 | 4.4 | +0.4 | win |
| Python | 2 | 4.4 | 4.4 | 0.0 | tie |
| Python | 3 | 4.0 | 4.4 | +0.4 | win |
| Python | 4 | 4.0 | 4.2 | +0.2 | win |
| Python | 5 | 4.0 | 4.4 | +0.4 | win |

总计 10 win / 3 tie / 2 loss。

## Metadata、Token、延迟与长度

| 指标 | Baseline | Candidate | Candidate - Baseline |
|---|---:|---:|---:|
| Metadata fit mean | 3.8213 | 3.8960 | +0.0747 |
| 平均 output tokens | 688.4 | 788.0 | +99.6（+14.4683%） |
| P95/max latency | 18.828s / 18.828s | 12.409s / 12.409s | Candidate 更低 |
| 平均题目字符 | 30.4747 | 38.3680 | +7.8933 |

字符长度只是诊断项，不能替代 Provider output tokens 或质量分数。按模块：

| 模块 | Baseline 字符 | Candidate 字符 | Baseline metadata | Candidate metadata |
|---|---:|---:|---:|---:|
| self_intro | 27.9833 | 35.5500 | 3.1833 | 3.3500 |
| professional | 33.6083 | 44.3417 | 4.2417 | 4.4167 |
| behavior_project | 29.9037 | 35.5630 | 4.0148 | 3.9185 |

Candidate 题库平均字符与正文质量的 Pearson/Spearman 为 0.0090/0.0390；Candidate 单题字符与 metadata fit 为 0.2437/0.2650。样本量、评分离散度、技术栈和模块构成都会影响这些值，不能表述为长度导致质量变化。

## Baseline 两次 retry

Java pair 3 首次 Provider call 是 network failure，usage 全部 unknown；第二次成功 usage 为 input 938、output 664、total 1602。该 execution 的 billing usage incomplete，1602 只是已知下界。

Python pair 3 首次响应产生 other/schema failure，但 Provider usage 已知：input 970、output 735、total 1705；第二次成功 usage 为 input 970、output 713、total 1683。两个 attempts 都进入账单已知合计，下界为 input 1940、output 1448、total 3388。

预注册 Token 配对只使用双方最终成功响应的真实 usage，因此 Java pair 3 使用 664、Python pair 3 使用 713。失败 attempt 的 usage 只进入 billing completeness/known lower bound，不替换成功响应数值；15 个 comparable pairs 的结论保持不变。
