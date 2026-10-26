# Phase 2.4D-E-B Offline Validation Report

验证日期：2026-10-24（Asia/Singapore）。本阶段只执行离线读取、派生分析和测试；Provider calls=0，Full、盲评和 finalize 均未执行。

## 1. 隔离与保护

分析输出位于独立目录 `storage/reports/question-bank-token-phase-2-4d-e-b-offline-20261024`。实施前基线覆盖 56 个文件，包括 v4 readiness、ab1 全部文件、v4 代码/测试/文档、Prompt、Schema、metadata v2、fixtures、生产默认 Agent，以及 v3 冻结实验与最终分析。基线 SHA-256 为 `71db36d434c2a2ee37b4997ea85d0b189553e965009dedaa56b8685da3b784ee`。

分析器在读入和输出后重复计算来源 report/audit 哈希，并拒绝非 `pilot_passed`、Full 非 `not_started`、缺少 6 个 real-safe runs 或协议身份漂移的输入。派生文件不包含完整输入、原始响应、题目正文、凭据或未过滤异常正文。

## 2. 语义验证

专项场景验证了逐 pair input/output/total/reasoning tokens、延迟、长度、stack、retry 和 billing；Go 失败 attempt usage 保持 null；visible completion 保持 unknown；没有使用 output-reasoning 推算。提前停止记录明确区分 Pilot passed、正式门禁 not_evaluable 与非统计性工程停止。下一建议固定两侧 non-thinking，只让 Prompt v0.2/v0.3 变化，并明确禁止复用 v3/v4 数据和放宽质量门槛。

## 3. 验证结果

| 检查 | 结果 |
|---|---|
| E-B 专项分析测试 | 7 passed，real socket attempts=0 |
| 全量离线测试 | 450 passed，1 skipped，1 条既有弃用 warning，real socket attempts=0 |
| `git diff --check` | passed；仅有工作区既有 LF/CRLF 提示 |
| 新文件空白检查 | 7/7 passed，无尾随空白，均有末尾换行 |
| 派生 JSON 解析 | 4/4 passed（含保护基线） |
| 冻结资产 SHA-256 | 56/56 passed，missing=0，changed=0 |
| v4 原始状态 | report/manifest 均为 `pilot_passed`，Full `not_started`，review=null |
| Prompt v0.3 | 不存在 |

机器可读结果记录于同目录 `offline-validation-report.json`。当前输出仅为离线工程决策，不新增真实实验结论。
