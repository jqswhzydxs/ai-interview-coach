# AI Interview Coach Frontend

React + TypeScript + Vite 前端。开发与单元测试默认由 MSW 读取 Phase 2.5A 冻结合同；Phase 2.5C 另提供只连接本机隔离 FastAPI 的浏览器测试。两种模式都禁止连接真实 Provider。

## 环境

- Node.js `>=20.19`
- npm（依赖版本由 `package-lock.json` 固定）
- 环境变量复制自 `.env.example`

```dotenv
VITE_API_BASE_URL=/api/v1
VITE_USE_MOCKS=true
```

只有显式设置 `VITE_USE_MOCKS=false` 才会关闭浏览器 Mock。该模式只能按 Phase 2.5C runbook 连接 loopback FastAPI；浏览器端不得配置 API key。

## 常用命令

```bash
npm ci
npm run contract:generate
npm run contract:check
npm run mock:check
npm run typecheck
npm run lint
npm run test
npm run build
npm run e2e:real
npm run e2e:visual:update
npm run e2e:visual
npm run e2e
npm run dev
```

`contract:generate` 从 `../contracts/frontend/phase-2.5a-v0.1/openapi.json` 经 stdin 生成 `src/api/generated/openapi.ts`。`contract:check` 同时验证冻结 OpenAPI SHA-256、生成文件漂移、12 个 fixture 哈希和 Mock 语义。

## 运行方式

1. 执行 `npm ci`，不要手工修改生成类型。
2. 保持 `VITE_USE_MOCKS=true`。
3. 执行 `npm run dev`。
4. 使用 `?scenario=<scenario-id>` 查看页面状态，例如：
   - `/evaluations/00000000-0000-4000-8000-000000000601?scenario=evaluator-degraded`
   - `/evaluations/00000000-0000-4000-8000-000000000601?scenario=memory-write-blocked`
   - `/prep/00000000-0000-4000-8000-000000000401/questions?scenario=question-bank-fallback`

场景选择头只在 Mock 模式发送。未匹配请求在浏览器和测试中都按错误处理，不允许穿透网络。

## Phase 2.5C 本机联调

`npm run e2e` 通过 `scripts/run-phase-2-5c-playwright.mjs` 自动创建临时 SQLite 和上传目录，清空 Provider 凭据，启动 loopback FastAPI、real Vite 与 mock Vite，并在结束时清理临时数据。脚本固定 `APP_ENV=test`、`LLM_PROVIDER=mock`、`RUN_REAL_LLM_ACCEPTANCE=false` 和 `SAVE_FULL_LLM_LOGS=false`。

- `e2e:real`：关闭 MSW，通过真实 HTTP 完成文档、画像、准备包、8/8/9 题库、评价、历史与 AgentRun。
- `e2e:visual:update`：在受控 mock 场景中生成 Chromium 截图基线。
- `e2e:visual`：校验四档视口及 standard、degraded/no-score、fallback、memory blocked、loading、error、404。
- 所有浏览器测试阻断非 loopback 请求；真实 API 请求不得带 `x-mock-scenario`。

完整环境、安全边界和故障恢复见 `../docs/131-phase-2.5c-local-integration-runbook-v0.1.md`。

## 目录

- `src/api/`：OpenAPI 生成类型、运行时 Zod 适配、ApiError、QueryClient。
- `src/mocks/`：冻结 fixture 注册、MSW browser worker 与 test server。
- `src/components/`：Phase 2.5A 组件合同实现。
- `src/pages/`、`src/routes/`：资源型路由与页面状态。
- `src/styles/`：semantic CSS variables、响应式和 reduced-motion。
- `src/test/`：合同、Mock、流程、错误、安全语义和 axe 验证。

## 数据与日志边界

- 简历、JD、面经和回答仅保存在页面内存，不写入 localStorage。
- 未提交敏感内容会触发离开提示。
- 前端不显示 Prompt、CoT、原始 Provider 响应、异常正文或堆栈。
- ApiError 只保留安全错误码、HTTP 状态、脱敏 request ID、retryable 与白名单 failure category。
- `score_available=false` 时不渲染任何精确分数。
