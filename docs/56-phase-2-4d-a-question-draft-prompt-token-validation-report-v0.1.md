# Phase 2.4D-A QuestionDraft Prompt Token 离线验证报告

日期：2026-10-21（Asia/Singapore）。

结论：**新的 Prompt 单变量 Token 协议、v0.2 候选、paired runner 和离线实验准备通过工程门禁。真实 Token、延迟与独立盲评门禁尚未执行，状态为 pending/not_evaluable。生产默认未改变。**

## 交付结果

新增 `question_bank_draft_agent_v0.2.md`，要求单一核心目标、一个直接问句、最多两个紧密子条件，并保留必要技术/场景/约束/证据边界。建议长度只写入 Prompt 和诊断。

新增 `QuestionDraftPromptExperimentAgent`。baseline/candidate 必须显式选择，使用同一个 Agent 类、同一个 Provider client 与 exact `QuestionBankMetadataAssemblerV2`。测试构建两份 LLMRequest 后移除各自 Prompt 文本，剩余 system prompt、user prompt、response Schema 和 temperature 完全相同。未知 variant、错误 assembler、Prompt hash 或绑定漂移均在 Provider 调用前终止。

新增 `QuestionDraftTokenExperimentRunner` 与 CLI。离线 `prepare` 已执行，状态 `prepared_offline`，Provider calls=0，runs=0，所有真实门禁为 pending/not_evaluable。CLI 的 smoke/pilot/full 要求未来 `--authorize-phase-2-4d-b-real` 和 `RUN_REAL_LLM_ACCEPTANCE=true` 双重条件；本阶段没有执行。

## 固定资产

| 资产 | SHA-256 |
| --- | --- |
| baseline Prompt v0.1 | `125a90d896d481b616955da5aebf7a5bdfb32be252c9ced0f47ed71c7ba4cde3` |
| candidate Prompt v0.2 | `f62170fcfab44a74c153f1c0af5195acf227ab2c8d2acce28178792890e82c4e` |
| metadata v2 assembler | `9b50ded10d174a248f4de94df62cbf45980e42d68bb818d8fabdf097c5be2888` |
| QuestionDraftBank Schema | `cabd200dca2e0eb0cda6b2c33cc860329e921adde31413529c12f53b12a93d1d` |
| final QuestionBank Schema | `fdd9313aab580cc9e5ce01e4193bd0510b2d2a0654b4cc280619ba5fd3cd578a` |
| frozen Go/Java/Python fixture | `286b6f1b784ea5b675c86aa83c2dd7ea6597b6f6f04be4541033d90e779c7a1c` |

fixture hash 已硬编码进协议并有拒绝测试。manifest 另行冻结 Base/Draft Agent、Prompt loader、metadata rules、assembler checks、两个最终 Schema、LLM contract、OpenAI-compatible/DeepSeek/Kimi client、Provider config/observability、分析/证据检查、runner、生产 Agent 与生产路由。每阶段重新核对。

QuestionDraft `question_text.maxLength` 经 Schema 测试确认仍为 500。Provider 请求仍未设置 max tokens，协议记录为 null；temperature=0.2、client timeout=60 秒、max attempts=2、variant deadline≤120 秒。

## runner 离线行为验证

fake Provider 完整模拟执行了一个 candidate smoke 和 3 cases × 5 pairs × 2 variants。fake usage 为 baseline 2000、candidate 1600，用于验证公式，得到 15 comparable pairs、candidate 平均 1600、paired reduction 20%。这些数字是测试夹具，不是模型实验结果，不能用于判断 v0.2 通过。

验证结果包括：

- 奇数 pair baseline→candidate，偶数 pair candidate→baseline；pilot/full 重复调用不增加请求或改变文件。
- 31 个 fake 请求全部只请求 `QuestionDraftBank`；没有运行其他业务 Agent。
- 每个合法 run 使用 metadata v2，记录 Prompt version/hash、真实 fixture input、最终 output、三类 Token、usage 状态、延迟、retry/fallback、安全检查、字符分布和两个输出指纹。
- 完整 375 个 candidate 问题的汇总支持平均、P50、P95、最大及模块超限计数；报告明确 `character_length_is_token_substitute=false`。
- missing usage 的 input/output/total 全为 null，状态 unknown，不写 0；Token 门禁 not_evaluable。
- pilot 只有 3 comparable pairs，绝对与相对 Token 门禁均 not_evaluable；达到 12 pairs 后才计算。
- baseline deadline 被取消后，当前 pair 的 candidate 仍执行；随后因 usage/budget 不可证明停止后续 pair。
- invalid Schema 和 assembler/跨栈失败触发原 retry/fallback，fallback 不标记 metadata v2 applied，也不进入 comparable pair。
- blind packet 使用随机 submission ID 和随机顺序；递归检查不存在 variant、Prompt、case、pair、执行顺序或指纹字段。独立 AI 类型在测试 finalize 中保持为 AI。
- fake 完整 review 验证全部预注册 gate 的计算和 any-failure rejection 结构；没有生成真实质量结论。

## 验证命令结果

| 检查 | 结果 |
| --- | --- |
| Phase 2.4D-A 专项 | 21 passed |
| 全量离线 | 340 passed，1 real_llm deselected |
| socket guard | 所有 pytest 会话 real socket attempts=0 |
| 迁移 | 3 passed |
| compileall（app/tests/scripts） | exit 0 |
| git diff --check | exit 0；仅既有 LF/CRLF 提示 |
| 新文件 whitespace 检查 | 通过 |
| 冻结资产哈希 | 80/80 不变 |

全量回归覆盖既有 degraded evaluation 和长期记忆安全链。唯一 warning 是已有 Starlette TestClient/httpx 弃用提示；本阶段没有修改依赖以处理该提示。

## 历史与生产保护

开工前记录的 80 个保护文件包括 run2、Phase 2.4C metadata 报告、Phase 2.4C Candidate 集成报告、生产/安全路径、v0.1 Prompt、Schema、fixture 和文档。终检变化为 0。runner 对三个历史实验目录及其子目录执行路径重叠拒绝。

`PrepPackageService` 仍引用 `QuestionBankAgent`，其 Prompt 版本仍为 `question_bank_agent_v0.1`。没有生产开关、API/DB Schema 或前端变更。

本协议在报告中固定 `phase_2_4b_interpretation=immutable_historical_result_not_rewritten`。2.4B 的 2067.4615 不进入本协议门禁，也不能被本阶段重新解释。

## 本地证据与停止点

本地离线证据位于 `storage/reports/question-bank-token-phase-2-4d-a-offline-20261021/`：专项/全量/迁移/compileall/diff 日志、保护哈希、socket 汇总、最终机器验证报告，以及 Provider calls=0 的 `runner-plan/`。该目录遵循仓库既有 `storage/reports/*` 忽略规则；规范与结论保存在 docs。

Phase 2.4D-A 到此停止。下一步只能在获得 Phase 2.4D-B 明确授权后，新建真实实验目录并按 smoke → pilot → full → independent blind review 顺序执行。
