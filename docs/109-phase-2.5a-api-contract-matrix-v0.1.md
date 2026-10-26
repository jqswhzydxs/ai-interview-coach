# Phase 2.5A API Contract Matrix v0.1

## 快照

- OpenAPI operation：16
- 规范化快照：`contracts/frontend/phase-2.5a-v0.1/openapi.json`
- SHA-256：`e983971aec77ddaf246efbb80637134f4fd41bfb9302fa2f3d06122430977304`
- 成功 envelope：`{data, message, request_id}`
- 失败 envelope：`{error: {code, message, details}}`

当前 OpenAPI 对大多数成功 response 只声明 generic object。下表的 response data 来自当前服务序列化行为；这是现状记录，不是后端改动。

## 端点矩阵

| Method / Path | Request | Response data | Nullable | 异步/Loading | 失败状态 | 降级字段与展示 |
|---|---|---|---|---|---|---|
| `GET /health` | 无 | `status, app_name, environment` | 无 | immediate | 通用 5xx | 应用可用性与刷新动作 |
| `POST /documents/text` | `TextDocumentCreate` | 文档 ID、类型、hash、metadata、时间 | `metadata, original_filename, file_path` | submitting | 422 | 字段附近显示错误；禁止重复提交 |
| `POST /documents/upload` | multipart `document_type, file` | 同文本文档 | filename/file_path 依输入 | uploading | 422 | 进度、取消、类型/大小错误 |
| `POST /resumes` | `ResumeCreate` | resume/document IDs、标题、方向、版本、时间 | `target_direction, version_label` | submitting | 404/422 | 保存 ID 后进入解析 |
| `POST /resumes/{resume_id}/parse` | UUID path | resume/profile/agent-run IDs | 无 | processing | 404/422/502 | 展示步骤并可深链 Agent run |
| `POST /jobs` | `JobDescriptionCreate` | job/document IDs、标题、公司、URL、方向、时间 | `company_name, job_url` | submitting | 404/422 | 保存 ID 后进入解析 |
| `POST /jobs/{job_description_id}/parse` | UUID path | job/profile/agent-run IDs | 无 | processing | 404/422/502 | 展示步骤并可深链 Agent run |
| `POST /experiences` | `ExperienceCreate` | experience/document IDs、标题、类型、公司、角色、时间 | `company_name, role_name` | submitting | 404/422 | 可选步骤；允许跳过 |
| `POST /experiences/{interview_experience_id}/parse` | UUID path | experience/profile/agent-run IDs | 无 | processing | 404/422/502 | 展示步骤并可深链 Agent run |
| `POST /prep-packages` | `PrepPackageCreate` | prep-package/agent-run IDs、status | `title` | processing | 404/422/502 | 多步骤进度；完成后进入摘要 |
| `GET /prep-packages/{prep_package_id}` | UUID path | ID、title、status、overview、题目/推荐计数、时间 | `title` | loading | 404/422 | 摘要、空状态与刷新 |
| `GET /prep-packages/{prep_package_id}/questions` | UUID path；可选 module/difficulty | `total, items[]`，item 为最终 QuestionBank 字段加 DB ID | 无 | loading | 404/422 | 8/8/9 tabs、筛选、稳定顺序 |
| `POST /evaluations` | `EvaluationCreate` | evaluation/run IDs、mode、score availability、source quality、reasons、score | question/custom text 二选一；`total_score` 可空 | processing | 404/422/502 | 标准/降级分支；null 不得显示为 0 |
| `GET /evaluations` | `limit, offset` | `total, items[]` 评价摘要 | package/run/score 可空 | loading | 422 | 历史、分页、空状态 |
| `GET /evaluations/{answer_evaluation_id}` | UUID path | 摘要、回答、改进、memory update、完整 evaluation | package/question/custom/run/score 可空 | loading | 404/422 | Badge、分数或 NoScoreState、记忆写入状态 |
| `GET /agent-runs/{agent_run_id}` | UUID path | 状态、模式、Provider、重试、Token、fallback、步骤 | model/prompt/latency/token/fallback/error/finished 可空 | pollable | 404/422 | execution mode、结构化原因、步骤和重试 |

## standard / degraded / fallback 映射

- `standard`：`evaluation_mode=standard`、`score_available=true`、数值分数和非空维度分。
- `degraded`：`evaluation_mode=degraded`、`score_available=false`、`total_score=null`、`dimension_scores=[]`，并提供 `degradation_reasons`。
- `fallback`：Agent run 的 `execution_mode=fallback` 且 `fallback_reason` 非空。评价若受影响，应同时进入 degraded 合同。
- `memory-write blocked`：界面只根据可观察的 `memory_update.write_decision=skip` 显示未写入；不得声称已观察到未暴露的内部 guard 分支。

## 缺口 proposals

1. prep-package/question-bank 读取目前不直接返回 `source_quality`；fallback 可从 Agent run 的 `execution_mode` 与 `fallback_reason` 看见，但不能伪造同名字段。
2. response model、统一错误响应、上传限制和异步轮询策略应在后端兼容版本中正式进入 OpenAPI。

机器可读矩阵位于 `contracts/frontend/phase-2.5a-v0.1/api-contract-matrix.json`。

