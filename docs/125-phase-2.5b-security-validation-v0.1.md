# Phase 2.5B Security Validation v0.1

- `frontend/.env.example` 只包含 API base URL 和 Mock 开关，无 API key。
- 完整简历、JD、面经和回答只保存在内存，不使用 localStorage/sessionStorage/IndexedDB。
- 未提交敏感文本注册刷新与站内链接离开提醒，并在组件卸载时清理监听器。
- ApiError 不采用后端原始 message；UI 只显示安全本地文案、白名单 failure category 和 request ID。
- ErrorBoundary 不把异常或用户内容写到 console。
- UI 不展示 Prompt、CoT、reasoning_content、完整响应或堆栈。
- 12 个 fixture 标记为 `synthetic_non_personal`，合同检查拒绝 secret、Authorization、真实 PII 标记。
- MSW 未匹配请求失败，离线测试不能穿透真实网络。
- 上传 input 仅提供 `.pdf,.docx,.txt` 客户端提示；后端是类型和大小的最终校验者。
