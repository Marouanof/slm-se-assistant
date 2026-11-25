# Benchmark Preparation (Mission 01) + Kaggle Baseline (Mission 02.2)

This directory contains the reproducible dataset and prompt layer for the six-task
SLM benchmark. It deliberately contains **no model weights, inference code,
quantisation code or GPU code**. Mission 01 prepares data and prompts only.
Mission 02.2 adds the **Kaggle-only** baseline notebook and local result
handling; it does not change the datasets or prompts.

## Baseline results - Kaggle only (Mission 02.2)

`notebooks/baseline_benchmark.ipynb` + `configs/baseline_config.yaml` run on
Kaggle with **no Google Drive, no Drive mount, no Colab and no cloud
synchronisation**. Benchmark data is read-only under
`/kaggle/input/<dataset-slug>/benchmark/`; temporary files, checkpoints,
results and the export ZIP live under `/kaggle/working/`. Checkpoints go to a
versioned `results/` tree (`smoke_test/` separate from `baseline/`, one
`<RUN_ID>` directory per session/account) and are exported as a ZIP downloaded
from the Kaggle Output pane to `%USERPROFILE%\Downloads\slm-benchmark\`.

- `MODE="full"` - official run, all 670 examples, stored under
  `results/baseline/`.
- `MODE="smoke_test"` - first `SMOKE_PER_TASK` rows per task, stored under
  `results/smoke_test/`.
- One model at a time, one T4 16 GB (`device_map={"": 0}`).
- Generated code is **never executed**; `code_generation`,
  `code_refactoring` and `unit_test_generation` are marked `skipped` until a
  real isolated backend exists.

Local merging/validation:

```powershell
$base = "$env:USERPROFILE\Downloads\slm-benchmark"
python benchmark\scripts\merge_results.py --source "$base\session-01\results" --dest "$base\merged\results"
python benchmark\scripts\validate_baseline_results.py --results "$base\merged\results\baseline" --check-sha256
python benchmark\scripts\aggregate_baseline.py --results "$base\merged\results\baseline"
```

Full procedure: `docs/KAGGLE_SETUP.md`; download/merge:
`docs/RESULTS_DOWNLOAD_AND_MERGE.md`; protocol:
`reports/baseline_protocol.md`; Kaggle MCP capability inventory:
`reports/kaggle_mcp_inspection.md`.

## Prepared Kaggle bundle

```powershell
python benchmark\scripts\prepare_kaggle_dataset.py --owner <kaggle-username>
python benchmark\scripts\verify_kaggle_readiness.py
```

The bundle is written to `kaggle_upload/slm-benchmark-baseline/` and must be
uploaded as a **private** Kaggle Dataset. It contains hidden references under
`benchmark/datasets/private/test/`; never make it public.

## Structure

```text
benchmark/
  configs/benchmark_config.yaml
  configs/baseline_config.yaml
  datasets/
    raw/            Official artefacts (pinned revisions) + MANIFEST.json
    processed/      Full records, including hidden references
    development/    Prompt-safe development JSONL (references hidden)
    test/           Prompt-safe evaluation JSONL (references hidden)
    private/        Hidden references: answers, tests, mutants
  prompts/          Six prompt templates + prompt_registry.py
  scripts/          Download, preparation, validation, leakage checks,
                    Kaggle packaging and readiness checks
  notebooks/        baseline_benchmark.ipynb (Kaggle-only)
  docs/             Kaggle setup and result merge procedures
  metadata/         Dataset sources and licences
  reports/          Validation, leakage and preparation reports
```

## Quick start (CPU only, no GPU)

```bash
cd C:\LF\DLP
python -m venv .venv-benchmark
.venv-benchmark\Scripts\python.exe -m pip install -r benchmark\requirements.txt
.venv-benchmark\Scripts\python.exe benchmark\scripts\download_datasets.py
.venv-benchmark\Scripts\python.exe benchmark\scripts\audit_canonical.py
.venv-benchmark\Scripts\python.exe benchmark\scripts\prepare_datasets.py
.venv-benchmark\Scripts\python.exe benchmark\scripts\validate_datasets.py
.venv-benchmark\Scripts\python.exe benchmark\scripts\check_leakage.py
```

## Fairness guarantees

- The same JSONL rows, in the same order, are used for every model.
- The same instruction text is used for every model.
- Model-specific chat templates are applied only at the tokenizer boundary by
  `benchmark/prompts/prompt_registry.py::apply_chat_template`.
- Reference answers, tests, mutants and labels are stored in `datasets/private/`
  and `datasets/processed/`, never in `datasets/development/` or `datasets/test/`.
- The generation budget and decoding parameters are fixed by the baseline
  configuration and are identical for every model.

## Evaluation methods

| Task | Method |
|---|---|
| Code generation | `pass@1` with hidden official tests, compilation and isolated subprocess |
| Code explanation | ROUGE-L proxy plus a criteria rubric and human review on a sample |
| Bug detection | Precision, recall and F1 on `has_bug` |
| Code refactoring | Compilation and hidden reference-test preservation |
| Unit test generation | pytest validity on the canonical solution plus mutation score |
| Code completion | Whitespace-insensitive exact match and edit similarity |

**Mission 02.2 safety gate:** the three execution-dependent methods above are
not run in the Kaggle notebook. They are generated and marked `skipped`;
their aggregate metrics are `null`. See `reports/baseline_protocol.md`.

## What this directory does not contain

- No model weights and no Hugging Face cache.
- No inference, benchmarking or quantisation code.
- No GPU code and no Colab/Kaggle runtime code beyond the Kaggle notebook.
- No API secrets or tokens.
