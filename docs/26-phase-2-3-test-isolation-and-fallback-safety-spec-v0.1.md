# Phase 2.3：测试环境隔离与降级链路安全化 Spec v0.1

## 1. 背景与证据

本阶段只处理以下已被真实验收或 A/B 报告证实的问题：

1. 保留本机 `.env` 运行离线测试时，pytest 会读取其中的真实 `LLM_PROVIDER`，曾导致 5 个 mock 断言失败。
2. question-bank fallback 在 Go、Java、Python 间复用带编号的相同模板，并把 FastAPI 串入非 Python 技术栈。
3. resume fallback 创建输入中不存在的“简历项目”，下游 matching 将占位内容当作事实。
4. evaluation fallback 固定返回 76 分，与真实模型的 13–40 分显著不一致。
5. fallback 题目、画像和评价可继续流入长期记忆，固化由降级造成的偏差。

Prompt v0.2 的真实 A/B 结果未通过并已回滚。本阶段不修改任何 Prompt 文件或 `prompt_version`，不更换模型，不调整模型参数，不调用真实 provider，不开发前端。

## 2. 测试环境隔离契约

### 2.1 默认离线 pytest

普通 pytest 会话必须满足：

- `APP_ENV=test`，`get_settings()` 不读取任何工作目录下的 `.env`；
- `LLM_PROVIDER=mock`，使用固定测试模型名；
- `DEEPSEEK_API_KEY`、`KIMI_API_KEY` 在进程环境中为空；
- `RUN_REAL_LLM_ACCEPTANCE=false`、`SAVE_FULL_LLM_LOGS=false`；
- 安装进程级 socket 出站阻断器；任何真实网络连接尝试立即使测试失败；
- 测试结束摘要报告真实 socket 尝试次数，成功全量测试必须为 0。

不得通过移动、重命名或删除 `.env` 达成隔离。

### 2.2 显式真实测试

真实 smoke 仍通过 `RUN_REAL_LLM_SMOKE_TESTS=1` 显式开启；真实 acceptance 仍通过 `RUN_REAL_LLM_ACCEPTANCE=true` 显式开启。pytest 内部始终不自动加载 `.env`，因此真实 smoke 的 provider、model 和 key 必须在启动 pytest 前进入进程环境。显式真实门禁打开时，pytest 网络阻断器才关闭。

`scripts/run_llm_acceptance.py` 不属于 pytest，会继续使用现有显式 acceptance 门禁。默认配置仍为 `LLM_PROVIDER=mock`。

## 3. 来源质量与执行模式

上游来源以安全摘要传递，不包含完整简历、JD、回答或原始模型响应。每个来源至少包含：

```json
{
  "execution_mode": "mock | real | fallback | user",
  "source_quality": "synthetic | trusted | degraded | user_provided | unknown",
  "agent_run_id": "optional UUID"
}
```

规则：

- `fallback` 必须映射为 `degraded`；
- `real` 映射为 `trusted`；
- `mock` 映射为 `synthetic`，不能伪装成真实；
- 用户直接输入的问题映射为 `user_provided`；
- 缺失或不可识别来源映射为 `unknown`。

来源质量只影响安全决策，不改变 Phase 2.1 的重试所有权：provider client 仍只负责单次请求，`BaseAgent` 仍是最多 2 次真实调用和一次 fallback 的唯一所有者，Harness 不重试。

## 4. 安全 fallback 契约

### 4.1 Resume

Resume fallback 只允许输出原文中逐字可识别的技能标签；无法可靠提取的教育、项目、工作经历、奖项保持空列表。不得创建“简历项目”、角色、职责、成果、指标或其他输入中不存在的事实。

### 4.2 QuestionBank

QuestionBank fallback 必须读取当前 `resume_profile`、`jd_profile`、`match_report`、`experience_profiles` 和 `preparation_goal`：

- 技术关键词优先来自 resume/JD 的结构化字段；matching 只提供准备重点和缺口，不得把未经 resume/JD 支持的技术栈升级为事实；
- 生成 8 道自我介绍、8 道专业题和至少 8 道行为/项目题，总数满足现有 Schema；
- 每道 `question_text` 在语义任务上不同，不得只追加编号；
- Go、Java、Python 等不同技术上下文的专业题集合必须实质不同；
- 不得固定注入 Python、FastAPI、PostgreSQL；
- source refs 只能概括已有结构化来源，不能补造候选人经历。

### 4.3 Evaluation

评价分为：

- `standard`：来源未发生 fallback，存在可用分数；沿用现有 0–100 评分语义。
- `degraded`：题目、简历画像、JD 画像、matching 或 evaluator 自身来自 fallback。允许输出一般性改进建议，但 `score_available=false`、`total_score=null`、`dimension_scores=[]`，不得返回 76 或其他精确分数。

`AnswerEvaluation` 对两种模式做条件校验：standard 必须有总分和维度分；degraded 必须没有精确分数，并必须携带结构化 `degradation_reasons`。

### 4.4 Memory

只有同时满足下列条件才允许自动写入长期记忆：

1. 题目、resume/JD 画像、matching、evaluation 均未使用 fallback；
2. evaluation 为 `standard` 且 `score_available=true`；
3. memory update 明确 `write_decision=write`；
4. 置信度达到现有阈值。

否则必须返回或记录 `write_decision=skip` 和结构化 `skip_reason`，且数据库中不得新增 `memory_items`。MemoryAgent 自身 provider fallback 也只能返回 skip。

## 5. 可观测性

策略触发的短路降级同样写入 `AgentRun`：

- `execution_mode=fallback`；
- `real_call_count=0`、`retry_count=0`；
- `fallback_reason.code=degraded_upstream_source` 或相应策略码；
- `failure_type=policy`，保留 fallback step；
- 不隐藏、重写或折算成 real/mock 成功。

provider 失败后的 fallback 继续保留原有 provider/schema/json/timeout 分类和调用次数。

## 6. API、Schema 与迁移兼容策略

请求 API 不变。评价响应增加：

- `evaluation_mode`；
- `score_available`；
- `source_quality`；
- `degradation_reasons`。

standard 路径的 `total_score` 仍为数字；只有 degraded 路径返回 `null`。这是为消除虚假精确评分所需的受控兼容变化，客户端应先检查 `score_available`。历史记录迁移为 `evaluation_mode=standard`，已有分数不变。

数据库为 `answer_evaluations` 增加模式、来源质量、来源上下文和降级原因字段，并把总分及维度分列改为可空。迁移必须支持 SQLite 测试和目标 PostgreSQL 方言，并提供 downgrade。

`MemoryUpdate` 增加写入决策；write 仍要求至少一条 memory，skip 必须为空且带原因。现有标准成功路径保持兼容。

## 7. 安全约束

- 不记录 API key；
- 不记录完整简历、JD、回答、Prompt 或原始模型响应；
- `SAVE_FULL_LLM_LOGS=false` 保持安全默认值；
- 来源上下文只保存执行模式、质量、组件名和 run id；
- 本阶段所有 provider 失败测试使用进程内 fake client，不进行网络请求。

## 8. 验收标准

1. 本机真实 `.env` 原样保留时，离线全量 pytest 通过。
2. pytest 摘要显示 provider=mock、真实 key 为空、真实验收关闭、socket 尝试 0。
3. 三个 sample cases 的 fallback 题库分别反映 Go、Java、Python 技术栈，问题文本唯一且无跨栈注入。
4. Resume fallback 不产生任何输入未明确支持的项目或经历。
5. 任一关键上游 fallback 会产生无精确分数的 degraded evaluation，并阻止长期记忆写入。
6. 所有策略 fallback 均可在 AgentRun 中查询。
7. 新迁移可从 base 升级到 head、可从前一 revision 升级，并验证 downgrade/upgrade 回环。
8. 单元、集成、端到端测试分别覆盖环境隔离、fallback 内容、来源传播、degraded evaluation、记忆门禁和可观测性。
