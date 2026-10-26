# Phase 2.5B Frontend Architecture v0.1

## 分层

```text
BrowserRouter + AppShell
  -> resource pages / route state
  -> TanStack Query / React Hook Form
  -> typed API client + Zod response adapter
  -> MSW browser worker (default enabled)
  -> frozen Phase 2.5A fixtures
```

`src/api/generated/openapi.ts` 从冻结快照生成。请求体直接引用生成类型；后端成功响应在 OpenAPI 中较弱，因此 `src/api/domain.ts` 只承担运行时收窄和跨字段不变量，不复制后端请求模型。

## 路由

- `/`
- `/prep/new`
- `/prep/:prepPackageId/processing`
- `/prep/:prepPackageId/questions`
- `/questions/:questionId/practice`
- `/evaluations/:evaluationId`
- `/history`
- `/agent-runs/:agentRunId`
- `*` 404

路由表达资源和状态，页面刷新可从 URL 复现当前 Mock 状态。processing 只读取状态，不自动触发后续业务请求。

## 状态所有权

- 服务端状态：TanStack Query，查询仅对安全 retryable 错误执行一次受控重试，mutation 不自动重试。
- 表单状态：React Hook Form + Zod，保存在组件内存。
- 场景状态：dev/test 查询参数，经 Mock header 选择；生产模式不发送。
- 导航状态：React Router；移动抽屉支持 Escape 并恢复触发器焦点。
