# Qwen 1.5B SFT v3 — five-model comparison

Same prompts, same private tests and the same `sandbox_runner.py` for every run.
Execution metrics were recomputed locally with `harness/scripts/compare_runs.py`
on the saved outputs. The v3 Kaggle numbers (pass@1 0.5165, refactoring 0.9833,
unit tests 0.5412, explanation 0.2092, bug F1 0.0, completion 0.2651) match this
local recomputation exactly.

The Qwen 1.5B base and Qwen 3B base `code_generation` scores are 0.6074 and
0.7438 here, i.e. 1–2 examples above the earlier `0.6033` / `0.7397` values.
The sandbox was re-run on the same saved outputs; the ranking and routing are
unchanged.

## code_generation

| metric | Qwen 1.5B base | Qwen 1.5B SFT v2 | Qwen 1.5B SFT v3 | Qwen 3B base | Phi-4 base |
|---|---|---|---|---|---|
| pass@1 | 0.6074 | 0.5372 | 0.5165 | 0.7438 | 0.6736 |
| compile_ok | 0.9917 | 1.0000 | 0.9959 | 1.0000 | 1.0000 |

n = 242 problems per model.

## code_explanation

| metric | Qwen 1.5B base | Qwen 1.5B SFT v2 | Qwen 1.5B SFT v3 | Qwen 3B base | Phi-4 base |
|---|---|---|---|---|---|
| rouge_l | 0.1179 | 0.1755 | 0.2092 | 0.1065 | 0.1531 |
| headings_ok | 1.0000 | 1.0000 | 0.9800 | 1.0000 | 1.0000 |

n = 100 problems per model.

## bug_detection

| metric | Qwen 1.5B base | Qwen 1.5B SFT v2 | Qwen 1.5B SFT v3 | Qwen 3B base | Phi-4 base |
|---|---|---|---|---|---|
| f1 | 0.1818 | 0.0000 | 0.0000 | 0.5470 | 0.4691 |
| accuracy | 0.4600 | 0.5000 | 0.5000 | 0.4646 | 0.5700 |

n = 100 problems per model.

## code_refactoring

| metric | Qwen 1.5B base | Qwen 1.5B SFT v2 | Qwen 1.5B SFT v3 | Qwen 3B base | Phi-4 base |
|---|---|---|---|---|---|
| pass@1 | 0.1000 | 0.9167 | 0.9833 | 0.0000 | 0.6667 |
| compile_ok | 0.6333 | 1.0000 | 1.0000 | 0.6500 | 0.9667 |

n = 60 problems per model.

## unit_test_generation

| metric | Qwen 1.5B base | Qwen 1.5B SFT v2 | Qwen 1.5B SFT v3 | Qwen 3B base | Phi-4 base |
|---|---|---|---|---|---|
| valid_suite_rate | 0.0235 | 0.4588 | 0.5412 | 0.1176 | 0.1059 |
| mutation_kill_rate | 0.0000 | 0.9140 | 0.9286 | 1.0000 | 1.0000 |
| syntax_ok | 0.1647 | 0.9529 | 0.9882 | 0.7765 | 0.7529 |

n = 85 problems per model.

## code_completion

| metric | Qwen 1.5B base | Qwen 1.5B SFT v2 | Qwen 1.5B SFT v3 | Qwen 3B base | Phi-4 base |
|---|---|---|---|---|---|
| exact_match | 0.2530 | 0.2048 | 0.2651 | 0.3253 | 0.3494 |
| edit_similarity | 0.6611 | 0.6330 | 0.6721 | 0.6893 | 0.7500 |

n = 83 problems per model.

## Reading

- v3 is the best model on **code_refactoring (0.9833)**, **unit_test_generation
  (0.5412 valid suites, 0.9286 mutation kill)** and **code_explanation (0.2092
  ROUGE-L)**. It beats v2 on all four tasks where v2 was competitive.
- v3 **code_generation (0.5165)** is still below Qwen 3B base (0.7438) and the
  1.5B base (0.6074); the six-task data did not fix that regression.
- v3 **bug_detection stays at F1 0.0** (100/100 `has_bug=false`, valid JSON).
  Qwen 3B base remains the bug_detection model (0.5470).
- v3 **code_completion (0.2651 exact)** improves over v2 but stays below Phi-4
  base (0.3494) and Qwen 3B base (0.3253).
