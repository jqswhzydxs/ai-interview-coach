# Phase 2.4D-A QuestionDraft Prompt Token 单变量实验 Spec

日期：2026-10-21（Asia/Singapore）。协议版本：`phase-2.4d-question-draft-prompt-token-v1`。

## 目标与历史边界

本协议比较同一 QuestionDraft Candidate 链路的两个 Prompt：baseline 为 `question_bank_draft_agent_v0.1.md`，candidate 为 `question_bank_draft_agent_v0.2.md`。唯一实验变量是 Prompt 文本。

Phase 2.4B 的 Candidate 已知平均 output tokens 2067.4615 仅用于提出优化目标。它来自旧协议，不能充当本协议 baseline、可比较 pair、门禁样本或通过证据。本协议不得回写、重新 finalize 或重新解释 Phase 2.4B。Phase 2.4C metadata v2 的 AI 盲评结论和 Candidate-only 集成同样保持只读。

2.4D-A 只完成 Prompt 候选、预注册、runner、离线测试和实验准备。它不访问真实 Provider，不产生真实 Token 结论，不切换生产，不开展前端工作。真实 smoke/pilot/full 必须等待单独的 2.4D-B 授权。

## 唯一变量与冻结项

两个 variant 由同一个 `QuestionDraftPromptExperimentAgent` 类执行，通过构造参数 `prompt_variant` 显式注入 Prompt 资产。省略、未知值、哈希漂移均拒绝；没有环境变量或全局默认开关。

两个 variant 共享同一个 Provider client 实例、model、QuestionDraftBank Schema、QuestionBankMetadataAssemblerV2、最终 QuestionBank Schema、temperature=0.2、未设置的 max tokens（记录为 null）、Provider 请求参数、client timeout=60 秒、max attempts=2、variant deadline、fallback、8/8/9、三套冻结 fixture、证据/技术栈/重复/安全检查。Prompt 之外的请求内容生成指纹必须相同。

QuestionDraft 的 `question_text` max_length=500 保持不变。v0.2 的模块建议长度仅存在于 Prompt 与实验诊断，不进入 Schema 或 assembler。

生产 `PrepPackageService` 继续实例化 `QuestionBankAgent`。原 Draft Agent、v0.1 Prompt、metadata v2 与生产路径不作修改。

## v0.2 写作目标

每题只有一个核心考察目标，以一个直接问句表达，最多两个紧密相关子条件。不复述完整 Resume/JD，不输出答题提示、方向、评分标准、示例或解释。压缩不得删除区分候选人所必需的技术、失败场景、工程约束或证据边界，不得编造经历、项目、指标或技术栈。

建议范围：self-intro 30–80 字符，professional 45–105 字符，behavior/project 40–100 字符。范围是诊断目标，不是生成有效性的替代 Schema。

## 执行计划

2.4D-B 如获授权，先运行一个独立 candidate v0.2 smoke；它不进入配对统计。pilot 是三套 case 的 pair 1：3 cases × 2 variants = 6 runs。full 继续 pair 2–5，最终每 case 五个 pair，共 30 个配对 runs。

奇数 pair 顺序为 baseline → candidate，偶数 pair 为 candidate → baseline。case 顺序使用冻结 fixture。deadline 只取消当前 variant；runner 必须继续尝试当前 pair 的另一方，然后才决定是否停止后续 pair。

runner 使用独占锁和幂等 manifest。重复 smoke/pilot/full 不增加调用、不重建 submission、不改变输出。新实验目录必须为空，且不能位于 run2、Phase 2.4C metadata 报告或 Candidate 集成报告目录内。

## 审计、用量和预算

默认调用预算 62：smoke 最多两次尝试，30 runs 各最多两次。默认已知 total token 上限 250,000。每个 Provider attempt 都记录成功/失败、过滤后的故障类别、延迟及 input/output/total tokens。

每个 run 记录真实冻结 input 和最终 QuestionBank output、Prompt version/SHA-256、metadata assembler version、调用/重试、execution mode、fallback、Schema、strict count、assembler、跨栈、重复、证据、长度分布、Question 文本与最终输出指纹。完整 input/output 仅在新实验目录 `audit/executions.json`，不进入公开报告或盲评包；不保存 raw provider response。

只有该 run 的全部 attempts 都具有三个非负 Token 字段时，run usage 才是 available。任何缺失或部分 usage 都标记 unknown，三个聚合字段为 null；已知下界另存，绝不填 0。预算不可证明时完成当前 pair 后停止。字符长度永远不能替代 Provider output tokens。

## 长度诊断

每个完成输出及每个 variant 汇总以下字符指标：平均值、P50、P95、最大值；按模块统计低于和超过建议范围的题数，并给出超过模块上限总数。指标不参与 Token 门禁。

## 盲评

runner 为每份合法输出生成随机 submission ID 和独立随机顺序。公开 packet 只含证据上下文及题目正文/metadata，不含 variant、Prompt、case、pair、执行顺序、指纹或私有映射。模板按相同盲序排列。

独立 evaluator 必须记录真实类型（AI 或 human）、标识与 `independence_confirmed=true`。正文按个性化、技术正确性与栈边界、覆盖与实质多样性、训练价值、清晰度五项 1–5 分；metadata v2 对每题给出适配度 1–5 分。不得把 AI evaluator 表述为人工。

## 预注册门禁

所有门禁是必需项，任一失败即 v0.2 不通过：

| 门禁 | 要求 |
| --- | --- |
| pilot | candidate v0.2 3/3 real 且最终安全输出有效 |
| full real success | candidate ≥ 90% |
| case coverage | 每 case candidate real ≥ 4/5 |
| 内容安全 | Schema、assembler、strict count、跨栈和重复失败总数为 0 |
| Token 可评价性 | 至少 12 个 usage 完整且双方 real/安全的 comparable pairs |
| 绝对 Token | 新协议 comparable candidate 平均 output tokens ≤ 1800 |
| 相对 Token | paired output token reduction 相对同批 v0.1 ≥ 10% |
| 延迟 | candidate P95 ≤ 90 秒，max ≤ 120 秒 |
| 正文质量 | candidate 综合均值 ≥ 4.0 |
| 相对正文质量 | candidate 相对 v0.1 下降不超过 0.2，即 candidate−baseline ≥ −0.2 |
| metadata v2 | candidate 适配度均值 ≥ 3.5 |

少于 12 个 comparable pairs 时，绝对和相对 Token 门禁均为 `not_evaluable`，不能使用 2.4B 均值或字符长度补足。盲评未完成时质量门禁与最终 verdict 为 pending/not_evaluable。

## D-A 停止点

离线检查通过后停止。`prepare` 和 `status` 可离线运行。CLI 的 smoke/pilot/full 同时要求未来显式 `--authorize-phase-2-4d-b-real` 与既有 real acceptance 配置；D-A 不满足前一授权条件，也不执行这些命令。
