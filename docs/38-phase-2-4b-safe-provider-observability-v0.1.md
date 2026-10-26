# Phase 2.4B：安全的逐次 Provider 调用观测

## 审计事实源与数据库边界

`scripts/run_question_bank_ab.py` 创建 `QuestionBankABRunner`，由 runner 直接调用
`agent.execute()`。它不使用生产业务链路的 `AgentHarness`、`AgentRunService`、
SQLAlchemy Session 或数据库提交。该实验是 **report-only**；`agent_runs` 为空
不是漏 commit，也不需要为 A/B 实验增加数据库表或迁移。生产业务的 AgentRun
写入行为不变。离线测试在禁止 SQLAlchemy Engine.connect 的情况下执行该实验。

实验目录的 `manifest.json` 是审计事实源；`question-bank-ab-report.json` 和
Markdown 报告是同步生成的审计视图。`provider_observability.mode=report_only`
及 `audit_source=manifest.json` 在两个 JSON 文件中明确声明。

旧 run1 只有聚合的 `provider` 标签，不能恢复 HTTP 状态或逐次异常细节。
加载旧格式时用 `legacy_unobserved_calls` 明确标记未观测的历史调用，绝不
根据耗时、后续成功或新调用结果补造历史失败分类。本变更不重写 run1。

## 逐次尝试白名单

所有 Provider 尝试（含 smoke、成功、失败和取消）都进入 `provider_attempts`。

| 字段 | 语义 |
| --- | --- |
| variant / case_id / pair / attempt | 冻结实验中的执行位置；attempt 在每个执行内从 1 计数 |
| call_index | 全实验累计调用序号 |
| status | started / completed / failed / cancelled |
| started_at / finished_at / latency_ms | UTC 时间及 Provider 调用耗时；未完成值为 null |
| failure_category | 规范化分类；成功时为 null |
| exception_type | 固定异常类型白名单；未知类统一为 OtherProviderError |
| http_status_code | HTTP 状态码；无法获取则 null |
| provider_error_code | 固定符号码白名单；未认可或含敏感反射值则 null |
| request_id | 仅允许有界 UUID、十六进制或 req_ / req- 标识；不符合规则则 null |
| retry_after | 有界秒数或规范化 HTTP-date；不符合规则则 null |
| filtered_fields | 被过滤的字段名；不包含被过滤的值 |
| token_usage_available / token_usage_status | 完整用量是否可用；available / unknown / not_available |
| token_usage | 三个非负整数或 null；不保存原始 usage 对象 |

smoke 使用 `variant=smoke`、`case_id=provider_smoke`、`pair=0`、`attempt=1`。

不保存异常原文、异常的动态类名、响应正文、请求 URL、完整输入、Prompt、
API key 或 Authorization header。禁止对异常使用 `str()` / `repr()`。
HTTP 错误正文只在内存中检查 `error.code`，仅固定白名单值可以输出。
Authorization 及客户端凭证仅在内存中用于拒绝反射进诊断字段的敏感值。
未认可的 request-id 和 error code 会丢失其原值，这是安全过滤的明确取舍。

## 分类规则

| 可观察证据 | 分类 |
| --- | --- |
| HTTP 401 | auth |
| HTTP 403，或明确的 model_access_denied / model_permission_denied 等权限码 | permission |
| HTTP 429 | rate_limit |
| 其他 HTTP 4xx | invalid_request |
| HTTP 5xx | provider_server |
| httpx.ConnectTimeout | connect_timeout |
| httpx.ReadTimeout | read_timeout |
| httpx 非超时传输异常、原生 ConnectionError 或 DNS gaierror | network |
| 其他异常，含无法确定阶段的通用超时 | unknown_provider |

HTTP 状态码优先于正文符号码。取消单独标记 `status=cancelled`，不把取消
伪装成 Provider 读取超时。分类描述本次可观察到的错误，不自动证明故障瞬时性。
分类不改变 Agent 原有的 failure_counts、重试次数或 fallback 策略。

## 立即持久化和中断

调用前写入 started 记录、调用计数和未知 usage；调用结束后立即补齐白名单
结果并写入 manifest、JSON 报告和 Markdown，再将异常重新抛给原来的重试/
fallback 逻辑。成功尝试也立即落盘。每个文件使用临时文件、flush、fsync 和
原子 replace；不等待整个 Agent、case 或 pilot 结束。

三个文件不构成跨文件事务。若进程恰在文件替换之间终止，以 manifest 为准。
重新加载发现 started 记录，或已观测但尚未提交到 runs 的执行时，重建报告并
停止为 `incomplete_interrupted`，要求全新目录，不自动重放未知结果的调用。
若审计写入失败，抛出固定文本的 QuestionBankABAuditError，越过 Agent 的
重试/fallback 捕获并中止实验，防止无审计地继续调用。

## Token usage 语义

逐次记录、smoke、执行记录、variant 汇总和实验 budget 中，任一相关调用的
某项 usage 缺失，该项实际总量就为 null，Markdown 显示 unknown/not_available。
只有明确收到数值 0 时才报告实际 0。部分 usage 不会补齐缺失字段为 0。

`known_token_usage` 保存可确认的用量之和，是**下界**，不是完整实际消耗；
预算守卫继续基于该已知累计量工作。`missing_token_usage_calls` 按字段计数，
原有 unknown_usage_calls / missing_usage_failure_calls 保留。
失败后成功也不会抹去前次缺失的用量；用量不完整的执行不进入 token 配对比较。
原有成功响应缺 total usage 时停止的门禁保持不变。

## 离线验证与冻结边界

专项测试使用 httpx.MockTransport 和本地 fake Provider，模拟 401、403、429、
400、500/502/503、连接超时、读取超时及网络错误；检查所有输出文件均不含
测试敏感标记。另覆盖失败后重试前的落盘、未知异常类名、恶意诊断字段、部分
usage、带/不带 usage 的失败后成功、审计写盘失败以及 os._exit 硬退出。

测试会话清空凭证、关闭真实验收开关，阻止并统计非 loopback socket 尝试。
硬退出子进程同样阻断外部连接；Windows asyncio 的本机 self-pipe 不属于
Provider 网络访问。专项测试、全量离线测试及现有迁移 round-trip 测试必须通过。

本变更只涉及实验包装层、安全诊断工具、离线测试和文档。不修改 Prompt、
模型输出 Schema、模型参数、最大尝试次数、fallback、assembler、生产默认
Agent 或冻结输入。冻结文件与 run1 文件使用变更前后 SHA-256 比对。
本工作不调用真实 Provider，不创建 run2，不执行真实完整 A/B。
