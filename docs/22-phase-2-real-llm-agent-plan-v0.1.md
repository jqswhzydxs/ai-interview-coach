# Phase 2 Plan：真实 LLM Agent 接入 v0.1

## 1. 实施原则

1. Phase 1 的 mock 闭环优先保持稳定。
2. 真实 LLM 能力采用小步接入，先做 `QuestionBankAgent`。
3. 每一步都必须有 Pydantic 校验和降级路径。
4. 默认测试不依赖真实 API key。

## 2. 第一阶段：QuestionBankAgent 真实分支

实现内容：

1. 保留现有 rule-based 题库生成逻辑。
2. 当 `llm_client.provider == "mock"` 时，继续走 rule-based 输出。
3. 当 `llm_client.provider != "mock"` 时，调用 `LLMClient.generate_json()`。
4. 将真实 provider 返回内容校验为 `QuestionBank`。
5. 校验通过后返回真实结果。
6. 任意异常或校验失败时降级到 rule-based 输出。

测试内容：

1. 真实分支成功返回合法 `QuestionBank`。
2. provider JSON 无效时降级。
3. provider schema 不匹配时降级。
4. provider 超时时降级。
5. 现有 mock 测试保持通过。

## 3. 第二阶段：Provider Smoke Test

新增 smoke test：

1. `tests/smoke/test_llm_providers_smoke.py`
2. 默认 skip。
3. 仅在 `RUN_REAL_LLM_SMOKE_TESTS=1` 且 API key 存在时运行。
4. 使用最小 prompt 请求 provider 返回 JSON。

## 4. 第三阶段：扩展到其他 Agent（已完成）

已按以下范围接入真实分支：

1. `ResumeAnalyzerAgent`
2. `JDAnalyzerAgent`
3. `ExperienceAnalyzerAgent`
4. `MatchingAgent`
5. `AnswerEvaluatorAgent`
6. `MemoryAgent`

实现结果：

1. 默认 mock 不变。
2. 真实 provider 输出通过现有 Schema。
3. 真实调用与 Schema 校验失败会重试一次，再降级到既有 rule-based 输出。
4. 单元测试覆盖成功、JSON 无效、Schema 不匹配和 provider 超时。

## 5. 回归验证

每次接入后运行：

```powershell
.\\.venv\\Scripts\\python.exe -m pytest tests\\unit
.\\.venv\\Scripts\\python.exe -m pytest tests\\integration
.\\.venv\\Scripts\\python.exe -m pytest tests\\e2e
```

完成标准：

1. Phase 1 现有 100 个测试继续通过。
2. 新增 QuestionBankAgent 单元测试通过。
3. smoke test 默认 skip。
