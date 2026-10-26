# Phase 2.4D-F-A Offline Validation Report

验证日期：2026-10-24（Asia/Singapore）。状态为 `offline_implementation_complete`。本阶段 Provider calls=0；未创建正式 v5 readiness ledger 或 A/B 目录，未执行 readiness attempt、smoke、pilot、full 或 finalize。

## 实现结果

新增 Prompt v0.3、显式 v0.2/v0.3 实验绑定、non-thinking DeepSeek 实验 client、protocol v5 记账、readiness runner/CLI、A/B runner/CLI 与机器可读预注册。两侧固定 `thinking.type=disabled` 且不发送 `reasoning_effort`；归一化 Prompt 后请求逐字段一致。普通 DeepSeek client、生产默认 QuestionBankAgent、Schema、metadata v2、fixtures 与 v1–v4 runner 未改变。

Prompt 测试覆盖 only-question-text、8/8/9、证据边界、覆盖、训练价值、禁止虚构、无特定技术栈硬编码、v0.2 哈希、metadata v2/QuestionBank 兼容与生产默认不变。协议测试覆盖 readiness 两次上限与幂等、单 call、无 retry/fallback、内容与 usage 拒绝、请求漂移、15 pairs、交替顺序、deadline/retry/RemoteProtocolError、fallback 排除、comparable pair、62-call 硬停止、匿名盲评 30/150/750、AI evaluator 元数据、五维质量门禁和隐私过滤。

Fake token 与评分仅验证计算和状态机，不是正式实验证据。paired output-token change 仅报告；测试确认不存在相对 Token 降幅门禁。

## 验证结果

| 检查 | 结果 |
|---|---|
| Prompt + v5 专项 | 37 passed，real socket attempts=0 |
| v1–v4 历史协议回归 | 87 passed，real socket attempts=0 |
| 全量离线测试 | 487 passed，1 skipped，1 条既有弃用 warning，real socket attempts=0 |
| 迁移测试 | 3 passed，real socket attempts=0 |
| compileall | passed |
| `git diff --check` | passed；仅既有 LF/CRLF 提示 |
| socket guard 专项 | 6 passed，real socket attempts=0 |
| CLI `--help` | readiness 3 commands、A/B 6 commands 均通过 |
| 冻结资产 SHA-256 | 193/193 passed，missing=0，changed=0 |
| 正式 v5 目录检查 | readiness ledger 与 A/B 目录均未创建 |

最终命令结果记录于同目录的 `offline-validation-report.json`。机器可读预注册 SHA-256 为 `be27f8f5bebb5141e7781f74d9abbf6044d15a2ba4f850febc61ba1f0655c768`。冻结保护基线包含 193 个文件，基线文件 SHA-256 为 `850dec298e464903973b0f3b7ffa9a16591ea696c016ad740b6a20c49ad39c10`。

本阶段完成后停止。下一步只能在用户逐阶段授权后按 Command Guide 执行 readiness、smoke、pilot、full 和 finalize。
