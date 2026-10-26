# Phase 2.5B Risk Analysis v0.1

| 风险 | 当前控制 | 剩余风险 |
|---|---|---|
| OpenAPI 成功响应类型较弱 | 生成类型作为请求事实源，响应经 Zod 适配；记录后端 proposal | 真实联调前仍需核对运行时 envelope |
| Mock 与真实服务偏差 | fixture/hash/语义/生成文件四重漂移检查 | Phase 2.5C 才能验证 CORS、代理和真实时序 |
| Mock 意外穿透网络 | browser/test `onUnhandledFrame=error` | 关闭 Mock 是显式操作，需在后续环境治理中限制 |
| degraded 被误读为 0 分 | Schema refinement 与组件/集成测试双重约束 | 后续新增评价 UI 必须复用该组件合同 |
| 敏感文本留在浏览器 | 仅内存状态、离开提醒、不记正文日志 | 浏览器崩溃恢复不会保留未提交内容，这是有意取舍 |
| 文件限制未由后端冻结 | 只设置格式提示，后端仍为最终校验者 | Phase 2.5C 前需确认后端 MIME/大小上限 |
| 长任务异步语义未冻结 | 页面只显示状态且不自动触发下一阶段 | polling cadence 与取消 API 仍待后端合同决策 |
| 视觉回归 | 四档响应式 CSS 和 axe 自动检查 | 尚无真实浏览器截图/端到端视觉基线 |
