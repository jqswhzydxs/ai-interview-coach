# Phase 2.5A Core Component Contracts v0.1

以下是实现无关的组件合同。props 名称用于表达数据边界，并不预设 React/Vue 语法。

| Component | 核心 props | 状态 | 可访问性与行为 |
|---|---|---|---|
| `AppShell` | `navigationItems, currentRoute, userMenu?, children` | default/mobile-nav-open | 跳到主内容链接；landmark；抽屉关闭后焦点回触发器 |
| `Stepper` | `steps, currentStepId, completedIds, onStepSelect?` | active/complete/error/disabled | 有序列表；`aria-current=step`；错误不只靠颜色 |
| `ResumeInput` / `JobInput` / `ExperienceInput` | `mode, value, errors, disabled, onChange, onSubmit` | idle/validating/submitting/error | 永久可见 label；错误通过 `aria-describedby` 绑定；Experience 可跳过 |
| `UploadDropzone` | `accept, maxSize?, file?, progress?, error?, onSelect, onCancel` | empty/dragging/uploading/success/error | 原生 file input 可键盘操作；44px 目标；不只支持拖放 |
| `ProcessingStatus` | `status, steps, currentStep?, startedAt?, agentRunHref?` | pending/running/success/degraded/error/cancelled | `aria-live=polite`；避免每次轮询重复播报 |
| `SourceQualityBadge` | `quality, sourceLabel?, derivedFrom?` | trusted/synthetic/degraded/user-provided/mixed/unknown | 文本完整；派生值标明来源；不只靠颜色 |
| `EvaluationModeBadge` | `mode` | standard/degraded | 显示“标准评价/降级评价”；与标题形成冗余提示 |
| `DegradationNotice` | `reasons, fallbackReason?, sourceQuality, actions` | info/blocking | `role=status` 或阻断时 `alert`；理由转为用户文案，禁止原始异常 |
| `ScoreCard` | `score, maxScore, scoreAvailable, label` | available/unavailable | unavailable 时不得渲染 0；应切换到 `NoScoreState` |
| `NoScoreState` | `reason, sourceQuality, actions` | degraded/unavailable | 固定主文案“本次无法提供可信分数”；含继续/重试动作 |
| `QuestionBankTabs` | `counts, activeModule, onChange` | 8/8/9/loading/empty | tablist/tab/tabpanel 语义；方向键切换；计数可读 |
| `QuestionCard` | `questionId, module, text, difficulty, sourceType, sortOrder, actions` | default/selected/degraded | 标题结构稳定；来源、难度和操作均有文字；稳定 ID 可深链 |
| `AnswerEditor` | `value, label, characterHint?, error?, disabled, onChange, onSubmit` | editing/submitting/error | textarea label；不自动丢失内容；离开时敏感数据提示 |
| `EvaluationDimensions` | `items, scoreAvailable` | standard/no-score | 表格或列表有名称、分值、上限和说明；无分数时完全隐藏数值列 |
| `RetryPanel` | `title, reason, retryable, onRetry?, onEdit?, agentRunHref?` | retryable/nonretryable | retryable 才显示重试；焦点进入面板标题；防重复提交 |
| `EmptyState` | `title, description, primaryAction?, secondaryAction?` | first-use/filter-empty/no-history | 使用可见图标加文字；筛选为空时提供清除筛选 |
| `ErrorBoundary` | `fallbackTitle, requestId?, resetAction, navigationAction` | caught | `role=alert`；不显示堆栈/原始异常；request ID 可复制 |
| `Skeleton` | `variant, count, labelledBy?` | loading | `aria-hidden=true`，容器另有“正在加载”；尺寸固定防 CLS |

## 跨组件不变量

- `score_available=false` 时，`ScoreCard` 与 `EvaluationDimensions` 不得接收或显示数字分数。
- fallback 页面必须同时出现 `SourceQualityBadge` 或明确的来源说明，以及 `DegradationNotice`。
- `ProcessingStatus` 的终态不能自行触发下一阶段请求。
- 所有异步主按钮在 submitting/processing 中防重复提交。
- 组件不得接收 API key、完整 Prompt、CoT、原始 Provider response 或未脱敏异常。
- 375/768/1024/1440px 均需验收；键盘路径必须覆盖所有操作。

