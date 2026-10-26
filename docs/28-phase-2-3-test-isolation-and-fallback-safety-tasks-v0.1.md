# Phase 2.3：测试环境隔离与降级链路安全化 Tasks v0.1

## P0：测试 hermetic

- [x] `APP_ENV=test` 时 Settings 不读取 `.env`。
- [x] 普通 pytest 导入应用前固定 mock provider。
- [x] 普通 pytest 清空 DeepSeek/Kimi key，关闭 real smoke/acceptance 和 full logs。
- [x] 离线 socket guard 遇到真实连接立即失败，并汇总尝试次数。
- [x] real smoke 必须由显式 flag 和进程环境配置开启。
- [x] 保留 `.env` 原文件运行全量测试。

## P0：降级语义和记忆门禁

- [x] 定义 source context、quality 聚合和 fallback 判定纯函数。
- [x] 策略短路 fallback 写入 `AgentRun`，调用数与重试数保持 0。
- [x] degraded evaluation 不含总分或维度分，仍提供一般性建议。
- [x] 上游任一关键来源 fallback 时 evaluator 不调用 provider。
- [x] evaluator 自身 provider fallback 输出 degraded evaluation。
- [x] MemoryAgent 在上游 fallback/degraded 时返回 skip。
- [x] MemoryService 在持久化前独立复核，不新增 `memory_items`。

## P0：fallback 内容安全

- [x] Resume fallback 只保留原文可识别技能。
- [x] Resume fallback 的 projects/work/education/awards 不虚构内容。
- [x] QuestionBank fallback 使用 resume/JD 技术栈。
- [x] QuestionBank fallback 使用 matching 的准备重点/缺口和 preparation goal。
- [x] 25 道题文本实质唯一，不使用编号伪装重复。
- [x] Go/Java/Python sample case 的专业题集合实质不同且无跨栈关键词。

## P1：Schema、API 与迁移

- [x] `AnswerEvaluation` 增加 standard/degraded 条件约束。
- [x] `MemoryUpdate` 增加 write/skip 条件约束。
- [x] 数据库支持 nullable scores 和来源质量审计字段。
- [x] standard API 保持数字分数；degraded API 返回 null 和明确状态。
- [x] 历史数据默认迁移为 standard，不改写已有分数。
- [x] migration upgrade/downgrade/upgrade 通过。

## P1：测试矩阵

- [x] unit：Settings 不读临时 `.env`。
- [x] unit：三技术栈 QuestionBank 和文本唯一性。
- [x] unit：Resume 不虚构事实。
- [x] unit：degraded evaluation Schema 与 metadata。
- [x] unit：MemoryUpdate 条件和 MemoryService gate。
- [x] integration：来源 AgentRun 传播到评价。
- [x] integration：fallback 评价 API 无分数且 memory 为 0。
- [x] integration：策略 fallback 在 AgentRun 可查询。
- [x] e2e：三个 sample cases 完整闭环技术栈隔离。
- [x] e2e：注入 fallback 的完整闭环阻止精确评分和长期记忆。
- [x] full suite：`.env` 存在、0 真实 socket 尝试、全部通过。

## 完成定义

- [x] 未修改 Prompt、模型、provider 参数或前端。
- [x] 未调用真实 provider。
- [x] 未输出或记录任何 API key、完整敏感输入、完整原始响应。
- [x] 报告测试总数、skip/warning、迁移验证和残余风险。
