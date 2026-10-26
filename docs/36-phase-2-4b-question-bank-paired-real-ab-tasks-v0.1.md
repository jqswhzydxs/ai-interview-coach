# Phase 2.4B：QuestionBank 配对式真实 A/B Tasks v0.1

## 离线实现

- [x] 三套结构化输入冻结，排除原始简历/JD/API key 字段。
- [x] 专用 QuestionBankABRunner，不运行完整七 Agent 链路。
- [x] 每 case 5 pairs，pilot 计入 pair 1。
- [x] 奇偶 pair 交替 baseline/candidate 顺序并记录实际顺序。
- [x] provider smoke 和 pilot 前置门禁。
- [x] 每次执行绝对截止，直接 await，不创建后台 task。
- [x] 项目级 manifest/lock 和明确完成状态。
- [x] provider-call/token 预算与不完整报告。
- [x] Agent/Prompt/Schema/assembler/input SHA-256 冻结复核。
- [x] 每次执行可观测字段和自动跨栈/重复检测。
- [x] 问题文本与逐题 metadata 独立盲评包。
- [x] real-only/user-visible 质量汇总与门槛判定。
- [x] 安全真实 CLI，生产默认 Agent 不变。

## 离线测试

- [x] 30 次 fake-provider 配对闭环，只调用 QuestionBank。
- [x] retry/fallback/schema failure 可观测测试。
- [x] pilot 顺序与 full 前置门禁测试。
- [x] 并发 lock 测试。
- [x] 绝对截止、取消传播、零后台 task 测试。
- [x] provider-call 与 token 预算停止测试。
- [x] 资产 hash 变化中止测试。
- [x] blind review 完整性与门槛汇总测试。
- [x] 离线全量 pytest 与 socket attempts=0。
- [x] 迁移 round-trip。

## 真实阶段

- [ ] 请求并获得真实验收执行确认。
- [ ] provider smoke passed。
- [ ] 三 case 各一对 pilot passed。
- [ ] 完成 15 baseline + 15 candidate 或生成明确不完整报告。
- [ ] 完成问题文本盲评与逐题 metadata 适配度评分。
- [ ] 输出最终门槛结论。
- [ ] 真实 A/B 后再次运行离线全量测试和迁移专项。

## 离线验证记录

- Phase 2.4B 专项：9 passed。
- Phase 2.4A/2.4B 相关回归：27 passed。
- 全量离线：188 passed、1 skipped、1 warning；`real socket attempts=0`。
- 迁移专项：3 passed。
- 本机 `.env` 保留，未改名或删除。
- hanging fake-provider 被 deadline 取消；无新增 pending asyncio task，lock 正常释放。
- 离线结束后项目级 `.question-bank-ab.lock` 不存在。
- 尚未调用真实 provider；真实 smoke/pilot/full 保持未执行。
