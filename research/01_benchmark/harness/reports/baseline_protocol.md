# Baseline Protocol (Mission 02, updated for Mission 02.2)

## Scope

Mission 02.2 executes the baseline on **Kaggle only**. Google Colab and Google
Drive are not used. No cloud synchronisation is used. The temporary Kaggle
filesystem is not a persistence layer; results are exported as a ZIP from
`/kaggle/working/` and downloaded from the Output pane.

## Models

- Qwen/Qwen2.5-Coder-1.5B-Instruct (`qwen15`)
- Qwen/Qwen2.5-Coder-3B-Instruct (`qwen3`)
- microsoft/Phi-4-mini-instruct (`phi4mini`)

All three are run in FP16 with the same decoding parameters:
temperature 0.0, do_sample False, top_p 1.0, max_new_tokens 512,
repetition_penalty 1.0, seed 42, batch size 1.

Phi-4-mini-instruct is loaded with `trust_remote_code=True` and
`attn_implementation="eager"`. Qwen models use their default attention
implementation. If FP16 loading fails, the run must stop and report the error;
it must not silently switch to 4-bit or 8-bit.

### Single-GPU contract

The target is one NVIDIA T4 16 GB. The notebook sets
`device_map={"": 0}` so a second T4 (if Kaggle exposes one) is never used.
Only one model is loaded at a time; the unload cell must be run before loading
the next model.

### Static memory budget

No model was loaded during Mission 02.2 preparation. The following are static
estimates from the published `config.json` files and safetensors sizes:

| Model | FP16 weights | Expected peak | Worst case / T4 headroom |
|---|---:|---:|---:|
| Qwen2.5-Coder-1.5B-Instruct | 3.09 GB | ~5.0 GB | ~10.8 GB headroom |
| Qwen2.5-Coder-3B-Instruct | 6.17 GB | ~8.5 GB | ~7.3 GB headroom |
| Phi-4-mini-instruct | 7.67 GB | ~11.5 GB | ~14.0 GB worst case, ~1.8 GB headroom |

The estimates include weights, KV cache, prefill/activation overhead and
runtime overhead. `MAX_INPUT_TOKENS=8192` bounds the worst case. The actual
peak is measured per run with `torch.cuda.max_memory_allocated()`. The first
real Phi-4-mini run must confirm it; if it OOMs, stop and report.

## Prompts

Prompts come from `benchmark/prompts/prompt_registry.py`. The same messages are
used for every model. Only the tokenizer's native chat template is applied; the
content is never modified per model.

## Data

- Model input: `benchmark/datasets/test/*.jsonl` only.
- Evaluation references: `benchmark/datasets/private/test/*.jsonl` only, loaded
  in the evaluation stage after generation.
- All 670 verified test examples are used in their original order for
  `MODE="full"`. `MODE="smoke_test"` uses only the first
  `SMOKE_PER_TASK` (3) rows per task and is reported separately.
- On Kaggle, both splits are read-only from
  `/kaggle/input/<dataset-slug>/benchmark/...`.

## Performance metrics

Recorded per example and aggregated:

- Input tokens and output tokens (tokenizer-encoded).
- Latency: wall-clock time from start of generation to end of generation,
  measured with CUDA synchronisation where available. Model loading time is
  measured separately and is never included in per-example latency.
- TTFT: time from generation start to the first non-empty streamed token.
- Throughput: output tokens divided by latency.
- Peak VRAM: `torch.cuda.max_memory_allocated` (reset before each model run).
- RAM and GPU utilisation are recorded where available.
- `input_truncated`: true if the 8192-token guard was hit. No benchmark prompt
  is expected to hit it; if one does, review the run before aggregating.

## Checkpointing and storage (Mission 02.2)

No Google Drive, no Drive mounting, no Colab and no cloud synchronisation.

Layout (`RESULTS_ROOT=/kaggle/working/results/`):

```text
results/
├── smoke_test/qwen15/<RUN_ID>/, qwen3/<RUN_ID>/, phi4mini/<RUN_ID>/
├── baseline/qwen15/<RUN_ID>/, qwen3/<RUN_ID>/, phi4mini/<RUN_ID>/  # MODE=full
└── metadata/ (run_<RUN_ID>.json, progress, dataset hashes, SHA256SUMS.txt)
```

Results are appended to `results/<MODE_DIR>/<model_dir>/<RUN_ID>/<task>_results.jsonl`
after every example and flushed. Each `(MODE, model)` run owns a unique
`RUN_ID` directory (`<model_dir>_<mode>_<UTC timestamp>_<hostname>_<uuid8>`),
so results from other sessions/accounts are never overwritten. Re-running
the main loop in the same session resumes (completed IDs are skipped,
including error rows); a disconnection destroys the temporary filesystem,
so the ZIP must be downloaded before disconnecting. A CSV aggregate
(`<short>_all_results.csv`) lives alongside the JSONL files in the run
directory. `SHA256SUMS.txt` (inside the ZIP) covers every result and
metadata file; the ZIP hash is printed on export with a `.sha256` sidecar.

`MODE_DIR` is `baseline` for `MODE="full"` and `smoke_test` for
`MODE="smoke_test"`. `MODE="baseline"` is accepted as a legacy alias and
normalised to `"full"`.

## Execution security

Generated code is **not executed** by the Mission 02.2 notebook. The Kaggle
runtime does not provide a real isolated sandbox by default: a subprocess has
no network isolation, no CPU/memory limits and no filesystem restrictions.
`EXECUTION_BACKEND="none"` and `ALLOW_UNSANDBOXED_CODE_EXECUTION=False` are
asserted in the notebook, and `run_python()` raises unconditionally.

Consequences for the three execution-dependent tasks:

- `code_generation`: generated, but `pass@1` is `null`; only a static syntax
  check (`ast.parse`) and text fields are recorded.
- `code_refactoring`: generated, but `behaviour_preservation` is `null`; only
  static syntax and the changed/no-op flag are recorded.
- `unit_test_generation`: generated, but `validity_rate` and
  `avg_mutation_score` are `null`; only static syntax and the test count are
  recorded.

The other three tasks (`code_explanation`, `bug_detection`,
`code_completion`) are fully scored. A complete official baseline requires a
real isolated backend (container/nsjail, network disabled, read-only
filesystem, non-root user, cgroup CPU/memory limits, no access to private data
or credentials). That backend was not implemented in Mission 02.2.

Only Python code from the benchmark models would be executed by such a
backend. No credentials, API keys or private data are exposed to the
subprocess environment.

## Reproducibility metadata

Each run records model ID, model source (Kaggle Models path or Hugging Face
ID), short name, model directory, mode, mode directory, RUN_ID, tokenizer ID,
Transformers/PyTorch/Python versions, GPU model, precision, generation
parameters, max input tokens, single-GPU device map, execution backend,
read-only input flag and per-file dataset hashes in `metadata.json` /
`run_<RUN_ID>.json` and in every result row (`model`, `model_source`,
`model_dir`, `mode`, `run_id`, `eval_skipped`). The ZIP
(`slm-benchmark_results_<MODE>_<RUN_ID>.zip`) carries the full `results/`
tree; download it from the Kaggle Output pane to
`%USERPROFILE%\Downloads\slm-benchmark\` and merge with
`benchmark/scripts/merge_results.py`. See
`benchmark/docs/RESULTS_DOWNLOAD_AND_MERGE.md` and
`benchmark/docs/KAGGLE_SETUP.md`.
