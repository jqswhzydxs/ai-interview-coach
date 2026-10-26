# AI Interview Coach 项目当前进度报告 v0.1

更新日期：2026-10-15

## 1. 项目定位

这是一个面向后端开发岗位求职者的 AI 面试准备后端服务。最终业务目标是把用户的简历、目标岗位 JD 和准备目标，转化为可练习、可追踪的面试训练闭环：

```text
输入简历 + JD + 准备目标
-> 解析个人与岗位画像
-> 生成针对性面试题库
-> 用户练习并提交单题回答
-> 获得结构化评分与改进建议
-> 记录长期薄弱点，支持后续持续练习
```

当前项目是 FastAPI 后端，尚未实现正式 Web 前端。

## 2. 最终业务能力与当前状态

| 业务环节 | 最终需要实现的能力 | 当前状态 |
| --- | --- | --- |
| 材料输入 | 保存简历、JD、面经；支持文本、Markdown、DOCX、PDF | 已实现 |
| 画像解析 | 将简历、JD、面经转为结构化 Profile | 已实现，支持 mock/真实 LLM 分支 |
| 岗位匹配 | 分析候选人的匹配优势、缺口、风险与准备重点 | 已实现，支持 mock/真实 LLM 分支 |
| 题库生成 | 生成不少于 25 道题，覆盖自我介绍、后端能力、项目与行为题 | 已实现，支持 mock/真实 LLM 分支 |
| 题库查询 | 查询备战包、按模块与难度筛选题目 | 已实现 |
| 单题评价 | 对题库题或自定义题回答进行结构化评分 | 已实现，支持 mock/真实 LLM 分支 |
| 记忆策略 | 高置信度薄弱点入库，低置信度仅留在本次评价 | 已实现；MemoryAgent 具备真实 LLM 分支 |
| Agent 可观测性 | 保存 Agent run、步骤、状态、错误和摘要 | 已实现 |
| 真实模型接入 | DeepSeek/Kimi 可选，输出校验、重试、降级 | 已实现首轮代码接入，尚未使用真实 key 做人工质量验收 |
| 前端产品 | 用户上传、练习、查看报告的页面 | 未实现 |
| 高级能力 | 联网搜索、语音面试、PDF 报告、真实面试复盘、质量后台 | 未实现，当前明确属于非目标 |

## 3. 当前已实现的用户流程

1. 用户通过 `POST /api/v1/documents/text` 或 `POST /api/v1/documents/upload` 提交简历、JD 或面经。
2. 用户创建简历与岗位记录。
3. 系统分别解析简历和 JD，形成：
   - `ResumeProfile`
   - `JDProfile`
   - 可选的 `ExperienceProfile`
4. 用户提交准备目标，例如“准备后端开发实习一面”。
5. 系统生成备战包：
   - 匹配报告 `MatchReport`
   - 至少 25 道面试题
   - 三类题目每类至少 8 道
   - 3 道推荐优先练习题
6. 用户从题库选择题目，或直接输入自定义题目与回答。
7. 系统输出：
   - 100 分制总分
   - 六个评分维度
   - 优点、改进点与风险
   - 改进版回答
   - 至少一个追问
   - 下一题建议
   - 记忆更新建议
8. 系统将高置信度的长期问题保存为记忆，并记录 Agent 执行日志。

## 4. 技术与架构

技术栈：

1. Python 3.11
2. FastAPI
3. SQLAlchemy 2.x
4. Alembic
5. Pydantic v2
6. PostgreSQL 设计，测试中使用 SQLite
7. `uv` 管理依赖
8. OpenAI-compatible `LLMClient` 抽象
9. DeepSeek / Kimi provider
10. mock/rule-based Agent 作为默认稳定路径

主要分层：

```text
app/api/v1/routes   API 路由
app/services        业务编排和持久化
app/agents          Agent、Provider、Prompt、重试与降级
app/schemas         Pydantic 输入输出契约
app/db/models       ORM 数据模型
app/tools           文件解析、hash、脱敏
tests               单元、集成、端到端、provider smoke 测试
```

## 5. 开发过程与阶段

### 5.1 Phase 1：项目基础与数据层

建立项目结构、配置、日志、request_id、统一错误响应、数据库连接、迁移、默认用户与全部 MVP 数据表。

### 5.2 Phase 1：Schema 与输入处理

设计并实现简历、JD、面经、题库、评分、记忆、Agent 日志等结构化 Schema；加入文件解析、5MB 限制、hash 和手机号/邮箱脱敏。

### 5.3 Phase 1：mock Agent 闭环

用稳定的规则/mock Agent 实现解析、匹配、题库生成、评分和记忆更新，先保证业务闭环和测试可重复运行。

### 5.4 Phase 1：API 与持久化

打通材料、简历、JD、面经、备战包、题库、评价、记忆和 Agent run 查询接口，并写入数据库。

### 5.5 Phase 1：验收与发布基线

完成单元、集成和端到端测试，并形成 `docs/20-mvp-phase-1-release-note-v0.1.md`。

### 5.6 Phase 2：真实 LLM 接入

引入统一真实调用流程：Prompt 加载、JSON 输出约束、Pydantic 校验、最多重试一次、失败回退 rule-based 输出。已覆盖 Resume、JD、面经、匹配、题库、回答评价和记忆 Agent。

### 5.7 Phase 2：真实上下文补齐

真实模型调用时，匹配 Agent 可得到简历/JD/面经画像；题库 Agent 可得到匹配报告与画像；评价 Agent 可得到题目、评分锚点和相关 Profile。

## 6. 当前质量状态

完整测试结果：

```text
128 passed
1 skipped
1 warning
```

说明：

1. 跳过项是默认关闭的真实 provider smoke test。
2. warning 是 Starlette `TestClient` 与 httpx 的弃用提示，不影响当前功能。
3. mock 默认路径持续可用，因此不配置 API key 时，项目仍能稳定运行和测试。

## 7. 真实 LLM 的当前行为

默认配置：

```env
LLM_PROVIDER=mock
```

因此默认不会调用外部模型。切换为 `deepseek` 或 `kimi` 并提供 API key 后，Agent 会尝试真实生成；如果模型超时、返回非 JSON、字段缺失、题库数量不够、评分不符合规则等，系统会重试一次，再自动回退到既有规则输出，保证主业务流程不中断。

Phase 2 文档：

1. `docs/21-phase-2-real-llm-agent-spec-v0.1.md`
2. `docs/22-phase-2-real-llm-agent-plan-v0.1.md`
3. `docs/23-phase-2-real-llm-agent-tasks-v0.1.md`

## 8. 下一阶段建议

当前最值得进行的是“真实模型验收”，而不是继续堆功能：

1. 配置 DeepSeek 或 Kimi API key。
2. 显式运行 provider smoke test。
3. 使用脱敏的真实简历和 JD 做人工验收。
4. 观察题目个性化程度、评分合理性、Schema 失败率、降级次数和调用成本。
5. 根据真实输出调整 Prompt、模型参数和质量门槛。
6. 真实能力稳定后，再开发前端练习界面与面试报告展示。
