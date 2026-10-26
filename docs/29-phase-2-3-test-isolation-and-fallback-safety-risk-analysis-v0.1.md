# Phase 2.3：测试环境隔离与降级链路安全化风险分析 v0.1

## 1. 重复重试风险

风险：为实现策略降级，在 service 或 Harness 中再次运行 Agent，形成隐藏的 2×2 调用。

控制：不新增任何 service/Harness 重试。策略门禁由 Agent 在 provider 调用前短路；provider 失败仍只走 `BaseAgent.run_with_fallback()` 的现有最多 2 次调用。测试断言策略 fallback 的 `real_call_count=0`、`retry_count=0`。

## 2. 责任混乱风险

风险：Agent、service 和数据库各自推导不同的来源质量，导致评价与记忆决策不一致。

控制：execution mode 到 source quality 的映射使用同一纯函数；Agent 负责输出语义，service 负责从持久化 AgentRun 组装上下文，MemoryService 作为最终写入防线。模型输出不能覆盖系统推导的门禁结果。

## 3. API 兼容风险

风险：`total_score` 在 degraded 路径从数字变为 null，旧客户端可能直接格式化或比较数值。

控制：请求不变；新增 `score_available` 和 `evaluation_mode`；standard 路径仍返回数字。该变化只发生在原本会给出误导性分数的降级路径。文档明确客户端迁移顺序：先判断 `score_available`，再读取分数。

## 4. Schema 被放宽风险

风险：为了让 fallback 通过，把所有评价字段变成可选，掩盖真实输出错误。

控制：采用条件 Schema。standard 仍强制总分和至少一个维度；degraded 反向强制总分为 null、维度为空、原因非空。Memory write 仍强制至少一条条目；只有明确 skip 才允许空列表。

## 5. 假事实残留风险

风险：即使删除“简历项目”，规则抽取仍可能把普通文本误判为技能或把 matching 的固定文案当成用户事实。

控制：Resume 只按原文逐字匹配有限技术标签；QuestionBank 技术栈只取 resume/JD 的结构化技能字段，matching 仅用于准备重点和缺口。降级输出不声称候选人完成过具体项目、指标或故障处理。

## 6. 题目表面唯一、实质重复风险

风险：删除编号后仍使用同一模板替换少量词。

控制：题库使用不同能力任务模板（边界、设计、排障、取舍、测试、可靠性等），测试同时检查规范化文本唯一、技术栈差异和主题动词差异；不只检查 ID。

## 7. memory gate 绕过风险

风险：MemoryAgent 安全，但 EvaluationService 直接读取 `memory_update` 并落库，或反之。

控制：两层门禁。MemoryAgent 对 acceptance/未来显式流程返回 skip；MemoryService 在真正写数据库前依据持久化 evaluator mode、source context、agent run mode 和 write decision 再检查一次。

## 8. `.env` 或真实网络泄漏风险

风险：测试模块在 fixture 前导入应用，或某段代码绕过 LLM client 直接访问网络。

控制：根级 conftest 在测试收集前设置环境；`APP_ENV=test` 从配置层禁用 dotenv；socket guard 在 pytest 配置期安装，覆盖直接和间接连接。真实测试只有显式 flag 才解除阻断。

## 9. 真实 smoke 可用性风险

风险：hermetic conftest 无条件清空 key，导致显式 smoke 永远无法运行。

控制：会话启动时先识别显式 real flag。普通会话强制清空；显式 real 会话保留启动进程已提供的 provider/key，但仍不由 pytest 读取 `.env`。本阶段只验证门禁，不实际调用 provider。

## 10. 迁移风险

风险：SQLite batch alter 与 PostgreSQL 类型/default 行为不同，或 downgrade 丢失 degraded 空分数记录。

控制：新增列先带 server default；nullable score 使用 batch alter；升级测试覆盖全新数据库和前一 revision。downgrade 前无法把 null 安全还原为可信分数，因此 downgrade 对 degraded 记录存在信息约束：必须先清理或显式阻止。实现中应选择阻止有 null score 的 downgrade，而不是填充伪分数。

## 11. 残余产品风险

本阶段不会解决真实 provider 成功率、question-bank 长尾延迟、Prompt v0.2 Java 回退、跨模型差异或真实材料覆盖不足。安全 fallback 可以防止错误扩散，但不能把降级输出提升为真实模型质量；进入前端阶段仍需后续真实验收重新判定。
