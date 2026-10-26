# Phase 2.4D-C 离线验证报告

验证日期：2026-10-22（Asia/Singapore）。本阶段未访问真实 Provider，未执行 Full、blind review 或 finalize，未创建 run4，未创建 Prompt v0.3。

## 1. 功能验证

新增离线分析器从冻结 ab1 提取 3 个 pair 的 successful-response usage、可见字符、延迟、retry、billing completeness 和 reliability。测试确认：

- baseline output tokens 为 9,271，candidate 为 10,197；
- baseline/candidate 平均 output tokens 分别为 3,090.33/3,399；
- 可见题目平均字符分别为 139.04/57.88；
- output token 变化为 +9.988%，可见字符变化为 -58.372%；
- output tokens / 可见字符密度为 baseline 的 2.642 倍；
- Java candidate final successful-response usage 与失败 timeout attempt 的 billing unknown 保持分离；
- 提前停止状态为 `stopped_for_engineering_futility`，正式最终门禁为 `not_evaluable`；
- v0.2 不晋升，Full/盲评/finalize 均未执行。

usage-details 解析测试确认：只提取白名单非负整数；缺失、bool、负数和其他非法值保持 unknown/unsupported；不复制正文或未知字段；不把缺失记为 0；不通过减法推算 visible tokens。历史 ab1 的 reasoning、visible completion 和 cached/input details 均保持 unknown。

## 2. 验证结果

| 检查 | 结果 |
|---|---|
| D-C 新增专项测试 | 11 passed，real socket attempts=0 |
| D-C + B/B2 专项回归 | 43 passed，real socket attempts=0 |
| 全量离线测试 | 383 passed，1 skipped，1 既有弃用 warning，real socket attempts=0 |
| 迁移测试 | 3 passed，real socket attempts=0 |
| compileall | passed |
| `git diff --check` | passed；使用当前工作区临时 safe-directory 参数，只有既有 LF/CRLF 提示 |
| 新交付文件 whitespace 检查 | passed |
| 冻结资产 SHA-256 | 145/145 passed，missing=0，changed=0 |
| ab1 状态 | `pilot_passed / completion_status=not_started`，未改写 |
| readiness ledger | 哈希一致，未改写 |
| run4 | 不存在 |

保护基线 SHA-256：`57425b704a132ae60ede13f7c077b3099174dbf2f45a5b53a39498cdcd58a7f3`。

## 3. 安全与冻结检查

输出目录不保存请求正文、问题正文、原始响应、异常消息或凭据。分析器拒绝把输出写入 ab1 或 readiness 目录。生产 `PrepPackageService` 仍引用原 `QuestionBankAgent`，Prompt v0.1/v0.2、Schema、metadata v2、fixtures、模型和生成参数均与实施前哈希一致。

机器可读验证记录见 `storage/reports/question-bank-token-phase-2-4d-c-offline-20261022/offline-validation-report.json`。

## 4. 阶段状态

Phase 2.4D-C 已完成并停止。ab1 不再继续 Full；下一阶段只建议设计新的 reasoning-control 单变量协议，且必须先证明当前 Provider/model 的参数支持。任何新协议不得混用当前 Prompt-only 数据。
