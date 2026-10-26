# Phase 2.4D-C 下一单变量实验建议

## 1. 选项比较

| 方案 | 25 题与 Schema 风险 | 成本 | 延迟 | 可比性 |
|---|---|---|---|---|
| 固定 `max_tokens` | 截断可能造成 JSON 无效或不足 25 题；安全上界尚未证明 | 提供硬上限，但截断重试会浪费调用 | 可能削短长尾，也可能因无效输出重试抵消 | 必须新协议完整重跑；不能与 ab1 混用 |
| 同模型关闭/限制 reasoning | 不引入输出 cap 时截断风险较低；仍需 25 题及质量门禁 | 若 Provider 真正支持，可直接降低不可见生成成本 | 预期改善，但必须实测 | 最能隔离 token 组成变量；新协议两侧从零重跑 |
| 更换明确非 reasoning 模型 | 新模型对 Schema、25 题、证据安全均需重新资格验证 | 可能更可预测 | 引入新的可靠性分布 | 模型能力是较大混杂因素；必须新协议完整重跑 |
| 同模型使用其他可控生成参数 | 风险依具体参数而定 | 通常没有 token 硬上限 | 影响未知 | 仅在恰好一个参数变化时具有清晰因果解释 |

## 2. 推荐

推荐下一阶段优先设计“同一模型显式关闭 reasoning”的单变量协议：两侧都固定 Prompt v0.2、metadata v2、Schema、fixtures、temperature、timeout、deadline、retry/fallback 和安全检查；control 使用模型默认 reasoning，treatment 只增加一个明确的 reasoning-disabled 参数。

该推荐有严格的 go/no-go 前置条件：必须先用离线 capability 证据证明当前 Provider/model 官方支持准确参数，并能在脱敏运行记录中确认参数已应用。当前仓库没有这项支持证据，ab1 也没有保留 reasoning usage details，所以本阶段不创建协议、不发送请求、不假定参数名称或效果。若前置条件不能满足，应停止该方案并另行评审“明确非 reasoning 模型”，不能在同一协议内临时替换变量。

选择这一方向的原因是：v0.2 已把可见字符压缩 58.372%，但 output tokens 增加 9.988%。在没有 usage details 的情况下，先隔离不可见生成控制，比直接设置可能截断 25 题 JSON 的 `max_tokens` 更能回答 token 组成问题。

## 3. 新协议要求

- max_tokens、reasoning 参数、模型或其他生成参数的任何变化都创建新协议；
- control 和 treatment 必须在新协议中从零完整重跑；
- ab1 数据只能作为历史背景，不能作为新协议 control，也不能合并计算门禁；
- readiness、Provider call budget、billing completeness、known lower bound、real/safe/comparable 规则重新预注册；
- quality、Schema、8/8/9、跨栈、重复、证据安全和延迟门禁不得放宽；
- 新真实数据产生前冻结参数名、值、能力证据、usage details 捕获字段和停止规则。
