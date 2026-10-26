# Phase 2.5B Accessibility Validation v0.1

- AppShell 提供“跳到主内容”链接和语义化 header/nav/main。
- 所有表单有可见 label；字段错误通过 `aria-describedby` 关联，错误摘要使用 `role=alert`。
- ProcessingStatus 使用 `role=status`、`aria-live=polite`；错误恢复使用 `role=alert`。
- 移动导航支持 Escape 关闭并恢复焦点；题库 tabs 支持左右方向键。
- 文件上传可由 label/键盘打开，不依赖拖放。
- 交互目标最小 44×44px；焦点环 3px；状态同时使用文字、图标与颜色。
- 正文为 16px/1.6，系统/Noto Sans SC 字体栈，无远程字体。
- 375/768/1024/1440 布局规则和 `prefers-reduced-motion` 已写入 CSS。
- 首页、创建页和 degraded 评价页通过 axe serious/critical 自动检查。

剩余工作是 Phase 2.5C 真实浏览器矩阵与缩放/高对比模式的人工验收。
