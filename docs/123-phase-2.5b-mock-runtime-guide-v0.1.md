# Phase 2.5B Mock Runtime Guide v0.1

开发和测试默认启用 Mock。浏览器入口在渲染 React 前启动 `mockServiceWorker.js`，测试入口使用 Node MSW server。二者共享同一组 handlers 与冻结 JSON fixtures。

## 场景选择

页面用 `?scenario=<id>` 选择状态，API client 仅在 Mock 模式把它转换为 `x-mock-scenario`。场景 ID 来自 Phase 2.5A catalog，包括 standard、degraded、fallback、memory blocked、processing、retryable/nonretryable、upload failure、empty 和 cancelled/timeout。

## 约束

- 未匹配请求以 error 终止，不回落到网络。
- `request-cancelled-timeout` 使用无限延迟，必须由 AbortSignal 终止。
- fixture 不复制到前端源码，直接从冻结目录导入。
- `npm run contract:check` 校验 OpenAPI、生成类型和全部 fixture；`npm run mock:check` 校验 12 场景语义。
