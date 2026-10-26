# Phase 2.5A Frontend Information Architecture v0.1

## 导航层级

一级导航保持三个入口：`准备任务`、`练习历史`、`系统状态`。创建流程在任务上下文内逐步展开；Agent 详情是辅助深链，不占主要导航位置。

| Route | 页面/用途 | 主返回行为 | 深链与空状态 |
|---|---|---|---|
| `/` | 首页与最近任务入口 | 浏览器返回遵循历史 | 无任务时提供“创建准备任务” |
| `/prep/new` | 创建流程总入口 | 返回首页前提示未保存输入 | 恢复当前会话内草稿 |
| `/prep/new/resume` | 上传或粘贴简历 | 返回创建入口；保留本次会话输入 | 上传失败时仍留在本页 |
| `/prep/new/job` | JD 录入 | 返回简历步骤 | 无简历 ID 时重定向到 resume |
| `/prep/new/experience` | 可选面经录入 | 返回 JD 步骤 | 可跳过；解析失败允许移除 |
| `/prep/new/review` | 检查并提交 | 返回上一有效步骤 | 缺字段时聚焦第一个错误 |
| `/prep/:prepId/status` | 生成进度 | 返回 review 或首页 | 可用 `agentRunId` 深链运行详情 |
| `/prep/:prepId/summary` | 匹配摘要与准备重点 | 返回最近任务列表 | 未 ready 时跳到 status |
| `/prep/:prepId/questions` | 8/8/9 题库与筛选 | 返回 summary | query 保存 module/difficulty；无结果提供清除筛选 |
| `/prep/:prepId/questions/:questionId/practice` | 单题作答 | 返回时保存会话草稿并提示 | question ID 无效时回题库并提示 |
| `/evaluations/:evaluationId` | 单次评价结果 | 返回原练习题或历史 | standard/degraded 可直接深链 |
| `/history/evaluations` | 历史评价 | 返回首页 | 空历史提供进入题库练习 |
| `/agent-runs/:agentRunId` | Agent 运行与降级详情 | 返回来源页面；无历史则首页 | pending/running 可刷新或轮询；404 提供返回任务 |

## 创建流程

`首页 → 简历 → JD → 可选面经 → 检查提交 → 生成进度 → 摘要 → 题库 → 单题练习 → 评价`

- Stepper 始终显示当前步骤、已完成步骤和可返回步骤。
- 已生成的后端 ID 写入内存态；本阶段不规定浏览器持久化实现。
- 用户主动返回时保留会话内未提交输入；刷新或离开敏感表单按安全文档处理。
- 直接访问深链时先加载必要资源；缺少父资源时显示局部错误，避免整站崩溃。

## 题库与评价

- 题库按 `self_intro`、`professional`、`behavior_project` 三组显示 8/8/9 计数。
- 过滤条件进入 URL query，题目顺序使用后端 `sort_order`，不在客户端重排稳定 ID。
- 评价默认显示 `source_quality`、`evaluation_mode` 和 `score_available`。
- `score_available=false` 时以 NoScoreState 替换所有数字分数，并提供继续使用降级反馈或重新练习的动作。

