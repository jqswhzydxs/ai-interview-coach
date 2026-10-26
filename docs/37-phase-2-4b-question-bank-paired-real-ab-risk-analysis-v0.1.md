# Phase 2.4B：QuestionBank 配对式真实 A/B 风险分析 v0.1

## 1. 全链路混杂

风险：重新运行七 Agent 链路会让上游波动改变 QuestionBank 输入，无法归因。

控制：专用 runner 只加载冻结结构化文件并实例化两个 QuestionBank Agent；fake-provider 测试断言请求 Schema 只能是 smoke、QuestionBank、QuestionDraftBank。

## 2. 时间窗口偏差

风险：先跑完 baseline 再跑 candidate，provider 状态变化会伪装成候选收益。

控制：每个 case 内配对，奇偶 pair 交替先后顺序，记录实际 sequence 和时间。

## 3. pilot 额外消耗或样本重复

风险：pilot 之后重新从第 1 对开始，导致超过 15+15 或选择性丢弃 pilot。

控制：pilot 就是正式 pair 1，full 只执行 pair 2–5，manifest 对 `(case,pair,variant)` 去重。

## 4. 超时后的幽灵调用

风险：外层命令超时但 asyncio/http 请求仍在后台继续，重复启动会产生额外费用和污染窗口。

控制：不使用 `create_task`；绝对截止取消当前 await 链。测试使用 hanging provider 证明取消进入 provider finally、没有新增 pending task、lock 已释放。

## 5. 并发进程

风险：两个验收进程同时运行，破坏配对顺序和预算。

控制：项目级 lock 原子独占创建，包含 PID、phase 和 run_dir。异常硬终止可能保留 stale lock；只能在人工确认 PID 不存在后处理，不能自动抢锁。

## 6. 预算不可证明

风险：失败响应没有 usage，或成功响应缺 usage，使 token 预算不可靠。

控制：所有真实 call 在发出前计数。成功响应缺 total usage 时停止；无响应失败调用单独记为 missing usage，并由 provider call 上限限制最坏调用数。

## 7. 运行资产漂移

风险：实验中修改 Prompt/Schema/Agent/assembler，导致不同 pair 使用不同版本。

控制：smoke 前记录 hash，每次执行前后复核；变化后状态为 `invalidated_assets`，不允许继续。

## 8. fallback 隐藏

风险：最终 QuestionBank 合法就被当作 real success。

控制：主报告单独记录 execution_mode、calls、retry、failure type 和 assembler_passed；质量同时给出 real-only 与包含 fallback 的 user-visible 结果。

## 9. 非盲人工评分

风险：知道 variant 后按预期打分。

控制：问题与 metadata 包只暴露随机 submission id 和 case，不含 variant/pair/order；评分文件完成后才与主报告映射解盲。

## 10. 自动规则覆盖不足

风险：技术别名表与高相似度阈值可能漏掉语义串栈或改写重复。

控制：自动门禁与人工“技术正确性/边界”和“覆盖/多样性”评分并用；最终报告保留这一残余风险。

