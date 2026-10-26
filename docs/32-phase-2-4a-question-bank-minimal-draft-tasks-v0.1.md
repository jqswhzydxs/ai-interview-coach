# Phase 2.4A：QuestionBank 最小草稿协议 Tasks v0.1

## P0：协议与组装

- [x] 定义仅包含 `question_text` 的 QuestionDraft。
- [x] QuestionDraftBank 严格限制为 8/8/9。
- [x] assembler 确定性生成全部最终字段。
- [x] 最终结果通过未修改的 QuestionBank Schema。
- [x] 规范化文本唯一性和近重复门禁。
- [x] resume/JD 技术栈边界门禁。
- [x] source refs 非空且来自当前上下文。

## P0：调用与 fallback

- [x] 成功路径每个 attempt 只有一个 provider 请求。
- [x] 不按模块拆分 provider 请求。
- [x] 不改变 temperature、timeout 或 max attempts。
- [x] assembler 失败归为 schema failure。
- [x] 重试耗尽后复用 Phase 2.3 安全 fallback。
- [x] fallback 的 AgentRun 指标保持可观测。

## P0：基线隔离

- [x] 当前 QuestionBankAgent 保持 v0.1。
- [x] 新候选使用独立类和独立 prompt_version。
- [x] 同进程可分别调用基线和候选。
- [x] acceptance runner 默认仍使用基线。
- [x] 比较过程不修改全局 Prompt 指针。

## P1：测试

- [x] Draft Schema 数量与 extra-forbid 测试。
- [x] Draft 契约复杂度小于最终契约测试。
- [x] 三个 sample cases assembler 成功测试。
- [x] 编号重复、近重复、串栈、缺失证据失败测试。
- [x] fake provider 单次成功调用测试。
- [x] fake provider/assembler 失败重试与 fallback 测试。
- [x] Harness 最终 QuestionBank 和 AgentRun integration 测试。
- [x] acceptance runner 基线/候选同进程隔离测试。
- [x] 保留 `.env` 的离线全量测试与 0 socket 尝试。

## 完成定义

- [x] 未调用真实 provider。
- [x] 未修改外部 API、最终数据库结构或前端。
- [x] 未修改基线 Prompt、provider client 或其他业务 Agent。
- [x] 报告全量测试数、skip/warning 和残余风险。

## 离线验证记录

- 实施前后基线文件 SHA-256 一致：`QuestionBankAgent`、`question_bank_agent_v0.1.md`、最终 `question.py` 均未变化。
- Draft JSON Schema 为 904 字符，最终 QuestionBank JSON Schema 为 3199 字符；候选输出契约缩小 71.74%。
- 候选成功路径：每个 case 的 question-bank 阶段 1 次 fake-provider 请求。
- 候选组装/草稿失败路径：2 attempts、1 retry，随后显式 `fallback`，schema failure 保留在 AgentRun。
- 三个现有 sample cases 已由 acceptance runner 在同一进程分别执行基线与候选；未切换全局 Prompt。
- 本机 `.env` 保留；全量 pytest 的终端摘要必须作为交付报告中的最终事实来源。
