# Phase 2.4D-F-A Protocol v5 Command Guide

以下命令只供未来逐阶段明确授权后使用。本阶段未执行真实请求，也未创建这些正式路径。

```powershell
$ledger = "storage/reports/question-bank-token-phase-2-4d-f-readiness-20261024/provider-readiness-v5.json"
$runDir = "storage/reports/question-bank-token-phase-2-4d-f-v5-20261024-ab1"
```

## Readiness

离线 prepare 与 status：

```powershell
.\.venv\Scripts\python.exe scripts\run_question_draft_provider_readiness_v5.py prepare `
  --ledger $ledger `
  --provider-label deepseek `
  --model-label deepseek-v4-pro

.\.venv\Scripts\python.exe scripts\run_question_draft_provider_readiness_v5.py status `
  --ledger $ledger
```

未来经明确授权后的单次 attempt：

```powershell
$env:RUN_REAL_LLM_ACCEPTANCE = "true"
$env:SAVE_FULL_LLM_LOGS = "false"
$env:LLM_PROVIDER = "deepseek"
$env:LLM_MODEL = "deepseek-v4-pro"
.\.venv\Scripts\python.exe scripts\run_question_draft_provider_readiness_v5.py attempt `
  --ledger $ledger `
  --authorize-phase-2-4d-f-a-readiness
```

第一次失败时只能对同一 `$ledger` 再执行一次；两次失败后不得新建 ledger 重试。

## A/B prepare 与 status

只有 readiness passed 后，以下 prepare 才会创建 A/B 目录：

```powershell
.\.venv\Scripts\python.exe scripts\run_question_draft_prompt_recovery_experiment_v5.py prepare `
  --run-dir $runDir `
  --readiness-ledger $ledger `
  --provider-label deepseek `
  --model-label deepseek-v4-pro

.\.venv\Scripts\python.exe scripts\run_question_draft_prompt_recovery_experiment_v5.py status `
  --run-dir $runDir `
  --readiness-ledger $ledger
```

## Smoke、Pilot、Full

三阶段须分别授权；命令不会自动启动下一阶段。

```powershell
.\.venv\Scripts\python.exe scripts\run_question_draft_prompt_recovery_experiment_v5.py smoke `
  --run-dir $runDir `
  --readiness-ledger $ledger `
  --authorize-phase-2-4d-f-a-smoke

.\.venv\Scripts\python.exe scripts\run_question_draft_prompt_recovery_experiment_v5.py pilot `
  --run-dir $runDir `
  --readiness-ledger $ledger `
  --authorize-phase-2-4d-f-a-pilot

.\.venv\Scripts\python.exe scripts\run_question_draft_prompt_recovery_experiment_v5.py full `
  --run-dir $runDir `
  --readiness-ledger $ledger `
  --authorize-phase-2-4d-f-a-full
```

## 独立盲评与 finalize

Full 后由独立 evaluator 完成模板；AI 评审必须将 `evaluator.type` 写为 `AI`。Finalize 不访问 Provider：

```powershell
.\.venv\Scripts\python.exe scripts\run_question_draft_prompt_recovery_experiment_v5.py finalize `
  --run-dir $runDir `
  --readiness-ledger $ledger `
  --review-file "$runDir/blind-review/question-review-completed.json"
```

不得复制任何 v3/v4 Token、题目、评分、submission ID 或样本到 v5。
