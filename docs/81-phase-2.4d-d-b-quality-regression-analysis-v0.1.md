# Phase 2.4D-D-B Quality Regression Analysis v0.1

## 分析范围

本报告在 Protocol v3 finalize 后使用 private blinding map 解盲，只分析冻结的 30 份题库、completed AI review 与脱敏运行统计。没有再次评分、生成题目或访问 Provider。

五个正文维度均为题库级评分；它们不能可靠拆分到单题或模块。模块分析因此使用每题可见字符数与 metadata-fit 分数。以下相关性均为描述性统计，不代表确定因果。

## 五个 text dimensions

| 维度 | Baseline 均值 | Candidate 均值 | Candidate - Baseline |
|---|---:|---:|---:|
| personalization | 4.0667 | 3.2000 | -0.8667 |
| technical correctness and stack boundary | 4.2000 | 3.8000 | -0.4000 |
| coverage and substantive diversity | 4.4667 | 3.9333 | -0.5333 |
| interview training value | 4.6000 | 3.8000 | -0.8000 |
| clarity | 4.5333 | 4.1333 | -0.4000 |

总体正文质量从 4.3733 降至 3.7733，差值为 -0.6000。所有五个维度都下降，其中 personalization 和 interview training value 的下降最大。

## 按技术栈

| 技术栈 | Baseline text | Candidate text | 差值 | Baseline metadata | Candidate metadata | W/T/L |
|---|---:|---:|---:|---:|---:|---:|
| Go | 4.3600 | 3.7200 | -0.6400 | 4.0720 | 3.7040 | 1/0/4 |
| Java | 4.4800 | 3.9200 | -0.5600 | 4.0400 | 3.8160 | 0/0/5 |
| Python | 4.2800 | 3.6800 | -0.6000 | 4.3120 | 3.9280 | 0/1/4 |

三个技术栈的 Candidate 正文均值都低于 Baseline。整体 15 pair 为 1 win、1 tie、13 loss：

| Stack | Pair | Baseline | Candidate | 差值 | 结果 | Baseline 平均字符 | Candidate 平均字符 |
|---|---:|---:|---:|---:|---|---:|---:|
| Go | 1 | 4.0 | 4.4 | +0.4 | win | 37.24 | 29.52 |
| Go | 2 | 5.0 | 3.8 | -1.2 | loss | 41.84 | 29.84 |
| Go | 3 | 4.6 | 4.0 | -0.6 | loss | 51.60 | 30.36 |
| Go | 4 | 3.8 | 3.2 | -0.6 | loss | 87.40 | 24.44 |
| Go | 5 | 4.4 | 3.2 | -1.2 | loss | 37.88 | 22.32 |
| Java | 1 | 4.8 | 3.8 | -1.0 | loss | 41.64 | 25.28 |
| Java | 2 | 4.8 | 3.8 | -1.0 | loss | 40.40 | 25.84 |
| Java | 3 | 4.0 | 3.8 | -0.2 | loss | 36.56 | 29.80 |
| Java | 4 | 4.8 | 4.4 | -0.4 | loss | 32.64 | 34.48 |
| Java | 5 | 4.0 | 3.8 | -0.2 | loss | 33.92 | 37.04 |
| Python | 1 | 4.0 | 3.2 | -0.8 | loss | 41.12 | 28.24 |
| Python | 2 | 4.4 | 3.8 | -0.6 | loss | 38.04 | 25.92 |
| Python | 3 | 3.8 | 3.8 | 0.0 | tie | 86.92 | 31.64 |
| Python | 4 | 4.6 | 3.8 | -0.8 | loss | 43.80 | 34.48 |
| Python | 5 | 4.6 | 3.8 | -0.8 | loss | 40.36 | 35.28 |

## 长度、模块与 metadata fit

整体平均题目字符数从 46.0907 降至 29.6320。按模块：

| 模块 | Baseline 平均字符 | Candidate 平均字符 | 差值 | Baseline metadata | Candidate metadata | Candidate 低于建议下限 |
|---|---:|---:|---:|---:|---:|---:|
| self_intro | 37.6000 | 27.2917 | -10.3083 | 3.2917 | 3.0583 | 90/120 |
| professional | 51.9000 | 33.8750 | -18.0250 | 4.8750 | 4.7000 | 108/120 |
| behavior_project | 48.4741 | 27.9407 | -20.5333 | 4.2444 | 3.7037 | 125/135 |

Candidate 的整体 metadata fit 仍以 3.8160 通过门禁，但分布从 Baseline 的 `{1:1, 2:14, 3:96, 4:84, 5:180}` 移到 `{1:0, 2:24, 3:156, 4:60, 5:135}`。P50/P95 均保持 4/5；均值下降 0.3253。模块均值都下降，behavior/project 的降幅最大（-0.5407）。模块均值不是额外的预注册门禁。

## 长度与评分相关性

| 层级 / 子集 | n | Pearson r | Spearman rho |
|---|---:|---:|---:|
| 题库平均字符 vs 正文质量，全部 | 30 | 0.1799 | 0.5859 |
| 题库平均字符 vs 正文质量，Baseline | 15 | -0.4848 | -0.0764 |
| 题库平均字符 vs 正文质量，Candidate | 15 | 0.5116 | 0.4979 |
| 单题字符 vs metadata fit，全部 | 750 | 0.3580 | 0.4225 |
| 单题字符 vs metadata fit，Baseline | 375 | 0.3300 | 0.4027 |
| 单题字符 vs metadata fit，Candidate | 375 | 0.3814 | 0.4134 |

按模块的单题字符数与 metadata fit 相关性：

| 模块 | Baseline Pearson / Spearman | Candidate Pearson / Spearman |
|---|---:|---:|
| self_intro | -0.0790 / -0.0879 | 0.1725 / 0.2067 |
| professional | 0.0887 / 0.1173 | 0.1018 / 0.0884 |
| behavior_project | 0.3650 / 0.4000 | 0.4259 / 0.4133 |

这些系数受 variant、技术栈、模块构成、评分离散度和较小的题库级样本影响。尤其是“全部题库”的相关性混合了 enabled/disabled 两组，不能据此声称缩短题目导致质量下降，也不能声称延长题目一定提升质量。

## Baseline timeout/retry

Baseline Go pair 3 有 1 次 timeout 和 1 次 retry，共 2 次 Provider call。第二次成功响应 usage 完整：1037 input、3785 output、4822 total；失败 attempt usage 未知。因此：

- 该 pair 的最终成功响应 Token 可比较；
- billing completeness 为 incomplete；
- billing 总量只能记录为已知下界 4822 total tokens；
- 未知 attempt 不填 0，也不污染成功响应 output-token 数值；
- Protocol v3 的成功响应 Token 比较结论不受影响。

完整机器数据见 `storage/reports/question-bank-token-phase-2-4d-d-b-offline-20261023/quality-regression-analysis.json`。

