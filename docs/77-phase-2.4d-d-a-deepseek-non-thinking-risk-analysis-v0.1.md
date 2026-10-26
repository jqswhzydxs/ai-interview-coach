# Phase 2.4D-D-A Risk Analysis

| 风险 | 影响 | 控制 |
|---|---|---|
| thinking 字段被 client 丢弃 | 两侧实际运行条件相同，实验无效 | MockTransport 捕获最终 HTTP body；manifest/attempt 记录 thinking 模式 |
| 同时发送 `reasoning_effort` | 引入第二变量 | payload builder 不包含该键；请求层和每条 run 均检查 absent |
| 普通业务误用 non-thinking | 生产行为变化 | 独立 client/CLI；生产 factory 和 `DeepSeekClient` 不变；无全局开关 |
| 两侧 Prompt 或参数漂移 | 无法归因 reasoning | Prompt v0.2 同哈希；同 pair `LLMRequest` 指纹相等；漂移立即 invalidated |
| non-thinking 导致 25 题不完整 | Schema 或 count 失败 | Draft/最终 Schema、metadata v2、8/8/9、evidence 和重复门禁不放宽 |
| output cap 截断 | JSON 无效 | v3 继续 max_tokens=null，不引入 cap |
| 失败 attempt usage 缺失 | 低估 billing | unknown 保持 null；billing incomplete 与成功 usage 分开；known lower bound 明示 |
| CoT 或敏感正文落盘 | 数据泄露 | 只解析白名单数字；details 禁止 response 默认序列化；审计文件无 raw response/正文 |
| readiness 连续重建目录重试 | 绕过 2-attempt 上限 | 单 ledger；第二次失败永久 blocked；A/B 前绑定 ledger SHA-256 |
| pilot 后自动 Full | 超出授权和预算 | CLI 分阶段；runner 的 pilot 只运行 pair 1；full 使用独立授权 flag |
| fallback 被误计入结果 | Token/质量失真 | comparable 和 blind submission 都要求 real、安全有效 |
| Provider 参数实际不支持 | 请求失败或字段无效 | 协议固定官方已确认的 `thinking.type`；真实 readiness 先验证同一 Provider/model 路径 |
| 与 ab1 数据混用 | 破坏单变量解释 | protocol v3、新 ledger、新目录；旧数据仅作历史背景，不参与计算 |
