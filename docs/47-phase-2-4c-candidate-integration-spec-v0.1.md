# Phase 2.4C Candidate Integration Spec

日期：2026-10-21。授权范围：独立实验路径接入已经通过 AI 盲评的 metadata v2，仅离线验证。

## 资格与边界

最终决策见文档 46。replay/holdout 的 metadata v2 冻结门禁通过，只授予 Candidate 集成资格。整个候选与 Phase 2.4B Token 效率未通过，不改变生产默认选择。

## 接口与选择

新增 `app/agents/question_bank_candidate_agent.py`，继承原 `QuestionBankDraftAgent`。调用者必须传入 `metadata_version="v1"` 或 `"v2"`；省略或其他版本拒绝。v1 对应原 `QuestionBankAssembler`，v2 对应原 `QuestionBankMetadataAssemblerV2`。选择属于实例，不读取环境变量或全局开关。原生产 Agent、Draft Agent 和两个 assembler 文件保持字节不变。

构造期可显式注入 `assembler_factory`。初始化异常、空返回、与所选版本不匹配的具体类型均抛出 `CandidateIntegrationError`，在 Provider 调用前终止，不偷偷改为另一个 assembler。构造完成后的实例替换、版本漂移和源资产漂移同样终止。

普通 `run/execute` 复用原 Draft 的请求、QuestionDraftBank Schema、Prompt、模型参数、Provider client、retry 和 fallback。组装期内容校验失败仍走原两次尝试和安全 fallback，不改变生产或基础类行为。冻结重放通过 `replay_draft` 使用同一实例 assembler；失败直接抛出，不补造题库。

`last_candidate_record` 是与最终题库分开的实验记录，只读副本。实验运行器须将其与结果一起持久化，不塞入 API 或 DB Schema。记录包含所选版本、规范 assembler 版本、是否实际应用及实际应用版本、源文件 SHA-256、资产清单摘要、Prompt 版本、输入/草稿（重放时）/输出摘要、执行模式及调用次数。mock/fallback 的 `metadata_applied=false`、实际版本为 null，不能算作 v2 成功集成样本。失败不会留下上次成功记录。

## 固定行为

QuestionDraft 与 QuestionBank 最终 API Schema、全部 question-bank Prompt、模型和参数、retry/fallback/client、8/8/9 计数、question_text、稳定 ID、模块与顺序、技术栈/重复/证据安全检查均保持不变。metadata v2 本身及规则库沿用通过评审时的字节哈希。

## 离线验收

使用冻结的 replay fixture 15 份及 holdout 4 份，验证其与 run2 正文包、原输入和 holdout 哈希的联系。v1/v2 各 19 份，均重复运行；完整题库须与既有 `audit/replayed-question-banks.json` 对应版本相等，且 v1/v2 正文、ID、模块和顺序相同。验证最终 Schema、严格数量、重复与 v2 证据来源。

新的离线运行器不创建评审包、不重新 finalize、不调用模型生成；socket/subprocess 与保护目录写入受到 guard 拦截。实验记录携带资产和输入哈希。专项、全量离线、迁移、compileall、diff 检查和保护文件哈希必须全部完成。degraded evaluation 与长期记忆安全使用既有离线回归覆盖。

## 非目标

不启动真实 Provider，不改 Prompt，不开始 2.4D 实验，不切换生产，不做前端。不修改任何既有实验报告、run2、盲评包、评分或最终报告。所有本阶段报告写入独立新目录。
