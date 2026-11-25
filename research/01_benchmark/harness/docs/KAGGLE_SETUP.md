# Kaggle Setup - Mission 02.2 (Preparation Only)

This guide prepares the **Kaggle-only** baseline. Nothing in this guide was
executed: no notebook was run, no model was downloaded or loaded, and no GPU
was used.

## 1. What was prepared

| Resource | Location / reference | Status |
|---|---|---|
| Kaggle-only notebook | `benchmark/notebooks/baseline_benchmark.ipynb` | Updated, static validation passed |
| Kaggle configuration | `benchmark/configs/baseline_config.yaml` | Updated, YAML validation passed |
| Private dataset upload bundle | `kaggle_upload/slm-benchmark-baseline/` | Built locally, **not uploaded** |
| Dataset metadata | `kaggle_upload/slm-benchmark-baseline/dataset-metadata.example.json` | Private, placeholder owner; rerun with `--owner` for CLI |
| Local readiness checker | `benchmark/scripts/verify_kaggle_readiness.py` | Added |
| Kaggle MCP capability inspection | `benchmark/reports/kaggle_mcp_inspection.md` | Added, read-only calls only |
| Local merge/validation/aggregation | `benchmark/scripts/merge_results.py`, `validate_baseline_results.py`, `aggregate_baseline.py` | Updated |
| Official Qwen Kaggle Models | `qwen-lm/qwen2.5-coder` / `Transformers` / `1.5b-instruct` and `3b-instruct` | Existing, read-only reference |
| Phi-4-mini Hugging Face model | `microsoft/Phi-4-mini-instruct` | Existing, Internet required |
| Optional Phi-4-mini community mirror | `kentarctic/phi-4-mini-instruct` / `Transformers` / `official-from-huggingface` | Unofficial; optional |

The Kaggle MCP was inspected. It exposes read-only metadata tools plus
notebook-session and dataset-file operations, but **no tool to create a new
Kaggle Dataset or to write a notebook without running it**. Therefore no
Kaggle resource was created or modified by the MCP. The safe, prepared
artefact is the local upload bundle above; you upload it manually.

## 2. Kaggle prerequisites

1. A Kaggle account with GPU quota.
2. The benchmark bundle uploaded as a **private** Kaggle Dataset.
3. A Kaggle Notebook created from `baseline_benchmark.ipynb`.
4. Accelerator: **GPU T4 x1** (not x2).
5. Internet: **On** (needed for the Hugging Face fallback and dependencies).
6. Persistence: **Files only** (no Drive, no cloud sync).

## 3. Create the private benchmark dataset

The bundle already contains the required layout:

```text
kaggle_upload/slm-benchmark-baseline/
├── dataset-metadata.example.json   # dataset-metadata.json after --owner
└── benchmark/
    ├── datasets/test/*.jsonl
    ├── datasets/private/test/*.jsonl
    ├── prompts/prompt_registry.py
    ├── notebooks/baseline_benchmark.ipynb
    ├── configs/baseline_config.yaml
    ├── scripts/...
    ├── docs/...
    └── reports/baseline_protocol.md
```

The dataset is private because `datasets/private/test/` contains hidden
references (tests, expected outputs, mutants). Never make it public.

### Option A - Kaggle web UI (recommended)

1. Kaggle -> **Datasets** -> **New Dataset**.
2. Upload the folder `C:\LF\DLP\kaggle_upload\slm-benchmark-baseline`.
3. Title: `SLM Benchmark Baseline (private)`.
4. Visibility: **Private**.
5. Create. The dataset slug will normally be
   `slm-benchmark-baseline`; the mounted path becomes:

   ```text
   /kaggle/input/slm-benchmark-baseline/benchmark/...
   ```

6. Confirm the dataset page lists `benchmark/datasets/test/` and
   `benchmark/datasets/private/test/`.

### Option B - Kaggle CLI (only if `~/.kaggle/kaggle.json` exists)

The default bundle contains `dataset-metadata.example.json` (placeholder
owner); the web UI upload does not need it. For the CLI, rebuild with your
username so `dataset-metadata.json` is created:

```powershell
python benchmark\scripts\prepare_kaggle_dataset.py --owner <your-kaggle-username> --force

# Create the dataset (private metadata is already set):
kaggle datasets create -p C:\LF\DLP\kaggle_upload\slm-benchmark-baseline

# Later updates:
kaggle datasets version -p C:\LF\DLP\kaggle_upload\slm-benchmark-baseline -m "Update benchmark bundle"
```

The `KAGGLE_API_TOKEN` used by the MCP is not a `kaggle.json` username/key
pair, so do not assume the CLI is authenticated. Use the web UI if in doubt.

## 4. Create the Kaggle notebook

1. Kaggle -> **Code** -> **New Notebook**.
2. **File -> Import Notebook** -> upload
   `benchmark/notebooks/baseline_benchmark.ipynb`.
3. **Add Input -> Datasets ->** your private `slm-benchmark-baseline`.
4. **Add Input -> Models (optional, recommended for Qwen)**:
   - `qwen-lm/qwen2.5-coder`, framework `Transformers`,
     instance `1.5b-instruct`, version `1`.
   - `qwen-lm/qwen2.5-coder`, framework `Transformers`,
     instance `3b-instruct`, version `1`.
   If you do not attach them, the notebook uses the Hugging Face model IDs
   and downloads them at runtime.
5. For Phi-4-mini, leave the notebook on the Hugging Face ID by default. The
   community Kaggle mirror is optional and unofficial; only attach it if you
   have verified its files against `microsoft/Phi-4-mini-instruct`.
6. **Settings**:
   - Accelerator: **GPU T4 x1**
   - Internet: **On**
   - Persistence: **Files only**
7. Do **not** click "Run All" during preparation. You will run the cells
   manually in the next section.

## 5. Run the smoke test first

1. Run the environment cell. If it reports `rouge_score` as `MISSING`, run
   `!pip install -q rouge_score` in a separate Kaggle cell and re-run the
   environment cell. The notebook raises an explicit error instead of
   silently scoring `None` for code explanation.
2. In the configuration cell set:

   ```python
   MODEL_ID = "Qwen/Qwen2.5-Coder-1.5B-Instruct"
   MODE = "smoke_test"
   ```

3. Run the cells in order: environment, storage, configuration, prompts/data,
   model loading, generation, evaluation, checkpointing, main loop, unload,
   export.
4. The main loop processes the first `SMOKE_PER_TASK = 3` rows per task.
5. Generated code is **not executed**. The three execution-dependent tasks
   (`code_generation`, `code_refactoring`, `unit_test_generation`) are
   generated and marked `{"skipped": true, ...}`.
6. Run the export cell. Download
   `slm-benchmark_results_smoke_test_<RUN_ID>.zip` and its `.sha256` sidecar
   from the **Output** pane.
7. Run the unload cell.

Save the ZIP under:

```text
%USERPROFILE%\Downloads\slm-benchmark\
```

## 6. Run the official `full` mode sequentially

For each model, one at a time:

1. Set `MODE = "full"` and the model ID.
2. Run the configuration cell (it creates a new `RUN_ID`).
3. Run the model loading cell.
4. Run the main loop. `MODE="full"` writes to
   `results/baseline/<model>/<RUN_ID>/` and processes all 670 examples.
5. Run the export cell and download the ZIP from the Output pane.
6. Run the unload cell before switching model. The load cell refuses to load
   a second model while `model`/`tokenizer` are still defined.

Recommended order:

```text
Qwen/Qwen2.5-Coder-1.5B-Instruct
Qwen/Qwen2.5-Coder-3B-Instruct
microsoft/Phi-4-mini-instruct
```

For a first Kaggle run, prefer one model per session. The notebook forces
`device_map={"": 0}`, so a second T4 is left idle if Kaggle exposes two.

## 7. Model readiness on a T4 16 GB

These are **static estimates**, not a real load. No model was downloaded or
loaded during preparation.

| Model | FP16 weights | Expected peak | Worst case / T4 headroom |
|---|---:|---:|---:|
| Qwen2.5-Coder-1.5B-Instruct | 3.09 GB | ~5.0 GB | ~10.8 GB headroom |
| Qwen2.5-Coder-3B-Instruct | 6.17 GB | ~8.5 GB | ~7.3 GB headroom |
| Phi-4-mini-instruct | 7.67 GB | ~11.5 GB | ~14.0 GB worst case, ~1.8 GB headroom |

Sources: Hugging Face `config.json` files and Kaggle Models file listings
(safetensors sizes). The estimates include weights, KV cache, prefill and
runtime overhead. Phi-4-mini is the tightest because it uses
`attn_implementation="eager"`; `MAX_INPUT_TOKENS=8192` bounds the worst case.
The notebook records the actual peak with `torch.cuda.max_memory_allocated()`.

**Limit of this verification:** actual loading was not performed, because
Mission 02.2 forbids launching GPU work. The first real run must confirm the
peak. If Phi-4-mini OOMs, stop and report it; do not silently switch to 4-bit
or 8-bit.

## 8. Result export and local merge

The export cell writes:

```text
/kaggle/working/slm-benchmark_results_<MODE>_<RUN_ID>.zip
/kaggle/working/slm-benchmark_results_<MODE>_<RUN_ID>.zip.sha256
```

Download both from the Kaggle **Output** pane. On Windows:

```powershell
$base = "$env:USERPROFILE\Downloads\slm-benchmark"
New-Item -ItemType Directory -Force -Path $base | Out-Null

# Extract one session per folder; never mix two ZIPs in the same folder.
# Use the exact ZIP name printed by the notebook (it contains the RUN_ID).
$zip = "$base\slm-benchmark_results_full_<RUN_ID>.zip"
Expand-Archive -Path $zip -DestinationPath "$base\session-01" -Force

# Compare with the printed ZIP SHA256.
Get-FileHash $zip -Algorithm SHA256

# Merge all extracted sessions (repeat --source per session).
python benchmark\scripts\merge_results.py `
  --source "$base\session-01\results" `
  --dest "$base\merged\results"

python benchmark\scripts\validate_baseline_results.py `
  --results "$base\merged\results\baseline" --check-sha256

python benchmark\scripts\aggregate_baseline.py `
  --results "$base\merged\results\baseline"
```

`MODE="full"` is stored under `results/baseline/`. `MODE="smoke_test"` is
stored under `results/smoke_test/`. They are never mixed.

## 9. Known issues and limitations

1. **Code-execution tasks cannot be officially scored yet.** The notebook
   hard-blocks generated-code execution because Kaggle does not provide an
   isolated sandbox by default. `code_generation` (`pass@1`),
   `code_refactoring` (behaviour preservation) and `unit_test_generation`
   (validity/mutation score) are recorded as `skipped`, and their aggregate
   metrics are `null`. A complete official baseline requires a real isolated
   backend (container/nsjail, network disabled, read-only filesystem,
   non-root, CPU/memory limits). This was not implemented.
2. **Phi-4-mini memory is tight.** The static worst case is ~14.0 GB on a
   15.78 GB T4. The observed benchmark prompts are much smaller, but the first
   run must be monitored. Do not change precision silently.
3. **Phi-4-mini Kaggle mirror is unofficial.** Prefer
   `microsoft/Phi-4-mini-instruct` from Hugging Face. If using the mirror,
   verify its files first.
4. **Kaggle MCP cannot create/upload a dataset or write a notebook without
   running it.** The local bundle and this guide replace that missing
   capability. No dataset, notebook or session was created by the MCP. See
   `benchmark/reports/kaggle_mcp_inspection.md` for the capability inventory.
5. **The temporary `/kaggle/working/` filesystem does not survive
   disconnection.** Export and download after each model.

## 10. Exact pre-flight checks (no GPU)

Run these locally before opening Kaggle:

```powershell
# Use the project environment (PyYAML is required for the readiness checker).
C:\LF\DLP\.venv-benchmark\Scripts\python.exe benchmark\scripts\verify_kaggle_readiness.py
python benchmark\scripts\validate_baseline_results.py --help
python benchmark\scripts\merge_results.py --help
python benchmark\scripts\aggregate_baseline.py --help
```

The readiness checker parses the notebook and config, verifies the 670 test
examples, checks that the model-facing split does not leak private keys,
checks the no-execution guard, and validates the private bundle. It does not
execute the notebook, load a model or touch the GPU.

## 11. Confirmation

- No notebook cell was executed.
- No Kaggle notebook session was created.
- No model was downloaded or loaded.
- No GPU was allocated or consumed.
- No Kaggle dataset, model or notebook was created or modified.
- Only read-only Kaggle MCP metadata calls were used (model listings and
  accelerator quota).
