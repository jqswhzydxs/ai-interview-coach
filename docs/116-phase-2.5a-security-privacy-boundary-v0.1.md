# Phase 2.5A Security and Privacy Boundary v0.1

## 浏览器禁止边界

- API key、Provider credential 和服务端 secret 永远不得进入 bundle、环境注入、网络请求参数或浏览器日志。
- 不展示或持久化完整 Prompt、reasoning content、CoT、原始 Provider response 或不受控异常正文。
- `localStorage`、`sessionStorage` 和 IndexedDB 不保存完整简历、JD、面经、用户答案或改进答案。
- Mock 与测试只能使用合成、非个人数据和固定虚构 UUID。

## 敏感表单生命周期

- 未提交内容默认只存在组件内存；是否使用短期内存 store 在 Phase 2.5B 决定。
- 页面刷新、关闭标签页或离开有未提交敏感内容的路由时显示明确提示。
- 用户确认离开后清理内存草稿、文件对象 URL、上传队列和错误上下文。
- 成功提交后清理原始文件句柄与粘贴缓冲；只保留后端返回 ID 和必要展示摘要。
- 请求取消或超时后允许在当前会话继续编辑，但不自动持久化到浏览器存储。

## 日志白名单

前端遥测最多允许：

- event name、route pattern、UI state；
- request ID、资源类型、非内容型实体 ID；
- HTTP status、后端 error code、白名单 failure category；
- latency bucket、retry count、payload byte-size bucket；
- `evaluation_mode`、`score_available`、`source_quality`、`execution_mode`；
- 题目模块和匿名计数。

禁止记录表单正文、文件名中的个人信息、question text、answer text、评价正文、fallback 原始异常、Provider/model 原始 response、Authorization header 和 URL 查询中的敏感内容。

## 上传边界

- 支持的类型由后端合同决定；当前 Mock 展示 `pdf/docx/txt` 仅用于错误交互示例，不构成生产限制冻结。
- 文件大小上限等待后端明确后再做客户端预校验；服务端仍是最终裁决者。
- 错误文案说明允许类型、大小和恢复动作，不回显文件内容。
- 上传控件必须允许移除、取消和重新选择，失败文件不进入后续步骤。

## 降级与错误展示

- `fallback_reason` 通过白名单 code 映射为用户文案；未知 code 使用通用安全文案和 request ID。
- 原始异常、堆栈、Provider code/message 不进入 ErrorBoundary。
- degraded 评价不写入长期记忆，并通过 NoScoreState 表达不可评分；不得用 0 分替代 null。
- 客户端不能自行把 fallback 结果提升为 standard。

