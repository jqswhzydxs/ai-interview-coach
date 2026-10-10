# API 设计 v0.1

## 1. 设计目标

第一版 API 服务两个核心工作流：

1. 生成完整面试备战包。
2. 提交单题回答并获得评分。

API 设计优先保证业务闭环清楚，不追求一开始就覆盖完整用户系统。

## 2. 通用约定

### 2.1 基础路径

```text
/api/v1
```

### 2.2 默认用户

第一版不做登录注册，后端使用默认用户。

请求中可以暂时不传 `user_id`，由服务端读取默认用户配置。

### 2.3 响应格式

推荐统一格式：

```json
{
  "data": {},
  "message": "ok",
  "request_id": "optional-request-id"
}
```

错误格式：

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid input",
    "details": {}
  }
}
```

## 3. 材料接口

### 3.1 上传文件材料

```text
POST /api/v1/documents/upload
```

用途：

上传 PDF、DOCX、Markdown 文件，提取文本并保存到 `source_documents`。

请求：

```text
multipart/form-data
file: binary
document_type: resume | jd | interview_experience
```

响应：

```json
{
  "data": {
    "source_document_id": "uuid",
    "document_type": "resume",
    "input_type": "pdf",
    "original_filename": "resume.pdf",
    "text_length": 12345
  }
}
```

### 3.2 粘贴文本材料

```text
POST /api/v1/documents/text
```

用途：

保存用户粘贴的 JD、面经、Markdown 或纯文本简历。

请求：

```json
{
  "document_type": "jd",
  "input_type": "text",
  "title": "后端开发实习 JD",
  "raw_text": "..."
}
```

响应：

```json
{
  "data": {
    "source_document_id": "uuid",
    "text_length": 5000
  }
}
```

## 4. 简历接口

### 4.1 创建简历记录

```text
POST /api/v1/resumes
```

请求：

```json
{
  "source_document_id": "uuid",
  "title": "后端实习简历 v1",
  "target_direction": "backend",
  "version_label": "v1"
}
```

响应：

```json
{
  "data": {
    "resume_id": "uuid",
    "status": "created"
  }
}
```

### 4.2 解析简历

```text
POST /api/v1/resumes/{resume_id}/parse
```

用途：

调用 Resume Analyzer Agent 生成 `ResumeProfile`。

响应：

```json
{
  "data": {
    "resume_profile_id": "uuid",
    "agent_run_id": "uuid",
    "profile": {}
  }
}
```

## 5. JD 接口

### 5.1 创建 JD

```text
POST /api/v1/jobs
```

请求：

```json
{
  "title": "后端开发实习生",
  "company_name": "示例公司",
  "raw_text": "...",
  "target_direction": "backend"
}
```

响应：

```json
{
  "data": {
    "job_description_id": "uuid"
  }
}
```

### 5.2 解析 JD

```text
POST /api/v1/jobs/{job_description_id}/parse
```

响应：

```json
{
  "data": {
    "jd_profile_id": "uuid",
    "agent_run_id": "uuid",
    "profile": {}
  }
}
```

## 6. 面经接口

### 6.1 创建面经

```text
POST /api/v1/experiences
```

请求：

```json
{
  "title": "某厂后端一面面经",
  "experience_type": "online_shared",
  "company_name": "某厂",
  "role_name": "后端开发",
  "raw_text": "..."
}
```

响应：

```json
{
  "data": {
    "interview_experience_id": "uuid"
  }
}
```

### 6.2 解析面经

```text
POST /api/v1/experiences/{interview_experience_id}/parse
```

响应：

```json
{
  "data": {
    "experience_profile_id": "uuid",
    "agent_run_id": "uuid",
    "profile": {}
  }
}
```

## 7. 完整面试备战包接口

### 7.1 生成备战包

```text
POST /api/v1/prep-packages
```

请求：

```json
{
  "resume_id": "uuid",
  "job_description_id": "uuid",
  "interview_experience_ids": ["uuid"],
  "title": "某公司后端实习备战包"
}
```

响应：

```json
{
  "data": {
    "prep_package_id": "uuid",
    "agent_run_id": "uuid",
    "status": "ready"
  }
}
```

第一版可以同步返回结果；如果生成耗时较长，后续改成异步任务。

### 7.2 查询备战包详情

```text
GET /api/v1/prep-packages/{prep_package_id}
```

响应包含：

1. 备战总览。
2. JD 拆解。
3. 差距分析。
4. 简历优化建议。
5. 面试准备优先级。
6. 题库。
7. 手册。
8. 推荐先练的 3 道题。
9. 下一步行动清单。

### 7.3 查询题库

```text
GET /api/v1/prep-packages/{prep_package_id}/questions
```

可选 query：

```text
module=self_intro | professional | behavior_project
difficulty=basic | medium | hard
```

### 7.4 导出 Markdown 报告

```text
POST /api/v1/prep-packages/{prep_package_id}/export/markdown
```

响应：

```json
{
  "data": {
    "report_path": "storage/reports/xxx.md",
    "markdown": "..."
  }
}
```

## 8. 单题模拟回答评分接口

### 8.1 提交单题回答

```text
POST /api/v1/evaluations
```

请求：

```json
{
  "prep_package_id": "uuid",
  "question_db_id": "uuid",
  "user_answer": "我的回答是..."
}
```

也支持手动题目：

```json
{
  "custom_question_text": "请介绍你项目中的数据库设计",
  "user_answer": "我的回答是..."
}
```

响应：

```json
{
  "data": {
    "answer_evaluation_id": "uuid",
    "total_score": 82,
    "evaluation": {}
  }
}
```

### 8.2 查询评分详情

```text
GET /api/v1/evaluations/{answer_evaluation_id}
```

### 8.3 查询历史评分

```text
GET /api/v1/evaluations
```

可选 query：

```text
prep_package_id=uuid
question_db_id=uuid
```

## 9. Agent 运行日志接口

### 9.1 查询运行详情

```text
GET /api/v1/agent-runs/{agent_run_id}
```

用途：

调试和展示 Agent 工作流过程。

响应包含：

1. run_type。
2. status。
3. prompt_version。
4. steps。
5. error_message。

## 10. 第一版 API 边界

第一版不做：

1. 登录注册接口。
2. 删除账号。
3. 在线支付。
4. 自动联网搜索面经。
5. 真实语音上传转写。
6. PDF 导出。

