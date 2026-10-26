# Phase 2.5C Local Integration Runbook v0.1

## 隔离环境

不得修改 `.env`。启动器必须在子进程中设置：

```text
APP_ENV=test
LLM_PROVIDER=mock
RUN_REAL_LLM_ACCEPTANCE=false
SAVE_FULL_LLM_LOGS=false
DEEPSEEK_API_KEY=
KIMI_API_KEY=
DATABASE_URL=sqlite+pysqlite:///<temporary>/phase_2_5c.db
UPLOAD_DIR=<temporary>/uploads
CORS_ALLOWED_ORIGINS=http://127.0.0.1:<vite-port>
VITE_USE_MOCKS=false
VITE_API_BASE_URL=http://127.0.0.1:<api-port>/api/v1
```

## 命令

在仓库根目录执行后端专项检查：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\integration\test_documents_api.py tests\integration\test_phase_2_5c_cors.py -q
.\.venv\Scripts\python.exe -m pytest tests\integration\test_migrations.py -q
.\.venv\Scripts\python.exe -X pycache_prefix=.tmp-phase25c-compile -m compileall -q app scripts tests
```

在 `frontend` 目录执行前端和浏览器验证：

```powershell
npm run typecheck
npm run lint
npm run test
npm run build
npm run contract:check
npm run mock:check
npm run e2e:real
npm run e2e:visual
# 或一次执行两套 Chromium 项目
npm run e2e
```

`scripts/run-phase-2-5c-playwright.mjs` 负责创建临时 SQLite 与上传目录、选择 loopback 端口、强制安全环境、等待 health、启动真实模式和 Mock 模式 Vite、执行测试并终止子进程。real-api 项目不启用 MSW；visual 项目只使用版本化 Mock。禁止手工加载仓库 `.env`。

## 失败恢复

- 启动失败：保存脱敏进程退出码和阶段，不保存环境变量值或正文。
- E2E 失败：保留 Playwright trace/screenshot；其中只能包含合成测试文本。
- 合同漂移：停止，保存新旧 SHA-256 和兼容性分类，不覆盖冻结快照。
- 浏览器缺失：记录本机依赖阻塞，不使用外网下载安装规避网络边界。
