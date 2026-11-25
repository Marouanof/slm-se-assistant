# Downloading and merging benchmark results (Mission 02.2, Kaggle-only)

No Google Drive, no Drive mounting, no Colab and no cloud synchronisation are
used. Results leave Kaggle only as a ZIP downloaded from the **Output** pane
and are organised locally under:

```text
%USERPROFILE%\Downloads\slm-benchmark\
```

The notebook never accesses your Windows filesystem directly.

## Result structure

Every session writes the same tree under `/kaggle/working/results/`:

```text
results/
├── smoke_test/
│   ├── qwen15/<RUN_ID>/
│   │   ├── <task>_results.jsonl  (one JSONL per task, appended per example)
│   │   ├── <short>_all_results.csv
│   │   └── metadata.json
│   ├── qwen3/<RUN_ID>/...
│   └── phi4mini/<RUN_ID>/...
├── baseline/                     # MODE="full" writes here
│   ├── qwen15/<RUN_ID>/...
│   ├── qwen3/<RUN_ID>/...
│   └── phi4mini/<RUN_ID>/...
└── metadata/
    ├── run_<RUN_ID>.json           (run metadata + dataset hashes)
    ├── progress_<RUN_ID>.json
    ├── dataset_manifest.json
    ├── export_manifest.json
    └── SHA256SUMS.txt              (every file under results/)
```

- **RUN_ID** (`<model_dir>_<mode>_<UTC timestamp>_<hostname>_<uuid8>`) is
  unique per session/account and stable while the kernel lives, so
  re-running the main loop resumes instead of overwriting. A new session
  always gets a new RUN_ID.
- **Modes:** `MODE="full"` writes under `baseline/` and processes all 670
  test examples. `MODE="smoke_test"` writes under `smoke_test/` and processes
  the first `SMOKE_PER_TASK` rows per task. They are never mixed.
- **Resume:** interruption within the same session is resumed by re-running
  the main loop (completed IDs are skipped). After a disconnection the
  temporary filesystem is gone - re-run that model with a fresh RUN_ID; the
  earlier downloaded ZIP is never overwritten.
- **Hashes:** `SHA256SUMS.txt` (inside the ZIP) covers every result and
  metadata file. The ZIP itself has a `.sha256` sidecar and its hash is
  printed in the notebook output.

## Kaggle procedure

1. Set `MODEL_ID` and `MODE` in the configuration cell.
2. Run the notebook cells manually. Outputs go to
   `/kaggle/working/results/`.
3. Run the export cell. It creates
   `slm-benchmark_results_<MODE>_<RUN_ID>.zip` plus a `.sha256` sidecar under
   `/kaggle/working/`.
4. Open the **Output** pane -> download the ZIP (and the sidecar). Save to
   `%USERPROFILE%\Downloads\slm-benchmark\`.
5. Run the unload cell before loading the next model.
6. Download before the session ends.

## Local verification and merging (Windows, PowerShell)

Run from your benchmark checkout (`C:\LF\DLP` or wherever `benchmark/` lives):

```powershell
$base = "$env:USERPROFILE\Downloads\slm-benchmark"
New-Item -ItemType Directory -Force -Path $base | Out-Null
```

Per session/account - extract into a **dedicated** folder (pick a new name
each time; never extract two sessions into the same folder):

```powershell
# Session 1: set the exact ZIP downloaded from the Output pane. The filename
# contains the RUN_ID; do not use a wildcard when several ZIPs are present.
$zip = "$base\slm-benchmark_results_full_<RUN_ID>.zip"
Expand-Archive -Path $zip -DestinationPath "$base\session-01" -Force
```

Verify the portable hash of the ZIP itself (compare with the notebook
output / `.sha256` sidecar), then merge any number of sessions:

```powershell
Get-FileHash $zip -Algorithm SHA256

python benchmark\scripts\merge_results.py `
  --source "$base\session-01\results" `
  --source "$base\session-02\results" `
  --dest "$base\merged\results"
```

`merge_results.py`:

- verifies every source against its own `SHA256SUMS.txt` (abort on
  mismatch unless `--skip-verify`);
- unions the trees into `merged\results\` without overwriting a run
  directory or file with different bytes (identical re-merges are skipped);
- writes a fresh merged `SHA256SUMS.txt` + `metadata/SHA256SUMS.txt`.

After merging:

```powershell
python benchmark\scripts\validate_baseline_results.py --results "$base\merged\results\baseline" --check-sha256
python benchmark\scripts\aggregate_baseline.py --results "$base\merged\results\baseline"
```

Aggregate output lands in `merged\results\baseline\metadata\`
(`comparison_summary.csv/.json`, one row per model/mode/run/task).
The CSV contains `n`, `errors`, `scored` and `skipped` columns. For the three
execution-dependent tasks, `pass_at_1`, `behaviour_preservation` and
`validity_rate` are `null` while `eval.skipped` is true; this is intentional,
because generated code is not executed without an isolated backend.

## Rules for multiple sessions/accounts

1. One `RUN_ID` => one directory. Keep them all; never hand-edit a JSONL to
   force a merge.
2. Same example ID in two different `RUN_ID`s is expected (same benchmark,
   different sessions). It is **not** a duplicate error - duplicates are
   errors only *within* a single `<task>_results.jsonl`.
3. If a re-run of the same model was interrupted, resume it **in the same
   kernel** (re-run the main loop) rather than starting a new session.
   Across sessions, prefer a fresh full run over stitching two partial
   RUN_IDs, unless the merge keeps both directories intact - the validator
   reports both and the aggregate keeps them separate.
4. `smoke_test/` and `baseline/` aggregate separately. Never compare a smoke
   number with an official number.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `FileNotFoundError: Benchmark dataset not found` | Attach the private dataset so that `/kaggle/input/<slug>/benchmark/datasets/test/` exists, or place `benchmark/` under `/kaggle/working/slm-benchmark/` as a fallback. |
| Kaggle ZIP missing in Output | The ZIP must be under `/kaggle/working/`; re-run the export cell and refresh the Output pane. |
| `Refusing to overwrite` during merge | That `RUN_ID` already exists with different bytes. Inspect, then merge into a fresh `--dest`. |
| Hash mismatch | Re-download that session; do not merge a corrupt tree (or use `--skip-verify` only for debugging). |
| Session disconnected, files gone | Expected for the temporary filesystem. Re-run the model; the new RUN_ID keeps old downloads intact. |
| `null` pass@1 / behaviour / validity | Expected: generated code is not executed. See the safety gate in `KAGGLE_SETUP.md`. |
| Phi-4-mini OOM | Stop and report; do not silently switch to 4-bit/8-bit. Lower `MAX_INPUT_TOKENS` only after recording the truncation and reviewing the benchmark. |
