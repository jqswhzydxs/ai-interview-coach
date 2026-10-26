# Phase 2.5C Risk Analysis v0.1

| 风险 | 控制 | 停止条件 |
|---|---|---|
| 真实凭据或 Provider 被误用 | test env 强制 mock、清空凭据、socket allowlist、调用计数 | 任一非 loopback socket 或 Provider call |
| 污染开发数据 | 每次运行独立临时 SQLite/上传目录，不加载 `.env` | 路径逃逸或开发 DB 被访问 |
| POST 自动重放产生重复数据 | mutation retry=0、按钮锁、AbortSignal、E2E 计数 | 同一用户动作产生第二次 POST |
| 同步 POST 被误画为实时后台进度 | 不确定进度文案；仅响应后读取 AgentRun | UI 声称尚未返回的真实步骤 |
| Response envelope 漂移 | 重新生成 OpenAPI、严格 Zod、禁止 `z.unknown()` | 破坏性漂移或无法安全适配 |
| 上传伪装/超限/残留 | 扩展名+MIME+解析白名单、流式计数、异常清理 | 非法文件被保存或正文回显 |
| CORS 过宽 | exact origin、wildcard 拒绝、credentials false | 未配置 origin 获得允许头 |
| 视觉测试假阳性 | deterministic baseline + real screenshot + 人工检查 | 遮挡、横滚、不可见焦点或严重 axe 问题 |
| Playwright 获取触发外网 | 优先本机缓存/现有 Chromium，禁止测试阶段外网 | 无法离线取得 runner/browser 时记录阻塞 |
