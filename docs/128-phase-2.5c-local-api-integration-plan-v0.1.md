# Phase 2.5C Plan v0.1

1. 记录冻结哈希，审计 FastAPI 路由、响应、同步执行、CORS、上传和本机浏览器能力。
2. 增加环境化 CORS allowlist、上传大小与文件安全裁决，并补单元/集成测试。
3. 扩展前端严格 Zod domain schema 与 API client，移除正常链路固定 ID。
4. 将创建流程接到 documents → profiles → parse → prep package，并用 session memory 传递真实 ID。
5. 接通 questions → practice → evaluation → detail/history/AgentRun；实现取消和受控 terminal polling。
6. 精确锁定 Playwright；建立 real-api 与 deterministic visual 两套配置。
7. 用隔离 FastAPI/Vite 子进程完成 Chromium E2E、四档截图、axe、键盘和焦点验证。
8. 重生成 OpenAPI做只读哈希比较，执行全部前后端、迁移、socket 和冻结资产回归。
9. 写入最终证据；任何破坏性合同变化触发停止，不覆盖 Phase 2.5A。
