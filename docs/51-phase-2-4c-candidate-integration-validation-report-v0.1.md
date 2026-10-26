# Phase 2.4C Candidate Integration 验证报告

日期：2026-10-21（Asia/Singapore）。结论：**Candidate-only metadata v2 离线集成通过，固定基线可供后续 Phase 2.4D 设计使用。生产默认未变，整个 QuestionBank Candidate 尚未通过。**

## 决策来源

metadata 质量结论引用已经完成的独立 **AI** 盲评，不是人工评审，也不是此次集成检查重新评分。replay mean = 3.952，holdout mean = 3.750，均达到冻结阈值 3.5。bank win/tie/loss = 19/0/0，question win/tie/loss = 369/103/3。

最终决策见文档 46；新机器决策 `final-decision.json` 记录 evaluator 类型、标识、冻结门禁及既有最终报告 SHA-256。既有 Phase 2.4B Token 门禁仍未通过或不可评价。本阶段没有 Token 参数调整或 Phase 2.4D 实验。

## 实现与生产边界

新增 `QuestionBankCandidateAgent`，调用时必须显式选择 `metadata_version="v2"`；`"v1"` 明确使用原 assembler。省略/错误版本拒绝，factory 初始化异常或类型与版本不符在调用 Provider 前终止。实例绑定、v2 版本和代码资产漂移也会终止。没有全局默认开关。

原生产 `QuestionBankAgent`、原 `QuestionBankDraftAgent`、assembler v1/v2、metadata 规则库、所有 Prompt、Schema、Provider client、模型配置、Base retry/fallback 及生产服务文件与开工时字节相同。Candidate 继承原 Draft 执行链。fake transport 测试比较原 Draft、Candidate/v1、Candidate/v2 的完整 LLMRequest，相同输入请求完全相等，temperature=0.2，Schema 名称相同，均仅调用 fake transport 1 次，无新增调用。

真实 Provider 没有启动。测试中的 `real` 是已有 BaseAgent 对 fake transport 的执行模式标记，不代表使用了真实服务。故障组装保持原两次尝试及安全 fallback，mock/fallback 实验记录中 `metadata_applied=false`、实际 assembler 版本为 null，不冒充 v2 成功。

## 冻结集成比较

| 检查 | replay | holdout | 结果 |
| --- | ---: | ---: | --- |
| 冻结语料 | 15 banks / 375 questions | 4 banks / 100 questions | 与原输入、run2 正文及冻结 holdout 哈希核对 |
| 版本 | v1 与 v2 | v1 与 v2 | 每版本 19 banks / 475 questions |
| 运行次数 | 60 次组装 | 16 次组装 | 每版本每份运行两次，共 76 次 |
| 完整题库 | 30 份版本结果 | 8 份版本结果 | 38/38 与集成前对应版本完整相等 |
| 正文、稳定 ID、模块、顺序 | 全部相等 | 全部相等 | 保留 8/8/9 与 sort_order |
| 重复输入结果与实验记录 | 全部相等 | 全部相等 | 没有时间/随机字段导致漂移 |
| API Schema、数量、重复、v2 引用 | 通过 | 通过 | 不修改最终题库合约 |

技术栈与证据安全检查由原字节版本 assembler 执行，额外校验 v2 引用可回溯输入字段。全部版本结果与集成前一致，因此此次接线不改变 metadata 内容。全量回归同时覆盖原降级链、degraded evaluation 不提供伪分数、长期记忆拒绝降级结果等既有安全行为。

离线验证器的 Provider calls = 0，network attempts = 0，protected write attempts = 0。只读/socket guard 的拒绝行为另有合成 audit 事件测试，未实际建立网络连接。所有离线 pytest 会话报告 real socket attempts = 0。

## 执行检查

| 检查 | 结果 | 新报告目录内证据 |
| --- | --- | --- |
| 新增测试 | 23 passed | 包含在专项和全量结果中 |
| 专项（含原 Draft、v2、安全与记忆回归） | 104 passed | specialized-tests.txt |
| 全量离线 | 319 passed，1 real_llm deselected | full-offline-tests.txt |
| 迁移升级/降级/往返 | 3 passed，临时 SQLite | migration-tests.txt |
| compileall app/tests/scripts | exit 0 | compileall-check.txt |
| git diff --check | exit 0 | git-diff-check.txt |
| 新增文件 whitespace 检查 | 通过 | new-file-diff-check.json |
| socket guard | 网络尝试 0；拒绝测试通过 | socket-guard-check.json |
| 保护文件 SHA-256 | 297/297 不变，变化 0 | protected-assets-before/after/check.json |

全量和专项出现 1 项既有 Starlette TestClient/httpx 弃用警告；git 输出既有工作区的 LF/CRLF 提示，无 whitespace 错误。没有为处理这些提示而修改依赖、配置或旧文件。

## 资产与实验记录

所有本阶段运行证据位于独立目录 `storage/reports/question-bank-candidate-integration-phase-2-4c-20261021/`，没有写入 run2 或 Phase 2.4C 旧盲评/最终报告目录。该目录遵循仓库既有 `storage/reports/*` 忽略规则，作为本地实验工件保留；规范与验证结论另存于新增 docs。

- `candidate-baseline.json`：固定 metadata v2 的完整资产清单与摘要、验证器哈希、结果文件哈希。
- `candidate-run-records.json`：38 份带版本的实验记录；重复执行的记录完全一致。每条含所选/实际应用版本、资产清单和摘要、输入/草稿/题库 SHA-256、Prompt 版本、执行模式与调用数。
- `integration-validation.json`：38 份逐语料比较、冻结输入与 Schema 摘要、保护和网络检查。
- `integration-verification-report.json`：最终检查汇总与证据摘要。

冻结 assembler v2 SHA-256：`9b50ded10d174a248f4de94df62cbf45980e42d68bb818d8fabdf097c5be2888`。

冻结规则库 SHA-256：`ee9182782932bf13084549a39f2bae565176ef67ca23aacbefa5d276050710d4`。

原 assembler v1 SHA-256：`389d70a3b589b4d062f5ffa11cdbb59cc9841153e3e52e40422a828bd3dbbd5b`。

以上三项与既有 Phase 2.4C 离线报告记录一致。完整 Candidate 资产清单摘要为 `8d92a9e04554f357f9d8663baeb340cd0df3d2b4b8ee32c09944287c8d57d999`。

后续实验必须显式创建 Candidate 并单独保存 `last_candidate_record`；该审计信息不加入生产 API Schema。复现命令与空目录要求见文档 48。

## 限制与停止点

本次证明已通过 AI 盲评的固定 metadata 实现在独立 Candidate 接线上可复现，没有证明真实 Provider 的 Token、延迟或未来任意题目质量。生产仍为 `QuestionBankAgent`，没有前端变更。工作在本阶段停止，等待 Phase 2.4D Token 单变量优化设计。
