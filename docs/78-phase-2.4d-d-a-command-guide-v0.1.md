# Phase 2.4D-D-A 命令使用说明

以下命令供后续逐阶段授权时使用。本阶段没有执行这些真实命令。路径示例中的日期和 run 名称必须在执行前按批准方案冻结，且不得指向任何旧目录。

```powershell
$ledger = "storage/reports/question-bank-token-phase-2-4d-d-readiness-20261023/provider-readiness-v3.json"
$runDir = "storage/reports/question-bank-token-phase-2-4d-d-v3-20261023-ab1"
```

## 1. Readiness

离线创建 ledger，不调用 Provider：

```powershell
.\.venv\Scripts\python.exe scripts\run_question_draft_provider_readiness_v3.py prepare `
  --ledger $ledger `
  --provider-label deepseek `
  --model-label deepseek-v4-pro
```

状态查询：

```powershell
.\.venv\Scripts\python.exe scripts\run_question_draft_provider_readiness_v3.py status `
  --ledger $ledger
```

后续获得 readiness 明确授权后，每次命令最多执行一个 Provider call：

```powershell
$env:RUN_REAL_LLM_ACCEPTANCE = "true"
$env:SAVE_FULL_LLM_LOGS = "false"
.\.venv\Scripts\python.exe scripts\run_question_draft_provider_readiness_v3.py attempt `
  --ledger $ledger `
  --authorize-phase-2-4d-d-a-readiness
```

首次失败时只允许对同一个 `$ledger` 再执行一次 attempt。不得新建 ledger 绕过次数限制。

## 2. A/B prepare

只有 readiness 状态为 passed 后才能执行。该命令会首次创建正式 A/B 目录：

```powershell
.\.venv\Scripts\python.exe scripts\run_question_draft_reasoning_experiment_v3.py prepare `
  --run-dir $runDir `
  --readiness-ledger $ledger `
  --provider-label deepseek `
  --model-label deepseek-v4-pro
```

状态查询：

```powershell
.\.venv\Scripts\python.exe scripts\run_question_draft_reasoning_experiment_v3.py status `
  --run-dir $runDir `
  --readiness-ledger $ledger
```

## 3. Smoke、Pilot 与 Full

三阶段需要分别获得用户授权并分别执行。任何命令都不会自动启动下一阶段。

```powershell
.\.venv\Scripts\python.exe scripts\run_question_draft_reasoning_experiment_v3.py smoke `
  --run-dir $runDir `
  --readiness-ledger $ledger `
  --authorize-phase-2-4d-d-a-smoke
```

```powershell
.\.venv\Scripts\python.exe scripts\run_question_draft_reasoning_experiment_v3.py pilot `
  --run-dir $runDir `
  --readiness-ledger $ledger `
  --authorize-phase-2-4d-d-a-pilot
```

```powershell
.\.venv\Scripts\python.exe scripts\run_question_draft_reasoning_experiment_v3.py full `
  --run-dir $runDir `
  --readiness-ledger $ledger `
  --authorize-phase-2-4d-d-a-full
```

## 4. 独立盲评 finalize

Full 完成并取得与模板严格匹配的独立盲评文件后执行：

```powershell
.\.venv\Scripts\python.exe scripts\run_question_draft_reasoning_experiment_v3.py finalize `
  --run-dir $runDir `
  --readiness-ledger $ledger `
  --review-file "path/to/independent-review-v3.json"
```

不要把 ab1 的盲评、Token 数值或 submission IDs 复制到 v3。
