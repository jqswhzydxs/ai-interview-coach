# Phase 2.4D-C Prompt v0.2 Pilot 分析报告

## 1. 证据范围

本报告只分析 ab1 的 3 个 paired Pilot。ab1 原报告仍为 `pilot_passed`、Full `not_started`；blind review 和 finalize 均未执行。readiness smoke 和 A/B 前的 candidate smoke 不计入下表。

所有 token 数值均来自 final successful response usage。Java candidate 的失败 timeout attempt usage 未知，因此其成功响应 token 可以进入 protocol v2 pair 比较，但实际 billing 总量只能视为已知下界。

## 2. 逐 pair 结果

| Case | Variant | Input | Output | Total | 可见字符总数 / 均值 | Latency | Calls / retry | Billing |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| Go | v0.1 | 859 | 3,114 | 3,973 | 3,414 / 136.56 | 40,767 ms | 1 / 0 | complete |
| Go | v0.2 | 1,037 | 3,358 | 4,395 | 2,241 / 89.64 | 41,601 ms | 1 / 0 | complete |
| Java | v0.1 | 839 | 3,337 | 4,176 | 3,809 / 152.36 | 38,220 ms | 1 / 0 | complete |
| Java | v0.2 | 1,017 | 3,331 | 4,348 | 1,030 / 41.20 | 106,529 ms | 2 / 1 | **incomplete**：attempt 1 unknown |
| Python | v0.1 | 871 | 2,820 | 3,691 | 3,205 / 128.20 | 34,179 ms | 1 / 0 | complete |
| Python | v0.2 | 1,049 | 3,508 | 4,557 | 1,070 / 42.80 | 40,772 ms | 1 / 0 | complete |

逐 pair 的 output token 变化为：Go +7.84%，Java -0.18%，Python +24.40%。可见字符变化分别为 -34.36%、-72.96%、-66.61%。只有 Java output tokens 略降 6，但其可见字符减少 2,779；三组都没有显示“可见字符压缩按比例转化为 output token 降低”。

## 3. 聚合结果

| 指标 | v0.1 baseline | v0.2 candidate | Candidate 变化 |
|---|---:|---:|---:|
| Input tokens | 2,569 | 3,103 | +20.79% |
| Output tokens | 9,271 | 10,197 | +9.99% |
| Total tokens | 11,840 | 13,300 | +12.33% |
| 平均 output tokens / run | 3,090.33 | 3,399.00 | +308.67 |
| 可见字符总数 | 10,428 | 4,341 | -58.37% |
| 平均可见字符 / 题 | 139.04 | 57.88 | -58.37% |
| Output tokens / 可见字符 | 0.8890 | 2.3490 | 2.642 倍 |
| Provider calls | 3 | 4 | +1 |
| Retry / timeout attempt | 0 / 0 | 1 / 1 | +1 / +1 |

candidate 的 3,399 平均 output tokens 比目标 1,800 高 1,599，即高 88.83%。candidate output tokens 相对 baseline 增加 9.988%，而可见字符减少 58.372%，两个变化方向相反，差 68.360 个百分点。按可见字符归一的 output-token 密度升至 baseline 的 2.642 倍。

这些数值证明 Prompt v0.2 的可见文本压缩没有带来 Provider 报告的 output token 降低。它们不能证明多出的 token 是 reasoning tokens，也不能定位 Provider 或 client 根因；当前历史响应没有保留可验证的 usage details。

## 4. 延迟、retry 与账单完整性

candidate P95 和 max 均为 106,529 ms，高于最终 90,000 ms 门槛，低于 120,000 ms variant deadline。该高延迟来自 Java candidate：第一次调用 ReadTimeout，第二次调用得到安全有效的 real output。

Java candidate 的成功 response usage 为 1,017 input、3,331 output、4,348 total；失败 attempt 三字段未知。报告没有把未知记为 0，也没有把失败 attempt 混入成功 response output token。candidate 已知 token 下界是 13,300 total，实际 billing 可能更高。

三个 pair 的双方 final output 都是 real、安全有效，且成功 response usage 完整，因此均符合 protocol v2 comparable 规则。账单完整性是独立维度，不改变这一准入结果。

## 5. Usage composition 审计

ab1 的 stored usage 和当前 `TokenUsage` 仅含 input/output/total 三字段。现有 client 从 response envelope 提取上述字段后不保留嵌套 details。由于原始响应按安全策略未保存，本次离线审计结果是：

| 字段 | ab1 状态 | 结论 |
|---|---|---|
| Reasoning tokens | unknown | 无法确认 Provider 是否提供，不能推算 |
| Visible completion tokens | unknown | 没有显式计数，不能用 output-reasoning 推算 |
| Cached input tokens/details | unknown | 没有保留细分字段 |

离线白名单解析器已经覆盖显式数值字段和缺失/非法值场景，但不回溯改写 ab1。

## 6. 评价边界

Pilot operational gate 已通过；这说明 3/3 candidate real 及内容检查满足 Pilot 运行准入。正式 Full 门禁要求至少 12 个 comparable pair，而当前只有 3 个；独立盲评也未执行。因此 token、延迟、质量和总 verdict 的正式最终门禁保持 `not_evaluable`。
