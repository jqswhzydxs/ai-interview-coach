# Phase 2.4D-B 阻塞事件记录

本文件是 2026-10-22 新增的只读审计记录。它引用旧资产的 SHA-256，不覆盖旧报告，不改变 protocol v1 的结论，也不把三次 smoke 解释成正式 Token A/B。

## run1：timeout 后真实成功

- 原状态：`smoke_failed`；原 stop reason：`smoke_usage_unknown`。
- attempt 1：`ReadTimeout` / `read_timeout`，约 60.792 秒，usage 全部未知。
- attempt 2：真实成功，约 30.733 秒；成功 response usage 为 input 1037、output 2528、total 3565。
- execution：real，2 calls，1 retry，总延迟 91.839 秒；Schema、metadata v2、8/8/9、跨栈和重复检查通过。
- protocol v2：`successful_response_usage=complete`，`billing_usage_completeness=incomplete`，known total lower bound=3565。
- 阻塞：只有 candidate smoke，没有 paired baseline；无法用于 Prompt token/质量门禁。未知的失败 attempt 费用不得记为 0，也不得覆盖 output_tokens=2528。

关键旧文件 SHA-256：manifest `7e3f616658219297e7f97a34da3f4cb6ddb0747ec962f0f43391cd1635849062`；report `787bd9eacc7da70b0b1ffdaf5c5113a8c8b89b60aa87024efccd3e75efbbe4c7`；execution audit `c5a52b596a0e5ecbdbdda317acc412911c3bcf1c20cf57aa51fa42540be70f71`。

## run2：manifest model label 配置错误

- 原状态：`prepared_offline`。
- manifest model label：`phase-2.4d-b-unconfigured`。
- Provider calls：0；没有 smoke execution 或真实输出。
- protocol v2：successful usage、billing usage 和 token lower bound 均为 `not_applicable`/`null`。
- 阻塞：属于准备阶段配置错误，不属于真实实验结果，不能进入成功率、token 或质量统计。

关键旧文件 SHA-256：manifest `57ef4f5112242c17e02b4d32c7bfe4b78556403f0d6e6bc70cd15ceb632587c4`；report `9fcdf09969911f2b6014764904a830f2a6665cb32dc231907da03ddb6cf5acf0`；execution audit `5c78dbf59230b0a2b0fba03e88570e61f58ffb750234e27d379f3e3719f6b0ee`。

## run3：两次 network failure 后 fallback

- 原状态：`smoke_failed`；原 stop reason：`smoke_usage_unknown`。
- attempt 1：`RemoteProtocolError` / `network`，约 6.743 秒，usage 全部未知。
- attempt 2：`RemoteProtocolError` / `network`，约 2.205 秒，usage 全部未知。
- execution：fallback，2 calls，1 retry，总延迟 9.004 秒。
- protocol v2：没有 successful response；billing incomplete；三个 known lower-bound 字段均为 `null`，没有用 0 代替未知。
- 阻塞：fallback 内容、字符长度及任何派生结果全部排除，不评价 Prompt v0.2。

关键旧文件 SHA-256：manifest `9c99e3dedb3473a2faafb5385b61399a43d1fe41b6cbaca499cf33d03a50b2c4`；report `7a2a73265a01424cc0e6b12c5aa04c8677e29927a9f3614fbdf93e1daf9d101a`；execution audit `b6f6d8c3aad721b80782a4f93d2feabb89034900c50d49438200f1c68c1b0be7`。

## 共同结论

三次运行均不能用于 Prompt v0.2 正式门禁。run1 提供了一个成功 response 的真实 output-token 观测和一次 billing 不完整事件；run2 没有真实调用；run3 只提供可靠性失败证据。现有证据不足以定位 Provider 根因。

完整的机器记录位于 `storage/reports/question-bank-token-phase-2-4d-b-protocol-v2-review-20261022/blocking-events.json`。
