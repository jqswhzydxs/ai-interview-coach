# Phase 2.4D-A QuestionDraft Prompt Token Tasks

日期：2026-10-21。

- [x] 冻结 2.4B/2.4C、生产与现有 Candidate 资产的开工哈希。
- [x] 新建 `question_bank_draft_agent_v0.2.md`，只改变 QuestionDraft Prompt。
- [x] 新建显式 Prompt 依赖注入实验 Agent；v0.1/v0.2 使用 exact metadata v2。
- [x] 新建 paired runner，支持 smoke、3×2 pilot、每 case 五 pair full、交替顺序与幂等恢复。
- [x] 记录真实 input/output、Token/usage、延迟、重试/fallback、安全检查、长度和指纹。
- [x] usage 缺失为 unknown/null；deadline 后继续当前 pair 另一 variant。
- [x] 新建盲评 packet/template/private map，随机盲序且隐藏 variant。
- [x] 固化至少 12 pairs、1800、10%、延迟、正文与 metadata v2 门禁。
- [x] CLI 的真实阶段增加 2.4D-B 命令行授权与 real acceptance 双重门禁。
- [x] 专项测试通过并保存日志：21 passed。
- [x] 全量离线与 degraded/memory 安全回归通过：340 passed，1 real_llm deselected。
- [x] 迁移、compileall、git diff --check、socket guard 通过。
- [x] 冻结资产终检无变化，完成离线验证报告。
- [x] 停止，等待是否授权 Phase 2.4D-B 真实 smoke/pilot/full。
