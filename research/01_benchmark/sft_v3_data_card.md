# SFT v3 data card — six tasks

Status: **dataset built; Qwen 1.5B training and six-task evaluation complete;
3B SFT v3 ablation running.** The 1.5B v3 results are in
`qwen_v3_findings.md`.

## Purpose

The v2 adapter covered only `code_generation`, `unit_test_generation` and
`code_completion`. It improved refactoring/unit tests but catastrophically
forgot `bug_detection` (F1 0.0) and never trained `code_explanation` or
`code_refactoring`. v3 adds the three missing tasks so one adapter can be
evaluated on all six tasks.

## Counts

Built with `research/01_benchmark/harness/scripts/build_sft_v3.py` (seed 42).

| Task | Train | Validation |
|---|---:|---:|
| code_generation | 736 | 49 |
| code_explanation | 1200 | 50 |
| bug_detection | 1200 | 50 |
| code_refactoring | 236 | 49 |
| unit_test_generation | 250 | 50 |
| code_completion | 250 | 50 |
| **total** | **3872** | **298** |

The validation set is approximately 50 examples per task so the checkpoint
selection loss is not dominated by one task.

## Sources

| Source | Split used | License | Size |
|---|---|---|---|
| MBPP full train + validation, via the v2 pilot file | train/validation | CC-BY-4.0 | ~0.1 MB |
| CodeXGLUE defect detection | train + validation | C-UDA | 17.9 + 2.2 MB |
| CodeXGLUE code-to-text Python | **validation only** | C-UDA | 16.7 MB |

The CodeXGLUE code-to-text train split is 291 MB; it is not used. The
validation split is large enough for 1,200 explanation examples and 500
code-generation replay examples, and it keeps the download small.

The MBPP pilot uses MBPP full train+validation with every MBPP+ benchmark id
removed. The builder re-checks the numeric ids and drops any overlap.

105 CodeXGLUE functions appear in both the code-generation replay set and the
code-explanation set. They use different prompts and are multi-task training
examples, not duplicate rows within one task; there is no benchmark test
overlap.

## What is actually supervised

- `code_generation`: complete fenced function. 236 MBPP examples plus 500
  CodeXGLUE real-repository functions filtered to self-contained functions.
  The replay set is **not** algorithmic benchmark data.
- `unit_test_generation`: fenced pytest suite from MBPP.
- `code_completion`: raw next line(s) from MBPP.
- `code_refactoring`: the original MBPP function in input and output, plus a
  generic `### Changes` section. This teaches the output contract and
  behaviour-preserving copying, **not** a semantic refactoring strategy.
- `bug_detection`: one JSON object per C function. `has_bug` is the real
  CodeXGLUE label (600 true / 600 false in train, 25/25 in validation). The
  `location`, `description` and `fix` strings are **templated**, so the model
  is not supervised on defect localisation or repair.
- `code_explanation`: the four required headings. The CodeXGLUE docstring is
  placed under `## Purpose`; the other sections are deliberately short
  (`Not applicable` / `Not determinable from the snippet`). The model is not
  trained on a rich parameter/return/complexity reference.

## Leakage control

The builder hashes normalised benchmark test inputs and private references and
rejects exact overlaps. On the current data:

- MBPP benchmark ids dropped: 0 (the pilot already excluded them).
- Exact CodeXGLUE/MBPP test overlaps: 0.
- The private test files are read only to compute hashes; they are never
  written to the SFT JSONL.

This is an exact-match audit, not a semantic near-duplicate audit. A
near-duplicate check would require an embedding pass and is not claimed here.

## Long examples

The training notebook tokenises every row with the Qwen tokenizer and drops
rows longer than 2,048 tokens before training. This prevents the assistant
completion from being silently truncated, especially for long C functions.
The v3 run kept **3 870 / 3 872** train rows (2 dropped) and **298 / 298**
validation rows.

## Regenerate

```bash
python research/01_benchmark/harness/scripts/build_sft_v3.py \
  --pilot-dir <pilot_dir> \
  --codexglue-dir <codexglue_dir> \
  --output-dir <out_dir> \
  --download
```

Outputs: `sft_v3_train.jsonl`, `sft_v3_validation.jsonl`, `manifest.json`,
`README.md`, `dataset-metadata.json`. The JSONL files are uploaded as the
private Kaggle dataset `merouanefaik/slm-sft-v3`; they are not committed to
this public repository.

## Honest limitations

- Templated bug descriptions mean a good F1 is evidence of label
  classification, not defect explanation.
- Identity refactoring targets mean a good pass@1 is evidence of format and
  behaviour preservation, not refactoring quality.
- Explanation targets are docstrings, so ROUGE-L measures docstring overlap,
  not a complete semantic explanation.
- The real-repository code-generation replay set may teach long functions and
  external-style code; it is a diversity measure, not a benchmark-matched
  training set.
- No v3 result should be reported until the six-task evaluation runs in the
  same sandbox as the base models.
