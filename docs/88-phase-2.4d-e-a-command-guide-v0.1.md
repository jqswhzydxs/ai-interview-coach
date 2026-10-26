# Phase 2.4D-E-A Protocol v4 Command Guide

以下命令仅供未来逐阶段明确授权后使用。本阶段没有执行真实命令，也没有创建下列正式目录。路径在首次执行前应作为该轮协议资产冻结，且不得指向任何 v1/v2/v3 目录。

```powershell
$ledger = "storage/reports/question-bank-token-phase-2-4d-e-readiness-20261024/provider-readiness-v4.json"
$runDir = "storage/reports/question-bank-token-phase-2-4d-e-v4-20261024-ab1"
```

## 1. Readiness

`prepare` 只创建独立 ledger，不调用 Provider：

```powershell
.\.venv\Scripts\python.exe scripts\run_question_draft_provider_readiness_v4.py prepare `
  --ledger $ledger `
  --provider-label deepseek `
  --model-label deepseek-v4-pro
```

状态查询：

```powershell
.\.venv\Scripts\python.exe scripts\run_question_draft_provider_readiness_v4.py status `
  --ledger $ledger
```

未来获得 readiness 明确授权后，先设置双重安全门。凭据从既有安全配置读取，不在命令、ledger 或报告中输出：

```powershell
$env:RUN_REAL_LLM_ACCEPTANCE = "true"
$env:SAVE_FULL_LLM_LOGS = "false"
$env:LLM_PROVIDER = "deepseek"
$env:LLM_MODEL = "deepseek-v4-pro"
.\.venv\Scripts\python.exe scripts\run_question_draft_provider_readiness_v4.py attempt `
  --ledger $ledger `
  --authorize-phase-2-4d-e-a-readiness
```

每次 attempt 严格最多一个 Provider call。第一次失败时只能对同一 `$ledger` 再执行一次；两次失败后永久 blocked，不得新建 ledger 连续重试。

## 2. A/B Prepare 与 Status

只有 readiness 为 passed 后才可执行 `prepare`；runner 会先验证 ledger、Provider/model 和全部冻结哈希，再创建 A/B 目录：

```powershell
.\.venv\Scripts\python.exe scripts\run_question_draft_reasoning_effort_experiment_v4.py prepare `
  --run-dir $runDir `
  --readiness-ledger $ledger `
  --provider-label deepseek `
  --model-label deepseek-v4-pro
```

```powershell
.\.venv\Scripts\python.exe scripts\run_question_draft_reasoning_effort_experiment_v4.py status `
  --run-dir $runDir `
  --readiness-ledger $ledger
```

## 3. Smoke、Pilot 与 Full

三阶段必须分别获得用户明确授权并分别执行。任一命令完成后都会停止，不会自动启动下一阶段。

```powershell
.\.venv\Scripts\python.exe scripts\run_question_draft_reasoning_effort_experiment_v4.py smoke `
  --run-dir $runDir `
  --readiness-ledger $ledger `
  --authorize-phase-2-4d-e-a-smoke
```

```powershell
.\.venv\Scripts\python.exe scripts\run_question_draft_reasoning_effort_experiment_v4.py pilot `
  --run-dir $runDir `
  --readiness-ledger $ledger `
  --authorize-phase-2-4d-e-a-pilot
```

```powershell
.\.venv\Scripts\python.exe scripts\run_question_draft_reasoning_effort_experiment_v4.py full `
  --run-dir $runDir `
  --readiness-ledger $ledger `
  --authorize-phase-2-4d-e-a-full
```

## 4. 独立盲评与 Finalize

Full 完成后，把 `question-review-template.json` 交给独立 evaluator。完成文件必须匹配 30 个 submission IDs 与顺序，并包含 evaluator 信息、150 个正文分数和 750 个逐题 metadata 分数。然后运行：

```powershell
.\.venv\Scripts\python.exe scripts\run_question_draft_reasoning_effort_experiment_v4.py finalize `
  --run-dir $runDir `
  --readiness-ledger $ledger `
  --review-file "$runDir/blind-review/question-review-completed.json"
```

Finalize 不发起 Provider 请求。不得复制 v3 review、Token、submission IDs 或任何 v3 样本到 v4。
