# Phase 2.4C Spec：确定性 metadata 适配度校准

本阶段的生产决策仍为 Candidate 不通过；参见 39 号最终决策记录。新增独立
QuestionBankMetadataAssemblerV2，不接线到 QuestionBankDraftAgent 或生产服务。
QuestionBankAgent、原 assembler、Prompt、Draft/最终 Schema、模型参数、重试、
fallback 和 Provider client 全部冻结。没有第二次 LLM 调用，也没有真实 A/B。

输入为既有 QuestionDraftBank 和当前结构化 Resume/JD/matching/面经证据。
正文、模块、位置、稳定 question_id 不变；结果仍为合法的严格 8/8/9 QuestionBank。
沿用计数、规范化重复和最终 ID 校验，并对完整 metadata 实施技术栈边界检查。

metadata 使用题意识别、可组合主题规则和显式证据检索：

- 区分自我介绍、动机、学习、优势、未来规划、概念、比较、设计、诊断、工作流程、
  真实经历复盘，不按模块强制套 STAR。
- purpose、技术 checkpoints、anchors、追问、建议从实际问句主题组合生成；
  对未知主题保守说明问题中明确出现的约束，不注入默认技术或虚构解法。
- EvidenceRef.quote 只能来自被允许的输入字段或标为 inferred 的问句本身。
  summary 标明字段路径。matching 的 gap/priority 不当作已经具备能力或 JD 硬要求。
- 项目名称必须在 Resume.projects 中出现；没有材料支持时说明缺少证据，
  STAR 使用占位提示，不预填候选人的经历、成功结果或量化收益。
- 不输出凭证、指令注入片段或完整原始 Resume/JD 文本；未知证据不补造。

离线 replay corpus 为 run2 15 个 Candidate submission 的 375 道原文，保留
来源哈希；run2 永远只读。独立 authored holdout 不取自原问句；同时提供空证据、
技术栈冲突、秘密反射、否定约束、重复、数量错误等边界测试。

v1/v2 在同一正文和输入上比较。自动检查仅评估结构、证据可追溯性、技术边界、
完整性和确定性；字段多样性只作描述，不充当语义质量评分。新匿名 metadata 包
由独立 evaluator 重新逐题评分，绝不复制历史分数。独立盲评完成前状态必须为
awaiting_independent_metadata_review，不能声称 metadata_fit >= 3.5。

盲评目录只放匿名包和空模板，不含版本、历史 submission_id、pair、case_id 或
映射。随机独立 opaque ID、全局随机排列，版本对应关系保存在独立 audit 目录，
评审者不得读取该目录、源码或带版本比较的报告。内容风格仍可能被推测，这是
无法仅靠移除标签消除的盲法限制。

验收：单元/集成/replay、全量离线、迁移、compileall、diff-check 均通过；外部
socket 尝试为 0；冻结资产及 run2 全文件哈希不变；生产默认 QuestionBankAgent
不变。真实语义适配度属于待独立评审的门禁。
