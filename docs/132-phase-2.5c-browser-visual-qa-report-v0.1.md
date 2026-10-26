# Phase 2.5C Browser and Visual QA Report v0.1

状态：`passed`。

## 执行环境

- Playwright：`1.61.1`，`package-lock.json` 精确锁定。
- 浏览器：本机 Chromium/Chrome `156.0.8078.47`，仅启动 Chromium 项目。
- 网络：所有页面请求由路由守卫限制为 `localhost`、`127.0.0.1` 或 `::1`；blocked/non-loopback attempts 为 0。
- real-api：`VITE_USE_MOCKS=false`，真实 FastAPI + 隔离 SQLite + 隔离上传目录；请求不含 `x-mock-scenario`。
- visual：现有 MSW 场景提供确定性数据；未匹配 API 请求失败。

## 自动化结果

合并执行 `npm run e2e` 共 15/15 通过：real-api 3 项，visual 12 项。四档 standard 页面分别在 375、768、1024、1440 px 验证；另覆盖 degraded/no-score、question-bank fallback、upstream fallback、memory-write blocked、loading、retryable error、404 和 reduced-motion。

每个关键页面执行横向溢出检查与 axe；serious/critical violations 为 0。所有可见 link/button/input/textarea 的边界至少 44×44 px。键盘测试覆盖空表单错误聚焦、字段修正、Enter 前进；取消/卸载由 AbortSignal 清理。reduced-motion 下 skeleton 的 `animation-name` 为 `none`。

## 人工视觉检查

人工查看了四档 standard 基线、degraded/no-score、fallback、memory blocked、loading、retryable error、404 以及真实 API happy-path 截图。检查结论：无横向滚动、导航或正文遮挡；移动端导航入口清晰；标准、降级、错误和无分数状态均同时使用图标、标题和文案传达语义；焦点/按钮层级、卡片间距和长页阅读顺序正常。真实 API 截图显示标准评价、可信来源、总分、维度分和建议，未出现 Mock 场景标识。

基线位于 `frontend/e2e/__screenshots__/visual/`，真实链路截图位于 `frontend/e2e/__screenshots__/real-api/real-api-happy-path.png`。像素比较用于回归检测，人工检查用于判断可读性与层级。
