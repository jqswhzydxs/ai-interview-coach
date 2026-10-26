# Phase 2.4D-B Provider 稳定性与 Token 记账协议 v2 离线验证报告

验证日期：2026-10-22（Asia/Singapore）。本次只执行离线代码、fake attempt 和已有证据解析，没有访问真实 Provider，没有创建 run4，没有修改 Prompt v0.2，也没有切换生产 Agent。

## 1. 实现结果

新增独立 `phase-2.4d-question-draft-prompt-token-v2` 模块。旧 `question_draft_token_experiment.py` 及其 `phase-2.4d-question-draft-prompt-token-v1` 常量保持字节不变。v2 实现并测试了：

- 成功 response usage 与全 attempts billing 完整性分离；
- 未知 usage 保存为 `null`；
- 已知 token 下界只累加观测值；
- Provider call budget 在调用前硬停止；
- timeout、network、retry、deadline、fallback 分开统计；
- pair 必须双方 real、安全有效且成功 response usage 完整；
- readiness 独立账本、最多 2 次、每次 1 call、失败后阻止正式 A/B 目录。

## 2. 三次事件复核

| 运行 | 新事件分类 | successful response usage | billing | 评价资格 |
|---|---|---|---|---|
| run1 | timeout 后真实成功 | 1037 / 2528 / 3565，complete | incomplete，attempt 1 未知 | 排除；只有 candidate smoke，无 pair |
| run2 | manifest model label 配置错误 | not applicable | not applicable，0 calls | 排除；不是真实实验 |
| run3 | 两次 network failure 后 fallback | not applicable | incomplete，2 attempts 未知 | 排除；fallback 不参与评价 |

run3 的 known input/output/total lower bound 均为 `null`，没有将未知记录为 0。run1 的失败 attempt 未污染成功 response 的 output_tokens=2528。三次运行均未产生 Prompt v0.2 Token 或质量门禁结论。

## 3. Provider client 审计

请求层 timeout=60 秒，variant deadline=120 秒；唯一 retry owner 是 `BaseAgent.run_with_fallback`，最多 2 attempts。`RemoteProtocolError` 仅归类为 network。默认 client 在每个 `generate_json` 中新建并关闭连接池；注入 client 时生命周期由调用方负责。

当前代码没有固定 proxy、TLS CA/verify、HTTP2 或 keep-alive；当前离线环境的 httpx 0.28.1 默认值只用于描述本地审计环境，不能反推失败进程或 Provider 根因。缺少 Provider trace、失败进程的脱敏 transport 配置和 request id，因此根因状态为 `insufficient_evidence`。

## 4. 预算与 max_tokens 决策

protocol v2 在产生新真实数据前冻结为 `known_lower_bound_audit`：无法证明 total-token 时不声称硬 total-token gate，不使用臆测上界；Provider call budget 仍为硬门禁。当前 payload 没有 `max_tokens`，本阶段保持不变。若未来设置 `max_tokens`，必须建立新协议并完整重跑 readiness、smoke、pilot、full。

## 5. 验证结果

| 检查 | 结果 |
|---|---|
| 专项 protocol v2 测试 | 13 passed，0 failed，real socket attempts=0 |
| 全量离线测试 | 353 passed，1 skipped，1 既有弃用 warning，real socket attempts=0 |
| 迁移测试 | 3 passed，real socket attempts=0 |
| compileall | passed |
| `git diff --check` | passed；只有工作区既有 LF/CRLF 提示，无 whitespace error |
| 新文件 whitespace 检查 | 10 files passed |
| 保护资产 SHA-256 | 110/110 passed，missing=0，changed=0 |

全量测试日志 SHA-256：`eac32a0963c18e155fdf020b0da1e86ac207d5a7bab9e449be823ccf8ebf02d2`。保护基线文件 SHA-256：`2a317c30f7b5249072f9df09bcbadba1f10e51d36f48a798dbf455db615a3940`。

## 6. 冻结与停止点

Prompt v0.1/v0.2、metadata v2、Draft/最终 Schema、fixtures、模型和生成参数、Provider client、retry/fallback、生产 `QuestionBankAgent`、Phase 2.4B/2.4C/2.4D-A 资产及 run1/run2/run3 全部通过最终哈希检查。本阶段停止在离线协议修复；新真实 readiness 和 A/B 尚未授权，也未执行。
