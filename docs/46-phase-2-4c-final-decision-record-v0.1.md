# Phase 2.4C 最终决策记录

日期：2026-10-21（Asia/Singapore）。范围：metadata v2 Candidate-only 离线集成。

**决定：metadata v2 两个冻结门禁均通过，获得独立实验 Candidate 集成资格。整个 QuestionBank Candidate 尚未通过，不切换生产默认 Agent。**

依据为已有 `storage/reports/question-bank-metadata-phase-2-4c-offline-20261020/metadata-review-final-report.json`。evaluator 类型为 **AI**，标识为 `Codex (GPT-6) / Phase 2.4C independent metadata blind reviewer / 2026-10-21`，独立性声明为 true。不得表述为人工评审。本记录不重新评分、不修改旧报告或盲评文件。

| 冻结门禁 | 阈值 | v2 观测值 | 决策 |
| --- | ---: | ---: | --- |
| replay Candidate metadata mean | ≥ 3.5 | 3.952 | 通过 |
| holdout metadata mean | ≥ 3.5 | 3.750 | 通过 |

bank win/tie/loss = **19/0/0**；question win/tie/loss = **369/103/3**。统计来自 AI 独立盲评，不是集成代码的工程检查得分。

Phase 2.4B 的 Token 门禁仍未通过或不可评价：相对节省门禁缺乏足够可比较 pair，状态为 not_evaluable；绝对输出均值 2067.4615 超过 1800，但该替代阈值未启用为 gating。不得据 metadata 达标推断 Token 效率通过。2.4B 决策与报告保留原样。

本次仅批准显式选择 `QuestionBankCandidateAgent(metadata_version="v2")`，冻结 metadata 基线供后续 Phase 2.4D 单变量优化设计使用。原 Draft/v1 可复现，生产仍由 `PrepPackageService` 实例化 `QuestionBankAgent`。没有环境变量、全局默认开关或自动晋升行为。

集成验收独立记录在 `docs/51-phase-2-4c-candidate-integration-validation-report-v0.1.md` 及新的 `storage/reports/question-bank-candidate-integration-phase-2-4c-20261021/`。不访问真实 Provider、不开展 Token 优化、不开始前端开发。完成后停止，等待 Phase 2.4D Token 单变量优化设计。
