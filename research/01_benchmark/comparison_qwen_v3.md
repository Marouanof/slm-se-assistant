# Qwen SFT v3 — six-model comparison

Same prompts, same private tests and the same `sandbox_runner.py` for every run.
The first five models were recomputed locally with
`harness/scripts/compare_runs.py` on the saved outputs. The Qwen 3B SFT v3
column is its Kaggle eval run (`qwen3_sft_v3_full_20261126-034405_...`), which
used the same harness and sandbox; its metrics were not recomputed locally.

The v3 Kaggle numbers (pass@1 0.5165, refactoring 0.9833, unit tests 0.5412,
explanation 0.2092, bug F1 0.0, completion 0.2651) match the local
recomputation exactly. The Qwen 1.5B base and Qwen 3B base `code_generation`
scores are 0.6074 and 0.7438 here, i.e. 1–2 examples above the earlier `0.6033`
/ `0.7397` values. The sandbox was re-run on the same saved outputs; the
ranking and routing are unchanged.

## code_generation

| metric | Qwen 1.5B base | Qwen 1.5B SFT v2 | Qwen 1.5B SFT v3 | Qwen 3B base | Qwen 3B SFT v3 | Phi-4 base |
|---|---|---|---|---|---|---|
| pass@1 | 0.6074 | 0.5372 | 0.5165 | 0.7438 | 0.6322 | 0.6736 |
| compile_ok | 0.9917 | 1.0000 | 0.9959 | 1.0000 | 0.9917 | 1.0000 |

n = 242 problems per model.

## code_explanation

| metric | Qwen 1.5B base | Qwen 1.5B SFT v2 | Qwen 1.5B SFT v3 | Qwen 3B base | Qwen 3B SFT v3 | Phi-4 base |
|---|---|---|---|---|---|---|
| rouge_l | 0.1179 | 0.1755 | 0.2092 | 0.1065 | 0.2093 | 0.1531 |
| headings_ok | 1.0000 | 1.0000 | 0.9800 | 1.0000 | 0.9900 | 1.0000 |

n = 100 problems per model.

## bug_detection

| metric | Qwen 1.5B base | Qwen 1.5B SFT v2 | Qwen 1.5B SFT v3 | Qwen 3B base | Qwen 3B SFT v3 | Phi-4 base |
|---|---|---|---|---|---|---|
| f1 | 0.1818 | 0.0000 | 0.0000 | 0.5470 | 0.0000 | 0.4691 |
| accuracy | 0.4600 | 0.5000 | 0.5000 | 0.4646 | 0.5000 | 0.5700 |

n = 100 problems per model.

## code_refactoring

| metric | Qwen 1.5B base | Qwen 1.5B SFT v2 | Qwen 1.5B SFT v3 | Qwen 3B base | Qwen 3B SFT v3 | Phi-4 base |
|---|---|---|---|---|---|---|
| pass@1 | 0.1000 | 0.9167 | 0.9833 | 0.0000 | 0.9667 | 0.6667 |
| compile_ok | 0.6333 | 1.0000 | 1.0000 | 0.6500 | 1.0000 | 0.9667 |

n = 60 problems per model.

## unit_test_generation

| metric | Qwen 1.5B base | Qwen 1.5B SFT v2 | Qwen 1.5B SFT v3 | Qwen 3B base | Qwen 3B SFT v3 | Phi-4 base |
|---|---|---|---|---|---|---|
| valid_suite_rate | 0.0235 | 0.4588 | 0.5412 | 0.1176 | 0.6000 | 0.1059 |
| mutation_kill_rate | 0.0000 | 0.9140 | 0.9286 | 1.0000 | 0.9389 | 1.0000 |
| syntax_ok | 0.1647 | 0.9529 | 0.9882 | 0.7765 | 1.0000 | 0.7529 |

n = 85 problems per model.

## code_completion

| metric | Qwen 1.5B base | Qwen 1.5B SFT v2 | Qwen 1.5B SFT v3 | Qwen 3B base | Qwen 3B SFT v3 | Phi-4 base |
|---|---|---|---|---|---|---|
| exact_match | 0.2530 | 0.2048 | 0.2651 | 0.3253 | 0.3133 | 0.3494 |
| edit_similarity | 0.6611 | 0.6330 | 0.6721 | 0.6893 | 0.7229 | 0.7500 |

n = 83 problems per model.

## Reading

- **Qwen 3B SFT v3 is the best unit-test model**: 0.6000 valid suites (51/85;
  47/85 valid + kill-all), versus 0.5412 (46/85; 41/85) for the 1.5B v3 and
  0.1176 (10/85) for the 3B base.
- **Qwen 1.5B SFT v3 remains the best refactoring model**: 0.9833 (59/60),
  one example above the 3B SFT (58/60).
- **Explanation is a tie**: 3B SFT 0.2093 vs 1.5B v3 0.2092; the 1.5B is
  cheaper, so the recommended deployment keeps it for that task.
- **The 3B SFT does not fix code_generation or bug_detection**: 0.6322 (153/242)
  is below the 3B base 0.7438, and bug_detection is F1 0.0 (100/100
  `has_bug=false`, valid JSON). Qwen 3B base remains the model for both.
- **Completion**: 3B SFT 0.3133 is better than the 1.5B v3 (0.2651) but below
  the 3B base (0.3253) and Phi-4 base (0.3494).
- The 3B SFT is a targeted unit-test upgrade. The 3-model routing (3B base,
  1.5B v3, Phi-4) is unchanged if the adapter is omitted; adding it for unit
  tests buys 5/85 valid suites at ~1.7× unit-test latency.
