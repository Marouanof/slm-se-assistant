# SLM SFT v3 — seven-model comparison

Same prompts, same private tests and the same `sandbox_runner.py` for every run.
The first five model columns were recomputed locally with
`harness/scripts/compare_runs.py` on the saved outputs. The Qwen 3B SFT v3 and
Phi-4 SFT v3 columns are their Kaggle eval runs, which used the same harness and
sandbox; their metrics were not recomputed locally.

The Qwen v3 Kaggle numbers (pass@1 0.5165, refactoring 0.9833, unit tests
0.5412, explanation 0.2092, bug F1 0.0, completion 0.2651) match the local
recomputation exactly. The Qwen 1.5B base and Qwen 3B base `code_generation`
scores are 0.6074 and 0.7438 here, i.e. 1–2 examples above the earlier `0.6033`
/ `0.7397` values. The sandbox was re-run on the same saved outputs; the
ranking and routing are unchanged.

Phi-4 SFT v3 eval run:
`phi4mini_sft_v3_full_20261126-100023_a807098d310d_c706867f`. Its numeric
explanation win is not statistically robust; see the last section.

## code_generation

| metric | Qwen 1.5B base | Qwen 1.5B SFT v2 | Qwen 1.5B SFT v3 | Qwen 3B base | Qwen 3B SFT v3 | Phi-4 base | Phi-4 SFT v3 |
|---|---|---|---|---|---|---|---|
| pass@1 | 0.6074 | 0.5372 | 0.5165 | **0.7438** | 0.6322 | 0.6736 | 0.2975 |
| compile_ok | 0.9917 | 1.0000 | 0.9959 | 1.0000 | 0.9917 | 1.0000 | 0.8802 |

n = 242 problems per model.

## code_explanation

| metric | Qwen 1.5B base | Qwen 1.5B SFT v2 | Qwen 1.5B SFT v3 | Qwen 3B base | Qwen 3B SFT v3 | Phi-4 base | Phi-4 SFT v3 |
|---|---|---|---|---|---|---|---|
| rouge_l | 0.1179 | 0.1755 | 0.2092 | 0.1065 | 0.2093 | 0.1531 | **0.2209** |
| headings_ok | 1.0000 | 1.0000 | 0.9800 | 1.0000 | 0.9900 | 1.0000 | 1.0000 |

n = 100 problems per model.

## bug_detection

| metric | Qwen 1.5B base | Qwen 1.5B SFT v2 | Qwen 1.5B SFT v3 | Qwen 3B base | Qwen 3B SFT v3 | Phi-4 base | Phi-4 SFT v3 |
|---|---|---|---|---|---|---|---|
| f1 | 0.1818 | 0.0000 | 0.0000 | **0.5470** | 0.0000 | 0.4691 | 0.0000 |
| accuracy | 0.4600 | 0.5000 | 0.5000 | 0.4646 | 0.5000 | 0.5700 | 0.4900 |

n = 100 problems per model.

## code_refactoring

| metric | Qwen 1.5B base | Qwen 1.5B SFT v2 | Qwen 1.5B SFT v3 | Qwen 3B base | Qwen 3B SFT v3 | Phi-4 base | Phi-4 SFT v3 |
|---|---|---|---|---|---|---|---|
| pass@1 | 0.1000 | 0.9167 | **0.9833** | 0.0000 | 0.9667 | 0.6667 | 0.6000 |
| compile_ok | 0.6333 | 1.0000 | 1.0000 | 0.6500 | 1.0000 | 0.9667 | 0.8333 |

n = 60 problems per model.

## unit_test_generation

| metric | Qwen 1.5B base | Qwen 1.5B SFT v2 | Qwen 1.5B SFT v3 | Qwen 3B base | Qwen 3B SFT v3 | Phi-4 base | Phi-4 SFT v3 |
|---|---|---|---|---|---|---|---|
| valid_suite_rate | 0.0235 | 0.4588 | 0.5412 | 0.1176 | **0.6000** | 0.1059 | 0.3647 |
| mutation_kill_rate | 0.0000 | 0.9140 | 0.9286 | 1.0000 | 0.9389 | 1.0000 | 0.9505 |
| syntax_ok | 0.1647 | 0.9529 | 0.9882 | 0.7765 | 1.0000 | 0.7529 | 0.8941 |

n = 85 problems per model.

## code_completion

| metric | Qwen 1.5B base | Qwen 1.5B SFT v2 | Qwen 1.5B SFT v3 | Qwen 3B base | Qwen 3B SFT v3 | Phi-4 base | Phi-4 SFT v3 |
|---|---|---|---|---|---|---|---|
| exact_match | 0.2530 | 0.2048 | 0.2651 | 0.3253 | 0.3133 | **0.3494** | 0.3373 |
| edit_similarity | 0.6611 | 0.6330 | 0.6721 | 0.6893 | 0.7229 | 0.7500 | 0.7587 |

n = 83 problems per model.

## Reading

- **Qwen 3B SFT v3 is the best unit-test model**: 0.6000 valid suites (51/85;
  47/85 valid + kill-all), versus 0.5412 (46/85; 41/85) for the 1.5B v3 and
  0.3647 (31/85; 25/85) for Phi-4 SFT v3.
- **Qwen 1.5B SFT v3 remains the best refactoring model**: 0.9833 (59/60), one
  example above the 3B SFT (58/60). Phi-4 SFT v3 is 0.6000 (36/60), below Phi-4
  base (0.6667).
- **Explanation**: Phi-4 SFT v3 is numerically best at 0.2209, but a paired
  bootstrap over the 100 examples gives +0.0117 over Qwen 1.5B SFT v3 with a 95%
  CI of [-0.0029, +0.0263], which includes zero. The Qwen 1.5B v3 remains the
  selected model because it is not a robust win and uses about 3.3 GB versus
  about 8.0 GB for Phi-4 v3 on this task.
- **Phi-4 SFT v3 does not fix code_generation or bug_detection**: 0.2975
  (72/242) is 37.6 pts below Phi-4 base, and bug F1 is 0.0 (0 TP / 1 FP / 50 FN
  / 49 TN). Qwen 3B base remains the model for both.
- **Completion**: Phi-4 base remains best on exact match (0.3494); Phi-4 SFT v3
  ties its own v2 at 0.3373 and has slightly higher edit similarity (0.7587 vs
  0.7500).
- **Routing is unchanged**: Qwen 3B base for code_generation and bug_detection;
  Qwen 1.5B SFT v3 for refactoring and explanation; Qwen 3B SFT v3 adapter for
  unit tests; Phi-4 base for completion. Phi-4 SFT v3 is a documented negative
  result.
