# Phase 2.4D-F-A Non-thinking Prompt Protocol v5 Spec

## 1. 范围与协议身份

Protocol v5 标识为 `phase-2.4d-question-draft-non-thinking-prompt-v5`。本阶段只新增 Prompt、实验专用代码、协议和离线测试；Provider calls=0，不创建正式 readiness ledger 或 A/B 目录。v1–v4 的 readiness、manifest、report、audit、盲评与分析资产只读，v3/v4 的真实样本不得成为 v5 证据。

生产 `QuestionBankAgent`、普通 `DeepSeekClient`、QuestionDraftBank/QuestionBank Schema、metadata v2、fixtures、模型和生成参数保持不变。

## 2. 唯一变量

| 项目 | Baseline | Candidate |
|---|---|---|
| Prompt | `question_bank_draft_agent_v0.2` | `question_bank_draft_agent_v0.3` |
| Thinking | `{"type":"disabled"}` | `{"type":"disabled"}` |
| `reasoning_effort` | 不发送 | 不发送 |
| Model | `deepseek-v4-pro` | `deepseek-v4-pro` |

两侧还固定输入、Schema、metadata v2 assembler、temperature=0.2、max_tokens=null、client timeout=60 秒、execution deadline=120 秒、最多 2 attempts、retry/fallback、JSON Output 和所有安全检查。同一 pair 将 system message 中唯一的 Prompt 资产替换为占位符后，请求必须逐字段一致；不一致立即使协议失效。

## 3. Prompt v0.3 合同

v0.3 只生成 `QuestionDraftBank.question_text`，保持 8/8/9。它要求在证据存在时引用一个安全、明确的 Resume/JD/matching 事实；禁止虚构；专业题包含具体技术对象、场景、约束或权衡；项目/行为题包含决策、难点、权衡、结果或复盘等训练角度；每题一个主要目标；题库覆盖实质多样且不做同义改写。长度区间只作生成指导，不代替 Token 或质量门禁。

Prompt 不硬编码特定技术栈，不要求或输出 metadata、证据标签、答案、评分点、解释、`reasoning_content` 或 CoT。QuestionDraft 的 500 字符 Schema 上限不变。

## 4. Readiness v5

Readiness 使用 Candidate Prompt v0.3、Go fixture、non-thinking 和独立 ledger。`prepare/attempt/status` 的状态机最多允许 2 个 attempts；每个 attempt 严格 1 call，不进入 BaseAgent retry，不使用 fallback。第一次失败只能继续同一 ledger；两次失败后永久 blocked；passed/blocked 的重复 attempt 字节幂等。

只有 real、安全有效、成功 response usage 三字段完整且 billing complete，并通过 Schema、metadata v2 assembler、8/8/9、技术栈、重复和 evidence 检查时才 passed。A/B runner 在创建目录前校验 passed ledger、ledger SHA-256、Provider/model 和资产 bundle。真实 attempt 同时要求 `RUN_REAL_LLM_ACCEPTANCE=true`、`SAVE_FULL_LLM_LOGS=false` 和 `--authorize-phase-2-4d-f-a-readiness`。

## 5. A/B 状态机与记账

独立 CLI 支持 `prepare/status/smoke/pilot/full/finalize`。设计为 3 cases × 5 pairs；Pilot 只执行 pair 1，Full 只补 pair 2–5；奇数 pair baseline→candidate，偶数 pair candidate→baseline。Smoke、Pilot、Full 各有独立授权，不自动串联。单 execution 绝对 deadline 为 120 秒，Provider call 硬预算为 62。

每次 execution 分别记录 successful response usage、billing usage completeness、known token lower bound、Provider call budget 和 execution reliability。未知 usage 保持 null，不填 0、不反推。只保存明确返回的白名单数值。Fallback 不进入 Token 比较或盲评；只有双方 final output 均为 real、安全有效且成功 usage 完整的 pair 才可比较。

## 6. 盲评与隐私

Full 后生成随机匿名 `question-review-packet.json`、`question-review-template.json` 和私有 blinding map。Finalize 要求 30 份 submission、150 个正文维度整数分数、750 个逐题 metadata 分数，ID 与顺序完全匹配，并如实记录 evaluator 的 `type`、`identifier` 和独立性。AI evaluator 必须标记为 `AI`。

持久化禁止包含密钥、完整敏感输入、原始 Provider response、未过滤异常正文、`reasoning_content` 或 CoT。盲评包只保存评审所需的最小 evidence context 和结构化题目。

## 7. 最终门禁

全部必需门禁必须通过：Candidate 15/15 real safe、每个技术栈 5/5、fallback=0、request invariant mismatch=0、安全检查 failure=0、至少 12 个 comparable pairs、Candidate 平均 output tokens≤1800、P95≤90 秒、max≤120 秒、独立盲评完整、正文综合质量≥4.0、相对 baseline 提升≥0.2、五个正文维度各≥4.0、metadata v2 fit≥3.5。

paired output-token change 只报告，不设相对 v0.2 再降低 10% 的门禁。任一必需门禁失败即拒绝 Prompt v0.3 Candidate。
