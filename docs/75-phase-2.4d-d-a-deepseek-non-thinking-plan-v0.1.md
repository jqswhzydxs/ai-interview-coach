# Phase 2.4D-D-A 实施 Plan

## 1. 冻结与隔离

1. 在任何代码修改前保存 Prompt、Schema、metadata、fixtures、Provider 参数、历史报告、ab1、旧 readiness 和 v1/v2 runner 的 SHA-256。
2. 新代码使用 v3 名称、独立 ledger 和独立运行目录规则。
3. 将 D-D-A 离线报告目录加入 v3 runner 的历史目录重叠保护。

## 2. 请求层

1. 新增实验专用 DeepSeek client。
2. 用显式构造参数选择 enabled/disabled，不读取全局 feature flag。
3. 在 HTTP body 写入 `thinking`，不发送 `reasoning_effort`。
4. 用 MockTransport 捕获真实 client 发出的 JSON，验证单变量和生产 client 不受影响。

## 3. Readiness 与 A/B

1. 从 protocol v2 的已验证记账规则建立独立 v3 模块和版本标识。
2. 建立 non-thinking readiness executor、ledger 校验和三命令 CLI。
3. 建立双 client 注入的 v3 runner；每个 variant 绑定自己的 thinking client，但共享 Prompt v0.2。
4. 保持交替顺序、deadline、retry/fallback、预算、盲评隐藏和 metadata v2 检查。
5. 将 smoke/pilot/full 的真实授权拆为三个独立 flag。

## 4. Usage details

1. response envelope 只经过白名单数字解析。
2. 实验 response object 的 details 字段禁止默认序列化。
3. measured call 和 execution 只写安全数值或 `unknown`。
4. 用包含伪造 CoT/未知字段的 response 测试持久化边界。

## 5. 验证

依次执行 v3 专项、B/B2/C 回归、全量离线、迁移、compileall、diff-check、socket guard 和冻结资产哈希验证。所有 runner execution 使用 fake client 和 pytest 临时目录，不建立正式实验目录。
