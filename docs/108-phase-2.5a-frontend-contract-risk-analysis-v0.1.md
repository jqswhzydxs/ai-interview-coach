# Phase 2.5A Risk Analysis v0.1

| 风险 | 影响 | 当前控制 | 后续动作 |
|---|---|---|---|
| OpenAPI 成功响应为通用 object | 类型生成无法覆盖真实 response data | Mock 同时校验运行时 envelope、服务结构和 Pydantic | 兼容版本中补 response model |
| 运行时错误 envelope 未完整进入 OpenAPI | 生成客户端可能误解 404/502 | API 矩阵与 Mock 明确状态；错误体受 `ErrorResponse` 校验 | 后端补 OpenAPI response 声明 |
| 创建接口实际等待 Agent 完成 | 长请求、取消与重复提交处理复杂 | 状态机包含 processing、timeout、cancelled 和幂等 UI 锁 | 冻结轮询/job 策略后再实现 |
| memory guard 结果缺少独立字段 | UI 无法区分 Agent 主动 skip 与安全 guard 阻断 | 仅展示合同中可观察的 `write_decision=skip`；不推测 | 需要时提议结构化 outcome |
| 上传限制未在当前合同完全冻结 | 客户端限制可能与服务端漂移 | 只显示后端错误；前端预校验等待后端数值 | Phase 2.5B 前冻结限制 |
| 降级结果被显示成 0 分 | 误导用户且违反安全语义 | Schema、Mock、组件合同和测试均强制 null/no-score | 保留回归测试 |
| fallback 被包装成标准结果 | 用户无法判断来源质量 | 默认展示 Badge 与 DegradationNotice | 不允许仅靠颜色区分 |
| Mock 夹带真实个人数据 | 隐私泄漏 | 固定合成 UUID、合成文案、敏感标记扫描 | CI 保留扫描 |
| 技术栈过早锁定 | 产生无授权脚手架与依赖债务 | ADR 仅推荐，manifest 标记等待确认 | 用户确认后进入 Phase 2.5B |
| 前端绑定 Prompt v0.3 | 把失败研究候选误当生产能力 | manifest 固定 `research_candidate_not_promoted` | 前端不暴露 Prompt 版本选择 |

剩余最高风险是 OpenAPI response typing 不完整。它不阻止本阶段形成 Mock 合同，但在自动生成正式客户端前应通过兼容审查解决。

