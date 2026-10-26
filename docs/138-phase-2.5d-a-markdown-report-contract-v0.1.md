# Phase 2.5D-A Markdown Report and Prep Manual Contract v0.1

## 1. 决策

Markdown 报告和备战要点手册保留为 MVP 收口项。二者必须从已持久化的 MatchReport、priority plan、question metadata、recommended questions 和 action items 确定性组装，不新增 LLM 调用，不创建新 Prompt。

PRD v0.2 将可下载 Markdown/PDF 留作待确认，而更具体的第一阶段 Feature Spec 和 Development Roadmap 已把 Markdown 定为 MVP。Phase 2.5D-A 采用后者；PDF 继续 deferred。

## 2. 数据来源

renderer 只允许读取：

1. InterviewPrepPackage 的 title、overview、priority plan、action items、package version。
2. 最新且与 package 关联的 MatchReport。
3. ResumeProfile/JDProfile 的已持久化结构化字段和安全 evidence refs。
4. 关联 ExperienceProfile 的结构化摘要。
5. 25 道 InterviewQuestion 及其 metadata。
6. RecommendedQuestion 的 rank、reason、related weaknesses。
7. 对应 AgentRun 的 execution mode 和受控 fallback/degradation 信息。

禁止读取或写入 Prompt、CoT、reasoning content、原始 Provider response、原始异常正文、API key。报告生成 Provider calls 必须为 0。

## 3. 稳定章节顺序

Markdown 必须严格使用以下顺序和固定一级/二级标题：

1. 备战总览
2. JD 核心要求
3. 匹配优势
4. 能力缺口与风险
5. 简历改进建议
6. 准备优先级
7. 8/8/9 题库
8. 推荐先练题与准备建议
9. 行动清单

备战要点手册内容并入第 8 节的独立子节：回答加分点、回答雷点、简历细节、现场话术节奏、反问环节。这样保留用户要求的九个顶层章节，同时明确手册的产品位置。

每次渲染必须使用稳定排序：rank、priority 映射、module 顺序 `self_intro/professional/behavior_project`、sort_order、稳定 ID。禁止依赖数据库未排序返回。

## 4. 备战要点手册确定性组装

### 4.1 回答加分点候选来源

按以下优先级生成并去重：

1. MatchReport matched strengths 与 evidence。
2. resume suggestions 中有 evidence 的推荐表达。
3. recommended questions 的 preparation advice。
4. question answer framework 与 scoring anchors 中可执行的正向要求。
5. priority plan 与 action item 的具体动作。

每条包含：推荐表达、岗位匹配点、可量化表达方式、对应经历位置或 evidence summary。renderer 只能套用固定句式重排已有事实，不增加新经历、技术或指标。

### 4.2 回答雷点候选来源

按以下优先级生成并去重：

1. MatchReport risk points。
2. expression issues。
3. missing capabilities 中与回答风险有关的项。
4. question scoring anchors 中明确的失败边界。
5. source/evidence 不足时的安全提示。

每条包含禁忌表述类别、可能影响和基于现有数据的替代表达。不得根据一般常识伪造候选人的缺点。

### 4.3 数量与完整性

Feature Spec 要求至少 8 条加分点和 6 条雷点。生成器必须去重后计数：

- 达到要求：`manual_completeness=complete`。
- 来源不足：`manual_completeness=incomplete_source_data`，列出缺失数量；不得复制、改写同一条来凑数。

来源不足不应触发新的 LLM 调用。是否允许 incomplete manual 作为 `outcome_mode=degraded` 的完整包结果，应在 Phase 2.5D-B preregister；推荐使用 degraded 成功结果并在 UI/报告显著说明，而不是编造内容或标成系统 failure。

## 5. Renderer 合同

renderer 输入是版本化、不可变的 `ReportSourceSnapshot`：

```json
{
  "renderer_version": "prep-markdown-v0.1",
  "prep_package_id": "uuid",
  "package_version": "v0.1",
  "source_resource_versions": {},
  "source_quality": "trusted",
  "outcome_mode": "standard"
}
```

完整 snapshot 只在服务端内存中构造；持久化其 canonical JSON SHA-256，不必复制全部业务正文到 report record。相同 source snapshot 和 renderer version 必须产生逐字节相同的 UTF-8、LF、末尾单换行 Markdown。

用户提供的文本按 Markdown text escaping 规则处理；Web 查看时关闭 raw HTML，并对链接 scheme 做 allowlist。不得把用户文本直接插入 HTML。

## 6. Content hash 与幂等

定义：

- `source_snapshot_sha256 = SHA256(canonical source refs + resource versions + renderer version)`
- `content_sha256 = SHA256(rendered UTF-8 bytes)`

建议增加 report artifact record：

- report ID
- prep package ID
- format=`markdown`
- renderer version
- source snapshot hash
- content hash
- rendered markdown
- safe storage key
- source quality/outcome mode
- created/updated timestamps

对 `(prep_package_id, format, renderer_version, source_snapshot_sha256)` 建唯一约束。重复 materialize 返回已有 artifact；来源变化或 renderer version 变化创建新 artifact。已有 artifact 内容不可原地篡改。

## 7. rendered_markdown 回写策略

`interview_prep_packages.rendered_markdown` 已存在。Phase 2.5D-B 推荐：

1. report artifact 是版本化事实源。
2. 成功 materialize 后，在同一数据库事务将最新 artifact 的内容回写到 `rendered_markdown`，作为现有字段的兼容缓存。
3. 写入失败则 artifact 和兼容缓存均不提交。
4. 下载依据 artifact ID/content hash，不依据文件系统路径。
5. 重新生成仅因 source snapshot 或 renderer version 变化；用户重复点击不生成不同内容。

这取代旧任务文档“每次导出生成不同时间戳文件”的做法。该旧做法与当前幂等要求冲突，标记为被本合同替代，不回写历史文档。

## 8. 文件名与原子写入

内部安全文件名只使用 ASCII、UUID 和 hash：

```text
prep-package-{prep_package_id}-{content_hash_prefix}.md
```

禁止将用户姓名、岗位名或自由文本直接放入文件名。写入流程：

1. 确认 resolved target 位于配置的 report root。
2. 在同目录写入随机临时文件。
3. flush/fsync。
4. 使用 atomic replace 移动到 content-addressed target。
5. 数据库只保存相对 storage key，不保存或返回绝对路径。
6. 异常时清理临时文件；已有同 hash 文件保持不变。

文件系统副本是下载缓存，不是唯一事实源。数据库 artifact 内容与 hash 必须可重新生成文件。

## 9. Proposed API

这些 endpoint 只在 Phase 2.5D-B 获得授权后实现：

### 9.1 Materialize

```http
POST /api/v1/prep-packages/{prep_package_id}/reports/markdown
Idempotency-Key: <key>
```

本地确定性执行，返回 201（新 artifact）或 200（幂等命中），不调用 Provider。

```json
{
  "data": {
    "report_id": "uuid",
    "prep_package_id": "uuid",
    "renderer_version": "prep-markdown-v0.1",
    "content_sha256": "hex",
    "source_snapshot_sha256": "hex",
    "outcome_mode": "standard",
    "source_quality": "trusted",
    "manual_completeness": "complete",
    "view_href": "/api/v1/prep-packages/{id}/reports/markdown",
    "download_href": "/api/v1/prep-packages/{id}/reports/markdown/download"
  },
  "meta": {"request_id": "safe-request-id"}
}
```

### 9.2 View

```http
GET /api/v1/prep-packages/{prep_package_id}/reports/markdown
```

返回 JSON metadata 和 `rendered_markdown`，供前端安全 Markdown viewer 使用。若 artifact 不存在，返回 404，不在 GET 中隐式生成。

### 9.3 Download

```http
GET /api/v1/prep-packages/{prep_package_id}/reports/markdown/download
```

Response：

- `Content-Type: text/markdown; charset=utf-8`
- `Content-Disposition: attachment; filename="prep-package-{uuid}.md"`
- `ETag: "{content_sha256}"`
- 可选 `Content-Digest` 使用标准 SHA-256 表达
- body 为精确的 Markdown bytes

不得返回 `report_path`、绝对路径或内部 storage key。

不向客户端返回服务端绝对路径；客户端只接收同源 API link、report ID 和 content hash。

## 10. 来源质量说明

报告头部必须出现“生成来源”块：

- standard/trusted：说明从已持久化分析和题库确定性生成。
- fallback：列出受控 fallback source 名称和用户可理解原因。
- degraded：说明哪些章节数据不完整、哪些分数不可用。

报告不得把 degraded 分数写成 0，不得隐藏 `score_available=false`，不得把 fallback 内容描述为真实 Provider 结论。来源说明同样进入机器可读 metadata。

## 11. 访问和敏感数据边界

1. 当前默认用户/无认证模式下，报告 endpoint 只允许本机或受控私有演示。
2. 公网启用前必须校验 authenticated user 对 prep package/report 的 ownership。
3. 响应和日志不记录完整报告正文；日志只记录 report ID、hash、字节数、renderer version 和 request ID。
4. 浏览器不得把完整报告、简历、JD 或回答写入 localStorage。
5. 报告不得包含 Prompt、CoT、Provider 原始响应、原始异常或密钥。

## 12. 前端合同

前端提供：

1. 备战包详情中的“查看 Markdown 报告”。
2. 显式“生成/刷新报告”mutation，不自动 POST。
3. “下载 .md”使用同源 download endpoint。
4. source quality、outcome mode、manual completeness 和 degradation reasons 的可见说明。
5. raw HTML disabled 的 Markdown 渲染；外部链接明确标识并使用安全 rel。

## 13. 不采用的方案

- 不新建 Prep Manual LLM Prompt。
- 不在每次下载时调用 Agent。
- 不用字符长度或报告存在性代替内容完整性。
- 不因来源不足而复制条目凑够 8/6。
- 不返回服务器绝对文件路径。
