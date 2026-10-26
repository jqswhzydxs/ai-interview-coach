# Phase 2.4D-B Provider 稳定性与 Token 记账协议 v2 Plan

## 实施顺序

1. 在任何代码变更前，对 Prompt、metadata v2、Schema、fixtures、模型/Provider 配置、生产路径、protocol v1 和 run1/run2/run3 全目录建立 SHA-256 基线。
2. 只读解析三次运行，仅提取状态、attempt 类型、延迟和 token usage；不复制请求正文、原始响应、凭据或异常文本。
3. 审计 timeout 层级、retry owner、`RemoteProtocolError` 分类、HTTP client/连接池生命周期及传输配置来源。
4. 在新模块实现 protocol v2 五类独立记账语义、pair 准入和硬 Provider call budget。
5. 在新模块实现单账本 readiness gate，冻结最多 2 次、每次 1 call、无内部 retry 的规则。
6. 生成三份独立事件记录及协议/client 审计；保持旧运行字节不变。
7. 用 fake attempts 覆盖 timeout/network/retry/fallback/usage unknown/预算/pair 排除/readiness，不访问网络。
8. 执行专项、全量离线、迁移、compileall、`git diff --check`、socket guard 和保护哈希复核。
9. 保存最终验证报告并停止；不创建 run4，不开始新的真实 smoke/pilot/full。

## 验收规则

- run1 成功 response output token 独立保留为 2528，同时 billing 显著标为 incomplete。
- run2 明确为零调用的配置阻塞，不进入真实实验集合。
- run3 的两个 unknown attempt 保持 `null`，fallback 完全排除。
- v1 和三次运行目录的 hash 不变。
- readiness 输出与 A/B 隔离，失败不能通过新目录绕过。
- 没有真实 socket 尝试，生产 `QuestionBankAgent` 绑定不变。
