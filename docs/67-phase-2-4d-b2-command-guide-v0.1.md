# Phase 2.4D-B2 完整命令说明

以下命令是后续授权阶段的操作说明。本阶段没有执行 `attempt`、`smoke`、`pilot` 或 `full` 的真实版本。示例中的 ledger 与 run 目录必须使用新的正式名称，不能使用 run1/run2/run3/run4 或任何历史目录。

## 1. Readiness

离线准备单一 ledger：

```powershell
.\.venv\Scripts\python.exe scripts\run_question_draft_provider_readiness_v2.py prepare `
  --ledger <readiness-ledger.json> `
  --provider-label <provider> `
  --model-label <exact-model>
```

查看状态，不访问 Provider：

```powershell
.\.venv\Scripts\python.exe scripts\run_question_draft_provider_readiness_v2.py status `
  --ledger <readiness-ledger.json>
```

真实 attempt 仅在另行授权后使用。先通过安全方式配置 Provider credential、`LLM_PROVIDER` 和精确 `LLM_MODEL`，然后执行：

```powershell
$env:RUN_REAL_LLM_ACCEPTANCE='true'
$env:SAVE_FULL_LLM_LOGS='false'
.\.venv\Scripts\python.exe scripts\run_question_draft_provider_readiness_v2.py attempt `
  --ledger <readiness-ledger.json> `
  --authorize-phase-2-4d-b-readiness
```

首次失败时重复同一条 `attempt` 命令和同一 ledger。不得复制 ledger 或新建目录规避上限。passed/blocked 后重复命令不会产生新调用。

## 2. Protocol v2 A/B

只有 readiness status 为 passed 后，才能离线创建 A/B manifest：

```powershell
.\.venv\Scripts\python.exe scripts\run_question_draft_token_experiment_v2.py prepare `
  --run-dir <new-protocol-v2-run-directory> `
  --readiness-ledger <readiness-ledger.json> `
  --provider-label <provider> `
  --model-label <exact-model>
```

查看状态：

```powershell
.\.venv\Scripts\python.exe scripts\run_question_draft_token_experiment_v2.py status `
  --run-dir <new-protocol-v2-run-directory> `
  --readiness-ledger <readiness-ledger.json>
```

后续真实阶段必须继续使用同一个 ledger、Provider 和 model，并分别显式授权：

```powershell
.\.venv\Scripts\python.exe scripts\run_question_draft_token_experiment_v2.py smoke `
  --run-dir <new-protocol-v2-run-directory> `
  --readiness-ledger <readiness-ledger.json> `
  --authorize-phase-2-4d-b2-ab

.\.venv\Scripts\python.exe scripts\run_question_draft_token_experiment_v2.py pilot `
  --run-dir <new-protocol-v2-run-directory> `
  --readiness-ledger <readiness-ledger.json> `
  --authorize-phase-2-4d-b2-ab

.\.venv\Scripts\python.exe scripts\run_question_draft_token_experiment_v2.py full `
  --run-dir <new-protocol-v2-run-directory> `
  --readiness-ledger <readiness-ledger.json> `
  --authorize-phase-2-4d-b2-ab
```

独立盲评完成后，离线应用 review：

```powershell
.\.venv\Scripts\python.exe scripts\run_question_draft_token_experiment_v2.py finalize `
  --run-dir <new-protocol-v2-run-directory> `
  --readiness-ledger <readiness-ledger.json> `
  --review-file <completed-independent-review.json>
```

protocol v1 仍使用原 CLI，仅用于历史复现；不得把 v1 manifest、usage 汇总或旧运行目录转换为 v2。
