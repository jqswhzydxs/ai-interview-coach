# Phase 2.4C 离线验证报告

**状态：工程约束通过，等待新的独立 metadata 盲评。新 metadata_fit 未评分，不宣布达到 3.5，不晋升生产。**

## 决策与范围

Phase 2.4B Candidate 不通过，保持 QuestionBankAgent 生产默认。baseline 的 27 题异常及 Token 门禁限制见 39 号决策记录。历史盲评类型为 AI，不是人工评分。

独立 metadata v2 未接线到生产、QuestionBankDraftAgent 或原 assembler。Prompt、模型、参数、Schema、Provider client、重试与 fallback 均未修改；没有真实 Provider 调用或新的真实 A/B。

## 数据与检查

- 冻结 run2 Candidate 15×25=375 道原文；正文、模块、位置和稳定 ID 不变。
- 实现前冻结独立 authored holdout 4×25=100 道题，含 Rust/Axum/SQLite、新语言稀疏履历、角色迁移、中文事务问题；与 replay 精确文本重合为 0。
- 实现作者能看到 authored holdout，因此不宣称它是第三方隐藏测试集；它不含旧分数，也不用于宣称适配度达标。
- 同一输入执行 v1/v2，并分别重复验证确定性。38 份题库全部通过 Schema、严格 8/8/9、重复、正文保持和完整 metadata 技术边界。v2 所有引用均可追溯到白名单输入字段或明确标记的问句推导。

## 测试结果

| 检查 | 结果 |
| --- | --- |
| 单元 / 集成 / replay 专项 | 48 passed |
| 全量离线 | 277 passed；排除 1 项真实 Provider 测试 |
| 迁移 | 3 passed（SQLite 升降级） |
| compileall | exit 0：app / tests / scripts / alembic |
| git diff --check | 最终结果见同目录 audit-summary.json |
| 外部 socket / Provider 调用 | 0 / 0 |
| 保护资产 | 56 项哈希不变，且与 run2 记录的 8 项冻结资产一致 |

全量测试有 1 条既有 Starlette/httpx 弃用警告；未升级依赖。日志见 specialized-tests.txt、full-offline-tests.txt、migration-tests.txt。

边界覆盖：空证据、未记录项目、matching 缺口、秘密/输入指令反射、跨栈正文、跨栈 metadata、重复、数量错误、正文空白归一化、否定约束、稀疏数据、新技术栈、中英文、源目录只读保护和模拟网络审计事件。普通 depends on 不再触发 FastAPI；revealed an authorization mistake 不再被误判为索取秘密。

## 字段差异（仅描述，不是评分）

| 分区 | 实现 | purpose | framework | anchors | follow-up | advice |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| frozen_run2 | v1 | 3.0 | 1.0 | 1.0 | 1.0 | 1.0 |
| frozen_run2 | v2 | 25.0 | 20.4 | 22.6 | 17.93 | 25.0 |
| authored_holdout | v1 | 3.0 | 1.0 | 1.0 | 1.0 | 1.0 |
| authored_holdout | v2 | 25.0 | 20.75 | 21.5 | 17.5 | 25.0 |

上表为每份 25 题中不同字段值数量的平均数。purpose/advice 包含问句范围，唯一值增加部分来自回指原题，不是语义质量证据。框架、anchors、追问由意图/主题组合产生，其具体适配度仍须逐题独立盲评。

## 独立盲评材料

只向独立 evaluator 提供 blind-review/metadata-review-packet.json 和 blind-review/metadata-review-template.json：38 份、950 个评分位置，模板全部留空，没有复用旧分数。新 opaque ID 全局随机排列；包内无版本、旧 submission_id、case_id、pair、corpus_id、哈希指纹或映射。同一正文两组的证据上下文完全相同。

版本映射和带版本结果隔离在 audit/，不得提供给评审者。评审者不得读取源码、误差分析、工程比较报告、版本映射或历史分数；若使用 AI，必须标记 AI，不能表述为人工评分。保持 submission 顺序，逐题评价 purpose/source/framework/anchors/follow-up/advice。

## 限制与后续

规则库有限，未知主题使用保守的问句范围提示。metadata 当前使用英文，支持中文主题匹配并保留中文问句和证据。规则遗漏、隐含语义、否定约束、混合语言和多主题组合仍需独立评审。内容风格可能被推测，去除标签不能完全消除盲法限制。

新评分前保持 awaiting_independent_metadata_review。原 AI 评分仅用于误差分析，不能证明新版本通过。下一步验证 metadata_fit 门槛及 holdout 表现；本阶段不调整模型输出链路、不做 Token 调参、不晋升。

机器报告与评审材料：`storage/reports/question-bank-metadata-phase-2-4c-offline-20261020/`。
