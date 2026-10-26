# Phase 2.4D-C Prompt v0.2 Pilot Futility 与 Token 组成审计 Spec

## 1. 范围

本阶段只读取 protocol v2 的冻结 Pilot `question-bank-token-phase-2-4d-b2-v2-20261022-ab1` 及其 readiness ledger，生成新的离线分析和提前停止记录。不得执行 Full、blind review 或 finalize，不访问 Provider，不创建 Prompt v0.3，不修改 ab1、readiness ledger、Prompt、Schema、metadata v2、fixtures、模型参数或生产 Agent。

ab1 原始状态保持 `pilot_passed`，其含义仅为 Pilot operational gate 通过。Phase 2.4D-C 在独立目录记录 `stopped_for_engineering_futility`；该决定不覆盖 ab1，也不把未执行的预注册 Full 表述为已完成。

## 2. 分析输入和边界

逐 pair 分析只使用 `audit/executions.json` 中 6 条 paired run，不把 candidate smoke 或 readiness 输出混入 A/B。每条记录读取以下脱敏字段：

- final successful response 的 input/output/total tokens；
- 25 道题的字符计数及聚合长度；
- execution latency、Provider call 数、retry、timeout、fallback；
- billing usage completeness 和 unknown attempt 序号；
- real、安全有效及 protocol v2 comparable 状态。

Java candidate 的第二次 attempt 是成功响应，三字段 usage 完整，因此该 pair 按 protocol v2 可比较。第一次 timeout attempt 的 usage 未知，所以整次 execution 的 billing usage 保持 incomplete，known token 只能作为下界。

## 3. 提前停止语义

提前停止记录必须同时满足：

- `decision_status=stopped_for_engineering_futility`；
- `formal_final_gate_status=not_evaluable`；
- `formal_statistical_rejection=false`；
- `prompt_v0_2_promoted=false`；
- Full、blind review、finalize 均为未执行；
- 原报告和运行目录保持字节不变。

工程停止依据是方向性 futility：3 个 Pilot pair 中 candidate 的 successful-response output tokens 合计高于 baseline，同时 candidate P95 已高于最终 90 秒门槛。由于只有 3 个 comparable pair，少于预注册的 12 个，且质量盲评未执行，正式最终门禁仍不可评价。

## 4. Usage details 安全合约

新增纯离线白名单解析器，仅接受已经解码的 SDK/response mapping，只返回以下显式非负整数：

- reasoning tokens；
- visible completion tokens；
- cached input tokens；
- cache read input tokens；
- cache creation input tokens。

解析器不保存 source object、原始响应、正文、异常消息、请求或凭据。不接受 bool、负数、浮点数和字符串，不把缺失字段填为 0，也不使用 `output_tokens - reasoning_tokens` 推算 visible completion tokens。

当前 ab1 只保留 `input_tokens/output_tokens/total_tokens`，现有 `TokenUsage` 捕获模型也只有这三个字段。由于原始响应没有保存，无法区分“Provider 未提供”与“client 未保留”，因此 ab1 的 reasoning、visible completion 及 cached/input details 全部记录为 `unknown`，Provider 支持结论也为 `unknown`。

## 5. 新实验边界

任何 max_tokens、reasoning 参数、模型或其他生成参数变化都必须建立新协议。新协议的两侧必须从零重跑，当前 Prompt-only Pilot 只能作为背景证据，不能与新数据合并或作为新协议的一侧。

本阶段推荐的下一单变量是：模型、Prompt v0.2 和其他冻结项不变，仅比较默认 reasoning 与一个显式、可证明受当前 Provider/model 支持的 reasoning-disabled 参数。若离线能力证据无法证明支持及请求生效方式，不得创建或执行该协议。

## 6. 输出

机器可读产物位于 `storage/reports/question-bank-token-phase-2-4d-c-offline-20261022`：

- `pilot-futility-analysis.json`；
- `usage-details-audit.json`；
- `early-stop-decision.json`；
- `next-experiment-options.json`；
- `protected-assets-before.json`；
- `offline-validation-report.json`。

输出目录与 ab1/readiness 路径重叠时分析器必须安全终止。
