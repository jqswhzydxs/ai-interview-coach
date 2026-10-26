# Phase 2.4D-A QuestionDraft Prompt Token 实施计划

日期：2026-10-21。

1. 在任何修改前冻结生产、2.4B run2、2.4C 报告、v0.1 Prompt、Schema、assembler、fixture 和当前安全链路的 SHA-256。
2. 新建 v0.2 Prompt，只调整 QuestionDraft 生成指令；不改 Schema、模型、client 或业务路径。
3. 新建独立实验 Agent，以必填构造参数选择 v0.1/v0.2，并将 exact metadata v2 assembler 绑定为相同依赖。比较两份 LLMRequest，除 Prompt 文本外必须相同。
4. 新建 2.4D paired runner：独立 smoke、pair 1 pilot、pair 2–5 full；实现交替顺序、deadline pair mate、调用与 Token 预算、usage unknown、真实 input/output 私有审计、Prompt/hash、内容安全、长度和指纹记录。
5. 创建随机盲序 packet、评分模板与私有映射；预注册正文及 metadata v2 门禁。finalize 只接受完整独立 evaluator 元数据和完整分数。
6. CLI 提供 prepare/status 与为 2.4D-B 预留的 smoke/pilot/full/finalize。真实阶段使用命令行授权和 real acceptance 配置双重门禁；D-A 只执行 prepare。
7. 用 fake Provider 覆盖同进程隔离、唯一请求变量、hash 漂移、幂等、预算、deadline、重试/fallback、unknown usage、12 pair 可评价性、盲法和 metadata 固定。
8. 运行专项、全量离线、迁移、compileall、diff、socket guard 与冻结哈希终检，输出独立验证报告后停止。

离线准备命令：

```powershell
.\.venv\Scripts\python.exe scripts/run_question_draft_token_experiment.py prepare `
  --run-dir <新的空目录> `
  --provider-label <未来 Provider 标识> `
  --model-label <未来模型标识>
```

`prepare` 目录只是离线协议快照。未来真实执行应在 2.4D-B 授权后使用新的空目录，以当时的真实 Provider/model 建立不可变 manifest。

验证命令：

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_question_draft_prompt_experiment.py tests/integration/test_question_draft_token_experiment.py -q -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest -m "not real_llm" -q -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests/integration/test_migrations.py -q -p no:cacheprovider
.\.venv\Scripts\python.exe -m compileall -q app tests scripts
git -c safe.directory=D:/桌面/ai-interview-coach diff --check
```
