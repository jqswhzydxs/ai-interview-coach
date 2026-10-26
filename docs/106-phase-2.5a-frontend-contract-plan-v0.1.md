# Phase 2.5A Plan v0.1

## 执行顺序

1. 读取 Phase 2.4D-F-B 后端冻结与前端入口记录，固定研究与生产边界。
2. 从当前 `app.main.app` 离线导出 OpenAPI，使用 UTF-8、稳定 key 排序和固定缩进生成快照。
3. 从 OpenAPI operation、路由 Pydantic 请求模型与服务序列化结构生成 API 矩阵。
4. 建立版本化 Mock harness；把 transport request/response 与 UI 预期分开。
5. 用现有 Pydantic 模型验证请求、统一 envelope、评价和题库，并加入语义断言。
6. 设计页面路由、导航、状态机、设计 Token、组件合同、安全边界和技术选型 ADR。
7. 执行专项、全量、迁移、diff-check、socket guard 与冻结哈希验证。
8. 输出机器可读 manifest，并停在技术栈等待确认状态。

## 变更原则

- 本阶段只新增合同、Mock、离线工具、测试与设计文档。
- 不修改后端路由、Schema、生产 Agent 或实验资产。
- 发现的合同缺口只进入 proposal，不通过 Mock 私自扩充后端 response body。
- Phase 2.5B 只能在技术栈被用户明确确认后启动。

