# Phase 2.5A Mock Scenario Catalog v0.1

Mock Schema 版本为 `frontend-mock-v0.1`。所有数据均标记为 `synthetic_non_personal`；request/response 表示后端合同，`ui` 只表达客户端状态和恢复动作，不会混入 response body。

| Scenario | 分类 | 核心断言 |
|---|---|---|
| `standard-success` | standard | 准备包 ready；题库 25 题且严格 8/8/9、稳定顺序 |
| `upstream-fallback` | fallback | Agent run 为 fallback，结构化 upstream 原因可见 |
| `question-bank-fallback` | fallback | fallback 原因与 25 题结果并存；结果不得伪装成 standard source |
| `evaluator-degraded` | degraded | mode=degraded、score unavailable、总分 null、维度空 |
| `standard-evaluation` | standard | score available，数值总分与维度分均存在 |
| `memory-write-blocked` | memory safety | `write_decision=skip` 与结构化 skip reason |
| `agent-running` | processing | running、未完成时间与 usage 为 null，显示当前步骤 |
| `retryable-provider-error` | error | 502 `AGENT_FAILED`；UI 提供重试 |
| `nonretryable-contract-error` | error | 422 `VALIDATION_ERROR`；定位字段并返回修改 |
| `empty-history` | empty | `total=0, items=[]`；展示首次使用入口 |
| `file-upload-failure` | error | 422；文件类型/大小错误靠近输入区显示 |
| `request-cancelled-timeout` | client control | 无伪造响应；取消与超时保留输入并提供恢复动作 |

## 自动校验

- path/method 必须存在于冻结 OpenAPI。
- JSON 请求使用实际路由 Pydantic model 校验；故意无效的合同错误场景必须确实失败。
- 2xx 使用 `SuccessResponse`，非 2xx 使用 `ErrorResponse`。
- 完整评价使用 `AnswerEvaluation`，题库使用 `QuestionBank`。
- degraded 的 score/null/维度约束、fallback 的结构化原因、memory skip、8/8/9 和顺序都有独立断言。
- 扫描凭据、Authorization、原始响应、reasoning content、CoT、私钥和 Prompt v0.3 产品假设。

版本化 fixture 位于 `contracts/frontend/phase-2.5a-v0.1/mocks/`。合同漂移检测会比较 OpenAPI、矩阵和每个 fixture 的 SHA-256。

