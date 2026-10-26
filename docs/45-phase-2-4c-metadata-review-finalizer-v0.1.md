# Phase 2.4C metadata review finalizer

## Purpose

The finalizer consumes a completed independent metadata review and produces the
unblinded Phase 2.4C decision report. It is an offline engineering tool. It does
not call a Provider, access the network, modify the replay assets, change the
production Agent, or perform a production switch.

The finalizer must not be run against the blank review template. It requires a
separate `metadata-review-completed.json` created by an independent evaluator.

## Frozen gate policy

Policy version: `phase-2.4c-metadata-gates-v1`.

Both gates are mandatory:

1. replay Candidate corpus metadata v2 mean must be at least 3.5;
2. holdout corpus metadata v2 mean must be at least 3.5.

Failure of either gate makes metadata v2 ineligible for production integration.
Passing both gates only makes it eligible for a separate production integration
decision. The finalizer never performs that integration.

## Validation and unblinding order

Before reading `audit/private-blinding-map.json`, the finalizer:

1. reads the frozen blank template and completed review;
2. checks the exact review version;
3. requires complete evaluator type, identifier, and an explicit
   `independence_confirmed: true`;
4. checks all 38 submission IDs and their order against the template;
5. requires exactly 25 integer scores from 1 through 5 for each submission;
6. requires exactly 950 scores, with no null, NaN, duplicate, missing, or extra
   submission;
7. checks the six qualitative field-note keys.

Only after those checks pass does it read the private map and replayed banks.
The private inputs must describe exactly 19 complete v1/v2 pairs: 15 replay
Candidate corpora and 4 holdout corpora. Paired question text must be identical.

The four inputs are hashed and checked before unblinding, before output commit,
and after output commit. If an input changes, the finalizer removes any reports
created by that invocation and fails.

## Report interpretation

The JSON and Markdown reports include:

- exact evaluator type and identifier;
- v1 and v2 means overall, for replay and holdout, and for every detected
  technology stack;
- v2-minus-v1 paired improvement;
- bank-level and question-level win/tie/loss;
- the two frozen gate decisions;
- purpose, source, framework, anchors, follow-up, and advice issue notes.

The review supplies one numeric metadata-fit score per question. It does not
supply six numeric field scores. The finalizer therefore reports field issues
from the evaluator's qualitative notes and never invents field-level scores.

Technology stacks are classified from the paired frozen `question_text` only.
Generated metadata is excluded so that v1 and v2 cannot classify the same
corpus differently.

## Invocation

Run only after the independent completed review exists:

```powershell
& '.\.venv\Scripts\python.exe' scripts\finalize_question_bank_metadata_review.py `
  --template storage\reports\question-bank-metadata-phase-2-4c-offline-20261020\blind-review\metadata-review-template.json `
  --mapping storage\reports\question-bank-metadata-phase-2-4c-offline-20261020\audit\private-blinding-map.json `
  --replayed-banks storage\reports\question-bank-metadata-phase-2-4c-offline-20261020\audit\replayed-question-banks.json `
  --completed-review storage\reports\question-bank-metadata-phase-2-4c-offline-20261020\blind-review\metadata-review-completed.json `
  --output-json storage\reports\question-bank-metadata-phase-2-4c-offline-20261020\metadata-review-final-report.json `
  --output-markdown storage\reports\question-bank-metadata-phase-2-4c-offline-20261020\metadata-review-final-report.md
```

Existing output reports are never overwritten silently.
