# Phase 2.5B Mock-first Frontend Spec v0.1

## 状态与边界

- 目标状态：`mock_scaffold_complete`。
- 技术栈：React、TypeScript、Vite、npm，FastAPI 独立部署。
- 本阶段只运行版本化 Mock；真实 FastAPI 与真实 Provider 调用均为 0。
- Phase 2.5A OpenAPI、Mock fixtures 与外部语义为事实源，后端合同不因前端实现而改变。
- production `QuestionBankAgent`、Prompt、模型配置和冻结实验资产保持不变。

## 必需行为

1. 开发与测试默认 `VITE_USE_MOCKS=true`，关闭 Mock 必须显式配置。
2. OpenAPI 类型只能由冻结快照生成；运行时以 Zod 适配弱响应声明。
3. `score_available=false` 必须对应 `total_score=null` 且无维度分，并显示“本次无法提供可信分数”。
4. degraded、fallback、memory-write blocked 均显示来源、原因和恢复动作，不展示原始异常。
5. 输入数据只驻留内存；前端不持久化完整简历、JD、面经或回答。
6. 路由可深链接，移动导航、tabs、上传和表单可由键盘完成。
7. MSW 未匹配请求直接失败，禁止 Mock 穿透网络。

## 验收

类型、lint、测试、构建、合同漂移、Mock 合同、后端离线回归、迁移、socket guard、diff-check 与冻结资产哈希必须全部通过。
