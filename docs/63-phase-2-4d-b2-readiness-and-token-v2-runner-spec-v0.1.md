# Phase 2.4D-B2 Readiness 与 Token Protocol v2 Runner Spec

## 1. 范围

本阶段新增可执行但默认禁用的 Provider readiness CLI，以及独立的 Token protocol v2 A/B runner。实现和验证只使用离线 fake client；不访问真实 Provider，不建立 run4，不执行正式 readiness attempt。

旧 `run_question_draft_token_experiment.py`、`question_draft_token_experiment.py` 和 protocol v1 运行目录保持不变。Prompt v0.1/v0.2、metadata v2、Draft/最终 Schema、模型参数、fixtures、Provider client 和生产 `QuestionBankAgent` 均为冻结资产。

## 2. Readiness 执行协议

readiness 使用单独 JSON ledger，不位于 A/B 运行目录内。`prepare` 创建或验证 ledger，`attempt` 执行一次 readiness 调用，`status` 只输出受控状态摘要。

每个 readiness attempt：

- 固定使用 `backend_go_case`；
- 固定使用 Prompt v0.2、`QuestionDraftBank`、temperature=0.2、max_tokens=null；
- 直接调用注入的 `LLMClient.generate_json()` 一次；
- 不调用 `BaseAgent.execute()`，因此不存在 Agent retry 或 fallback；
- 受 120 秒外层 deadline 和冻结 Provider client 60 秒请求 timeout 约束；
- 成功响应依次通过 Draft Schema、metadata v2、最终 Schema、8/8/9、跨栈、重复及 evidence safety 检查；
- 只有 real、安全有效、成功 response usage 三字段完整且本次 billing usage 完整时通过。

最多允许 2 个 attempt。第一次失败后只能继续写同一个 ledger；第二次失败后状态为永久 `blocked`。`passed` 或 `blocked` 后重复执行 `attempt` 原样返回，不新增 Provider call，也不重写 ledger。

如果进程在已标记 `active_attempt` 后中断，后续自动调用会失败关闭，禁止在无法确认调用状态时自动补一次请求。

## 3. Readiness 授权

真实 `attempt` 同时要求：

- `RUN_REAL_LLM_ACCEPTANCE=true`；
- 显式 `--authorize-phase-2-4d-b-readiness`；
- `SAVE_FULL_LLM_LOGS=false`；
- Provider 为 deepseek 或 kimi；
- credential 已配置；
- `LLM_MODEL` 显式配置。

任一条件缺失时，CLI 在构造真实 client 或调用 Provider 前终止。`prepare` 和 `status` 不需要真实授权，也不会调用 Provider。

## 4. Ledger 合约

ledger 保存：Provider/model、协议版本、Prompt/Schema/Go fixture/metadata v2 的路径与 SHA-256、资产 bundle SHA-256，以及每次 attempt 的开始/结束状态。每个 attempt 保存：

- 单次 Provider call 的延迟和脱敏状态；
- filtered failure category、exception type、HTTP status、provider code、request-id、Retry-After；
- `successful_response_usage`；
- `billing_usage_completeness`；
- `known_token_lower_bound`；
- execution reliability；
- 内容检查结果和不可逆 output fingerprint。

ledger 不保存密钥、完整输入、问题正文、原始 response 或异常正文。readiness 输出不进入 A/B manifest 的 runs、token 指标、盲评包或生产数据；A/B 只引用 ledger SHA-256 和受控身份字段。

## 5. Protocol v2 A/B runner

新 runner 与 v1 完全分离，支持 `prepare/status/smoke/pilot/full/finalize`。构造顺序固定为：

1. 检查 readiness ledger 不在 A/B 目录中；
2. 验证 ledger 为 passed；
3. 验证 Provider/model、协议、冻结资产 bundle 和 passing attempt；
4. 计算 ledger SHA-256；
5. 才允许创建 A/B 运行目录。

manifest 保存 readiness ledger 路径、SHA-256、Provider/model 和资产 bundle SHA-256。运行恢复时 ledger 字节变化、Provider/model 不一致、Prompt/Schema/fixture/metadata hash 漂移均拒绝。

runner 固定：baseline Prompt v0.1、candidate Prompt v0.2、metadata v2、temperature=0.2、max_tokens=null、client timeout=60 秒、variant deadline=120 秒、Agent attempts=2、Provider call budget=62、3 cases × 5 pairs。奇数 pair 为 baseline→candidate，偶数 pair 反向。

## 6. 记账与比较

每次 execution 保存 protocol v2 的五类记录：successful response usage、billing completeness、known lower bound、全局 call budget 快照和 execution reliability。失败 attempt 不覆盖最终成功 response token，未知 usage 不写为 0。

只有两侧最终 output 均为 real、安全有效，且成功 response usage 三字段完整时 pair 才可比较。billing 不完整必须显著显示，但不会污染成功 response 的 output-token 值。fallback 永远不创建盲评 submission，也不进入 Token 或质量比较。

total-token 继续采用 `known_lower_bound_audit`；Provider call budget 是唯一硬预算。任何未来 `max_tokens` 修改都必须建立新协议并完整重跑。
