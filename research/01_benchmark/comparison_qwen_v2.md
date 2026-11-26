# Qwen2.5-Coder-1.5B — base vs SFT v2

> Historical comparison. The v3 adapter supersedes SFT v2 on `code_refactoring`,
> `unit_test_generation` and `code_explanation`; see `qwen_v3_findings.md` and
> `execution_eval_results.md` for the current routing.

Same prompts, same private tests, same sandbox (`sandbox_runner.py`). The SFT run
uses `checkpoint-199` (eval_loss 0.3156). Execution metrics are recomputed
locally for **both** runs, so the comparison is methodologically identical.

## Execution tasks

| task | metric | Qwen base | Qwen SFT v2 | delta |
|---|---|---|---|---|
| code_generation | pass@1 | **0.6033** (146/242) | 0.5248 (127/242) | −0.0785 |
| code_refactoring | pass@1 | 0.1000 (6/60) | **0.9167** (55/60) | +0.8167 |
| unit_test_generation | valid suites | 0.0235 (2/85) | **0.4588** (39/85) | +0.4353 |
| unit_test_generation | mutation kill (aggregate) | 0.0000 (0/2) | **0.9140** (85/93) | +0.9140 |
| unit_test_generation | valid + kills all mutants | 0/85 | **35/85** | +35 |

The SFT code_generation number is 0.5248 in the local recomputation and 0.5372
(130/242) in the Kaggle run; the 3-example gap is platform/sandbox noise. The
base number (0.6033) is the same sandbox, so the regression is real.

## Zero-shot / static tasks

| task | metric | Qwen base | Qwen SFT v2 | delta |
|---|---|---|---|---|
| code_explanation | ROUGE-L | 0.1179 | **0.1755** | +0.0576 |
| bug_detection | F1 | **0.1818** | 0.0000 | −0.1818 |
| code_completion | exact_match | **0.2530** | 0.2048 | −0.0482 |
| code_completion | edit_similarity | **0.6611** | 0.6330 | −0.0281 |

## Reading

- **Refactoring (+81.7 pts)** is mostly a format win. The base Qwen puts a
  `### Changes` prose block **inside** the code fence, so only 38/60 outputs
  compile and 6/60 pass the tests. Qwen SFT v2 emits a clean fenced function
  (60/60 compile, 55/60 pass).
- **Unit tests (+43.5 pts)**: base Qwen writes almost no valid suite (2/85);
  SFT v2 reaches 39/85 valid, 91.4% aggregate mutation kill.
- **Code generation (−7.9 pts)**: Qwen SFT copies the signature perfectly
  (242/242), so the regression is genuine logic degradation, not formatting.
- **Bug detection (−18.2 pts)**: SFT collapses to the negative class
  (100/100 `has_bug=false`).
- **Explanation (+5.8 pts)** and **completion (−4.8 pts exact)** are small
  changes; explanation improves, completion slightly regresses.

## Final routing (best model per task)

| task | best model | metric | runner-up |
|---|---|---|---|
| code_generation | **Qwen 3B base** | **0.7397** | Phi-4 base 0.6736 |
| code_refactoring | **Qwen 1.5B SFT v2** | **0.9167** | Phi-4 base 0.6667 |
| unit_test_generation | **Qwen 1.5B SFT v2** | **0.4588** | Phi-4 SFT v2 0.3882 |
| code_explanation | **Qwen 1.5B SFT v2** | **0.1755** | Phi-4 base 0.1531 |
| bug_detection | **Qwen 3B base** | **0.5470** | Phi-4 base 0.4691 |
| code_completion | **Phi-4-mini base** | **0.3494** | Qwen 3B base 0.3253 |

Three models: Qwen 3B base (2 tasks), Qwen 1.5B SFT v2 (3), Phi-4 base (1).
The 3B is base-only; a 3B SFT is the best future ablation. A 2-model
simplification is possible: Qwen 3B base for code_generation, bug_detection and
completion (0.3253 vs 0.3494, −2.4 pts), Qwen 1.5B SFT for the other three.
This supersedes the earlier "base for 5 tasks, SFT for unit_test only"
recommendation.
