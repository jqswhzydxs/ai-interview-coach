# Phase 2.4D-B2 Readiness 与 Token Protocol v2 Runner 离线验证报告

验证日期：2026-10-22（Asia/Singapore）。本阶段没有访问真实 Provider，没有执行正式 readiness attempt，没有创建正式 A/B 目录或 run4。测试中的 attempt 全部由注入的 fake client 在临时目录完成。

## 1. Readiness executor

新增独立 runner 和 CLI，支持 `prepare/attempt/status`。真实 attempt 必须同时满足环境授权、显式 CLI flag、安全日志、真实 Provider、credential 和精确 model 条件。

离线测试确认：

- prepare 不调用 Provider；
- 首次成功只调用一次并通过；
- 首次 RemoteProtocolError 后可在同一 ledger 第二次成功；
- 两次失败后永久 blocked；
- passed/blocked 后重复 attempt 不新增调用且 ledger 字节不变；
- usage 缺失或内容检查失败不能通过；
- 每条 attempt 的 call count=1、retry=0、fallback=false；
- 未保存完整输入、输出正文、raw response 或异常正文；
- provider/model/assets 漂移拒绝。

## 2. Protocol v2 A/B runner

新 runner 在任何 A/B 目录创建前读取并验证 passed readiness ledger。pending、Provider/model 不一致或冻结资产漂移时，目标目录保持不存在。首次 prepare 后 manifest 固定 ledger SHA-256；后续对 ledger 的任意字节修改会被拒绝。

runner 保持 Prompt v0.1/v0.2、metadata v2、temperature=0.2、max_tokens=null、client timeout=60、deadline=120、Agent attempts=2、Provider call budget=62。protocol v1 runner 和 CLI 没有修改。

离线场景确认：

- ReadTimeout 后第二次成功：successful response output tokens 独立保留，billing 标为 incomplete，timeout/retry 单独统计；
- 两次 RemoteProtocolError：最终 fallback，successful response usage 为 not applicable，known lower bound 为 null；
- paired fallback 不进入 comparable pair，也不进入盲评 packet；
- 30 个安全 real runs 形成 15 个 comparable pairs；
- fake baseline/candidate output tokens 分别为 30000/24000，paired reduction=20%；
- 61/62 calls 已使用时，smoke 在 Provider call 前硬停止；
- full 阶段重复执行幂等。

上述 fake token 数值只用于验证 runner 算法，不是 Prompt v0.2 的实验结果。

## 3. 验证结果

| 检查 | 结果 |
|---|---|
| B2 专项测试 | 32 passed，real socket attempts=0 |
| 全量离线测试 | 372 passed，1 skipped，1 既有弃用 warning，real socket attempts=0 |
| 迁移测试 | 3 passed，real socket attempts=0 |
| compileall | passed |
| `git diff --check` | passed；仅有工作区既有 LF/CRLF 提示 |
| 新文件 whitespace 检查 | 11 files passed；验证报告加入后再次复核 |
| 冻结资产 SHA-256 | 129/129 passed，missing=0，changed=0 |
| run4 检查 | 不存在 |
| 项目报告区 readiness ledger | 不存在 |

全量测试日志 SHA-256：`9a07c10f737ef7ca34916863ebb197d73493487f3dab09a5338a9afe0082ab49`。保护基线 SHA-256：`d2a0b5c5d2b84d78fe406edb2e170744f312812f1e1f1359a9a8063bcd0f84bc`。

## 4. 交付状态

readiness runner/CLI、protocol v2 A/B runner/CLI、Spec、Plan、Tasks、Risk Analysis 和完整命令说明均已完成。生产 `PrepPackageService` 仍实例化 `QuestionBankAgent`，Prompt/Schema/metadata/Provider 参数及历史实验资产保持不变。

本阶段停止在离线就绪状态。真实 readiness、smoke、pilot、full 和独立盲评均未开始，等待后续明确授权。
