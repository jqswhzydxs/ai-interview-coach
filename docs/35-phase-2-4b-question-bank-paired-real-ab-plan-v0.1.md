# Phase 2.4B：QuestionBank 配对式真实 A/B 实施计划 v0.1

## A. 离线实现

1. 冻结三套结构化输入并记录 hash。
2. 新增独立 `QuestionBankABRunner`，不复用七 Agent `LLMAcceptanceRunner.run()`。
3. 实现 smoke → pilot → full → finalize 状态机。
4. 实现项目级 lock、manifest、原子报告更新、资产复核、绝对截止与调用/token 预算。
5. 生成主报告、问题文本盲评包、metadata 盲评包和严格评分模板。
6. 增加显式 CLI；真实阶段必须保留 `SAVE_FULL_LLM_LOGS=false`。

## B. 离线验证

1. fake provider 完成 30 次配对执行，只允许 `ProviderSmoke`、`QuestionBank`、`QuestionDraftBank` 请求。
2. 验证每 variant 15 次、pilot 计入 pair 1、奇偶 pair 顺序交替。
3. 验证 retry/fallback/failure type/token/latency/assembler/Schema 记录。
4. 验证并发 lock、资产变化、provider-call 预算、token 预算和 pilot 门禁。
5. 用永不返回的 fake provider 验证绝对截止、取消传播、0 遗留 task 和 lock 释放。
6. 完成盲评导入与 real-only/user-visible 汇总的离线测试。
7. 保留本机 `.env` 运行全量 pytest 和迁移 round-trip，确认 socket attempts=0。

## C. 真实执行（需离线门禁后单独确认）

1. 创建唯一 real run directory。
2. 运行 `smoke` 并检查 manifest。
3. 运行 `pilot`；仅在 `pilot.status=passed` 时继续。
4. 运行 `full`，达到 30 次或由预算/截止/资产门禁停止。
5. 先在隐藏 variant 的问题包上评分，再评价逐题 metadata，最后导入评分解盲。
6. 运行离线全量测试和迁移专项。

## D. 不修改项

- provider client、model、temperature、timeout；
- BaseAgent 的重试次数和所有权；
- QuestionBankAgent 默认运行时引用；
- Prompt、Schema、assembler、其他 Agent、API、数据库、前端。

