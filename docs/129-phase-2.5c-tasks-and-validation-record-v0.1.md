# Phase 2.5C Tasks and Validation Record v0.1

## 实现任务

- [x] 精确 CORS allowlist 与 preflight 测试。
- [x] 10 MiB 默认上传限制、扩展名/MIME/解析白名单与残留清理。
- [x] 全链路 Zod schema 和 type-safe API client。
- [x] 文本/上传 → Resume/JD/Experience → parse → PrepPackage。
- [x] questions → practice → Evaluation → history/AgentRun。
- [x] POST 取消、禁止重复、terminal polling 与 Retry-After。
- [x] Playwright Chromium、real-api 与 deterministic visual 项目。
- [x] 四档截图、至少一张 real-api happy-path 截图及人工视觉检查。

## 验证记录

| 检查 | 状态 | 证据 |
|---|---|---|
| Phase 2.5A OpenAPI hash | passed | 当前重生成值仍为 `e983971aec77ddaf246efbb80637134f4fd41bfb9302fa2f3d06122430977304` |
| Phase 2.5B 与新增 Vitest | passed | 6 files，30 tests；原有覆盖未删减 |
| CORS / upload | passed | 13 tests；exact allowlist、拒绝未配置 origin、OPTIONS、大小/类型/残留清理 |
| Playwright real-api | passed | 3/3，经真实 FastAPI、SQLite 与 loopback HTTP |
| deterministic visual | passed | 12/12；375/768/1024/1440、7 个状态、reduced motion |
| axe / keyboard / focus / 44 px | passed | Chromium 中 serious/critical=0；键盘恢复与焦点断言通过 |
| frontend typecheck/lint/build | passed | TypeScript、ESLint、Vite production build 均通过 |
| backend full | passed | 510 passed，1 skipped；provider=mock、credentials=cleared、real socket attempts=0 |
| migrations | passed | upgrade/downgrade 3/3 |
| non-loopback sockets / Provider calls | passed | 均为 0；mock Provider，凭据清空 |
| frozen assets | passed | Phase 2.4 共 30 个文件与记录哈希一致；Prompt 与 production Agent 未变 |

全量验证证据已落盘，最终状态为 `phase_2_5c_local_api_integration_complete`。
