# Phase 2.5A Design System v0.1

## 设计方向

界面采用专业、可信、内容优先的 Flat Design，以轻量阴影和分层 surface 建立 Soft UI 层次。视觉层次服务于长文本阅读、步骤进度和降级状态判断；不使用赛博朋克、重渐变、玻璃拟态或装饰性动画。

`ui-ux-pro-max` 的可访问性、触控、响应式和反馈优先规则被采用。其自动检索给出的紫/粉 AI 营销色、远程字体和夸张标题不符合本项目约束，因此未纳入本系统。

## Semantic color tokens

| Token | Light value | 用途 |
|---|---:|---|
| `color.primary` | `#1D4ED8` | 主操作、选中状态 |
| `color.onPrimary` | `#FFFFFF` | 主色上的文字/图标 |
| `color.surface.canvas` | `#F8FAFC` | 页面底色 |
| `color.surface.default` | `#FFFFFF` | 内容面板 |
| `color.surface.raised` | `#FFFFFF` | 浮层；配合边框与轻阴影 |
| `color.text.primary` | `#0F172A` | 正文与标题 |
| `color.text.muted` | `#475569` | 次要说明 |
| `color.border.default` | `#CBD5E1` | 控件与分隔线 |
| `color.success.fg` | `#166534` | 成功状态文字 |
| `color.success.bg` | `#F0FDF4` | 成功状态底色 |
| `color.warning.fg` | `#92400E` | 警告文字 |
| `color.warning.bg` | `#FFFBEB` | 警告底色 |
| `color.danger.fg` | `#B91C1C` | 错误与危险动作 |
| `color.danger.bg` | `#FEF2F2` | 错误底色 |
| `color.degraded.fg` | `#5B21B6` | 降级状态文字 |
| `color.degraded.bg` | `#F5F3FF` | 降级状态底色 |
| `color.focusRing` | `#2563EB` | 3px 可见焦点环 |

正文与 surface 的对比度必须至少 4.5:1。degraded 同时使用信息图标、标题“降级结果”和原因文案，不依赖黄色或单一色彩。

## Typography

- 字体栈：`system-ui, -apple-system, "Segoe UI", "Noto Sans SC", "Microsoft YaHei", sans-serif`。
- 不加载阻塞渲染的远程字体。
- 正文 `16px/1.6`；辅助文字不低于 `14px/1.5`；表单输入不低于 16px。
- H1 `32px/1.25/700`，H2 `24px/1.35/650`，H3 `20px/1.4/600`。
- Token、ID 和日志白名单值使用系统等宽栈；不缩小到难以阅读。

## Spacing、shape 与 elevation

- spacing：`4, 8, 12, 16, 24, 32, 48, 64px`。
- radius：控件 8px、卡片 12px、badge 999px；避免过度圆润。
- border：默认 1px；焦点环 3px 并保留 2px offset。
- elevation：默认无阴影；raised 使用 `0 2px 8px rgb(15 23 42 / 0.08)`。
- 内容最大宽度 1200px；长文本阅读列建议 720–800px。

## Responsive acceptance

| 宽度 | 布局规则 |
|---:|---|
| 375px | 单列；底部或全宽主操作；tabs 可水平滚动但正文不横向滚动 |
| 768px | 单列内容加紧凑侧栏/抽屉；表单可两列分组 |
| 1024px | 持久侧栏；主内容与上下文面板两列 |
| 1440px | 内容保持最大宽度；增加留白，不无限拉长行宽 |

所有断点都必须保持 44×44px 最小点击目标、浏览器缩放能力和键盘顺序。不能通过隐藏核心信息解决窄屏问题。

## Motion 与图标

- 状态反馈 150–300ms，使用 opacity/transform；不动画 height/width 造成布局跳动。
- 动画只表达展开、状态改变或焦点转移。
- `prefers-reduced-motion: reduce` 下取消非必要过渡和位移。
- 使用同一 SVG outline 图标库；功能图标必须有可访问名称或配套可见文字。
- emoji 不充当按钮、导航或状态图标。

