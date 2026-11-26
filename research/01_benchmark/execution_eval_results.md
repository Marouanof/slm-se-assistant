# Execution-based evaluation (sandbox) — Phi-4 and Qwen base vs SFT

**Status:** computed locally on the saved model outputs (CPU only, no GPU quota used).
The same `harness/scripts/sandbox_runner.py` runs unchanged on Kaggle.

## Why this replaces the static metrics

The first comparison used *static* checks (`compile_ok`, `syntax_ok`, `exact_match`).
Those saturated at the base model:

| task | static metric | base | SFT v1 |
|---|---|---|---|
| code_generation | `compile_ok` | 1.0000 | 0.9545 |
| code_refactoring | `compile_ok` | 0.9667 | 0.9833 |
| unit_test_generation | `syntax_ok` | 0.7529 | 0.7765 |

A file can compile and still be functionally wrong. The sandbox actually
executes the generated code against the hidden reference tests.

## Sandbox design

`harness/scripts/sandbox_runner.py`

- **Isolation:** every program runs in a fresh `python -I` subprocess, never in the host interpreter.
- **Hard limits (POSIX / Kaggle):** `RLIMIT_CPU`, `RLIMIT_AS`, `RLIMIT_NPROC`,
  `RLIMIT_FSIZE`, `RLIMIT_CORE` + a wall-clock timeout.
- **Static pre-check:** rejects `os`, `sys`, `subprocess`, `socket`, `ctypes`,
  `eval`, `exec`, `open`, `__import__`, … before execution (defence in depth).
- **Deterministic:** same program → same verdict; temp file deleted afterwards.

Task adapters:

- **code_generation / code_refactoring:** `generated_code + reference_tests`
  (HumanEval+ appends `check(entry_point)`; MBPP+ runs its top-level assertion loop).
  `pass@1 = 1` iff the process exits 0.
- **unit_test_generation:** `canonical_solution + generated_tests`.
  A suite is **valid** iff it passes on the canonical solution; the suite is then
  run against every stored **mutant**. `mutation_kill_rate = killed / mutants`.
  A small pytest shim provides `pytest.raises` and the runner actually calls
  `def test_*()` functions (otherwise they are only defined and never run).

## Results

### code_generation (HumanEval+, 242 problems)

| model | pass@1 | passed |
|---|---|---|
| base Phi-4-mini | **0.6736** | 163 / 242 |
| SFT v1 (checkpoint-203) | 0.2727 | 66 / 242 |
| SFT v2 (checkpoint-398) | 0.2851 | 69 / 242 |

Top SFT v1 failures: `AssertionError` 35, `NameError: name 'List' is not defined` 16,
`syntax_error` 11, `wall_clock_timeout` 3.

### Signature fix (harness-level)

The dominant failure is not logic: the SFT model **renames the function** instead
of copying the stub signature (`has_close_elements` → `has_come_close_elements`).
Forcing the generated function name to the stub's `entry_point` before running
the tests recovers a large part of the regression:

| model | raw pass@1 | renamed outputs | recovered | pass@1 with signature forced |
|---|---|---|---|---|
| SFT v1 | 0.2727 | 87 | 30 | **0.3967** (96 / 242) |
| SFT v2 | 0.2851 | 101 | 51 | **0.4959** (120 / 242) |

The base model already copies the signature (242 / 242), so the fix is a no-op
for it. Even corrected, SFT v2 stays 18 pts below the base: the remaining
failures are genuine logic errors.

### code_refactoring (MBPP+, 60 problems)

| model | pass@1 (behaviour preserved) | passed |
|---|---|---|
| base Phi-4-mini | **0.6667** | 40 / 60 |
| SFT v1 | 0.4167 | 25 / 60 |
| SFT v2 | 0.4000 | 24 / 60 |

Top SFT v1 failures: renamed entry point (`tuple_to_dict` → `tuple_2_dict`,
`text_match_three` → missing, …), missing imports, syntax errors.

### unit_test_generation (MBPP+, 85 problems)

| model | valid suites (pass on canonical) | mutation kill rate (valid suites) | valid + kills all mutants |
|---|---|---|---|
| base Phi-4-mini | 9 / 85 = 0.1059 | 23 / 23 = 1.0000 | 9 / 85 = 0.1059 |
| SFT v1 | 23 / 85 = 0.2706 | 55 / 62 = 0.8871 | 20 / 85 = 0.2353 |
| SFT v2 | **33 / 85 = 0.3882** | 0.9444 aggregate (0.9858 per-problem) | **29 / 85 = 0.3412** |

SFT v2 is the best here: **3.7× more valid suites than the base** and, on the
valid suites, **94.4% of the mutants are killed** (aggregate). 34.1% of the
problems have a valid suite that kills every mutant.

## Zero-shot tasks (static metrics)

These three tasks are not in the SFT data; they measure forgetting.

| task | metric | base | SFT v1 | SFT v2 |
|---|---|---|---|---|
| code_explanation | ROUGE-L | **0.1531** | 0.1534 | 0.1272 |
| bug_detection | F1 | 0.4691 | **0.4902** | **0.0000** |
| code_completion | exact_match | **0.3494** | 0.3373 | 0.3373 |
| code_completion | edit_similarity | 0.7500 | 0.7662 | **0.7673** |

SFT v2 collapses `bug_detection` to the negative class (92/100 parseable
outputs are `has_bug=false`), a clear catastrophic-forgetting signal.

## Conclusion

SFT v2 fixes the v1 formatting problems but is **still not a net win**:

- ✅ `unit_test_generation`: 10.6% → **38.8%** valid suites.
- ❌ `code_generation`: 67.4% → 28.5% raw (49.6% with the signature forced).
- ❌ `code_refactoring`: 66.7% → 40.0%.
- ❌ `bug_detection`: F1 0.47 → 0.00.
- ⚪ `code_completion` / `code_explanation`: flat or slightly down.

It is shippable only with **per-task routing**: base model for the five tasks,
SFT v2 for `unit_test_generation`. See `sft_v2_findings.md`.

## Root causes (SFT v1)

1. **Stray `|` token in every training completion.** All 900 completions ended
   with `|<|endoftext|>`; the model learned to emit `|` before stopping.
2. **Prompt/template mismatch.** Training used a generic system prompt and a
   different user template than `prompt_registry.py`, so the model did not learn
   the evaluation distribution.
3. **Completion format mismatch.** The harness asks for fenced code blocks and
   complete functions including imports; the pilot completions were unfenced and
   often omitted `typing`/`math` imports.
4. **Small data + high LR.** 300 examples/task, LR 2e-4, 3 epochs; val loss was
   best at epoch 1 (0.5710) and degraded afterwards (0.6511) → overfitting.

## SFT v2 — dataset, training, evaluation

`harness/scripts/build_sft_v2.py` + Kaggle dataset `merouanefaik/slm-sft-v2`:

- Every row is rebuilt with the **exact** `SYSTEM_PROMPTS` / `USER_TEMPLATES`
  from `prompt_registry.py`.
- The chat is rendered with the tokenizer's own `apply_chat_template`
  (training == inference byte-for-byte).
- Completions are normalised: fenced code where the harness asks for it, the
  stray `|` removed, imports preserved, and code_generation inputs converted to
  HumanEval-style stubs (imports + signature + docstring).
- 796 train / 89 validation examples across the 3 canonical-answer tasks.
- Training: 2 epochs, LR 1e-4, per-epoch checkpoints.

### Training result

| epoch | eval_loss v1 | eval_loss v2 |
|---|---|---|
| 1 | 0.5710 | **0.3864** |
| 2 | 0.5932 | **0.3745** (best) |
| 3 | 0.6511 | — |

The aligned data removes the v1 overfitting: v2 validation loss keeps improving
at epoch 2 instead of degrading. Best adapter = `checkpoint-398`.

The `phi4-sft-v2-eval` notebook mounts the training output directly through
`kernel_sources`, picks `checkpoint-398` from `train_history.json`, and scores
all 6 tasks with the embedded execution sandbox (no model download).
**Status: COMPLETE** — the results are the `SFT v2` rows above.

## Qwen2.5-Coder-1.5B SFT v2

Same `slm-sft-v2` dataset (2 epochs, best `checkpoint-199`, eval_loss 0.3156),
evaluated on Kaggle T4 with the same prompts and the same sandbox. The eval
run took **57 min** after fixing the attention backend (`sdpa`) and making the
EOS tokens explicit (`<|im_end|>` / `<|endoftext|>`).

| task | metric | Qwen SFT v2 |
|---|---|---|
| code_generation | pass@1 | **0.5372** (130/242) |
| code_refactoring | pass@1 | **0.9167** (55/60) |
| unit_test_generation | valid suites | **0.4588** (39/85) |
| unit_test_generation | mutation kill (aggregate) | 0.9140 |
| unit_test_generation | valid + kills all mutants | 0.4118 (35/85) |
| code_explanation | ROUGE-L | 0.1755 |
| bug_detection | F1 | 0.0000 |
| code_completion | exact_match | 0.2048 |
| code_completion | edit_similarity | 0.6330 |

Key difference with Phi-4 v2: **Qwen copies the stub signature perfectly**
(242/242 function names correct), so its `code_generation` failures are genuine
logic errors, not renames. `bug_detection` still collapses to the negative class
(100/100 `has_bug=false`, 100% parseable). `unit_test_generation` has 39 valid
suites and 4 syntax errors (4 outputs hit the 512-token cap).

### Qwen base vs SFT v2

Execution metrics recomputed with the same sandbox for both runs.

| task | metric | Qwen base | Qwen SFT v2 |
|---|---|---|---|
| code_generation | pass@1 | **0.6033** (146/242) | 0.5248 (127/242) |
| code_refactoring | pass@1 | 0.1000 (6/60) | **0.9167** (55/60) |
| unit_test_generation | valid suites | 0.0235 (2/85) | **0.4588** (39/85) |
| unit_test_generation | mutation kill (aggregate) | 0.0000 (0/2) | **0.9140** (85/93) |
| unit_test_generation | valid + kills all mutants | 0/85 | **35/85** |
| code_explanation | ROUGE-L | 0.1179 | **0.1755** |
| bug_detection | F1 | **0.1818** | 0.0000 |
| code_completion | exact_match | **0.2530** | 0.2048 |
| code_completion | edit_similarity | **0.6611** | 0.6330 |

The local SFT code_generation is 0.5248 vs 0.5372 in the Kaggle run (3 examples,
platform/sandbox noise). The base number uses the same local sandbox, so the
−7.9 pt regression is real. The refactoring gain is mostly format compliance:
the base Qwen puts `### Changes` prose inside the fence, while the SFT model
emits a clean function.

## Qwen2.5-Coder-3B base (zero-shot)

Same prompts, private tests and sandbox. No SFT.

| task | metric | Qwen 3B base |
|---|---|---|
| code_generation | pass@1 | **0.7397** (179/242) |
| code_refactoring | pass@1 | 0.0000 (0/60) |
| unit_test_generation | valid suites | 0.1176 (10/85) |
| unit_test_generation | mutation kill (aggregate) | 1.0000 (19/19) |
| code_explanation | ROUGE-L | 0.1065 |
| bug_detection | F1 | **0.5470** |
| code_completion | exact_match | 0.3253 |
| code_completion | edit_similarity | 0.6893 |

- Best `code_generation` (0.7397) and `bug_detection` (F1 0.5470) of the project.
- `code_refactoring` 0.0 is the same format failure as the 1.5B base: the
  `### Changes` prose is inside the fence, so no test passes. The 1.5B SFT v2
  (0.9167) is the fix.
- Unit tests: only 10/85 valid suites, but 19/19 mutants killed on those
  suites; coverage is too low versus the 1.5B SFT (39/85 valid, 0.914
  aggregate).
- Explanation (0.1065) is below Phi-4 base (0.1531) and 1.5B SFT (0.1755);
  completion (0.3253) is slightly below Phi-4 base (0.3494).
- Cost: ~20–80% slower than the 1.5B depending on the task, ~8.5 GB VRAM.

## Qwen2.5-Coder-1.5B SFT v3 (six tasks)

Dataset `slm-sft-v3`: 3 872 train / 298 validation, all six tasks. Training:
2 epochs, 1 936 steps, 55.9 min, Unsloth 4-bit, LoRA r=16/alpha=32. Best
`checkpoint-968` (eval_loss 0.4206). Eval: same prompts/private tests/sandbox,
`checkpoint-968` selected automatically.

| task | metric | Qwen SFT v3 | Qwen SFT v2 | delta |
|---|---|---|---|---|
| code_generation | pass@1 | 0.5165 (125/242) | 0.5372 (130/242) | −0.0207 |
| code_refactoring | pass@1 | **0.9833** (59/60) | 0.9167 (55/60) | **+0.0666** |
| unit_test_generation | valid suites | **0.5412** (46/85) | 0.4588 (39/85) | **+0.0824** |
| unit_test_generation | mutation kill (aggregate) | 0.9286 (104/112) | 0.9140 (85/93) | +0.0146 |
| unit_test_generation | valid + kills all mutants | 0.4824 (41/85) | 0.4118 (35/85) | **+0.0706** |
| code_explanation | ROUGE-L | **0.2092** | 0.1755 | **+0.0337** |
| bug_detection | F1 | 0.0000 | 0.0000 | 0.0000 |
| code_completion | exact_match | 0.2651 (22/83) | 0.2048 (17/83) | **+0.0603** |
| code_completion | edit_similarity | 0.6721 | 0.6330 | +0.0391 |

The v3 ZIP SHA256 is
`269615a681c0674e8200aa0fb5fa4c0afe0fbb799eb81d9b8ae1f7e4ba10f4a6`
(100 159 bytes); the 14 internal checksums verified. The local
`compare_runs.py` recomputation matches the v3 numbers exactly
(`comparison_qwen_v3.md`). It reports 0.6074 / 0.7438 for the 1.5B / 3B base
code_generation, 1–2 examples above the earlier values; the ranking and routing
are unchanged. `bug_detection` is still 100/100 `has_bug=false` with valid JSON,
so the 1.5B model did not learn the C defect signal. Qwen 3B base remains the
bug_detection model.

## Qwen2.5-Coder-3B SFT v3 (six tasks)

Same v3 dataset, prompts, private tests and sandbox as the 1.5B v3. Training:
2 epochs, 1 936 steps, **80.3 min**, `train_loss` 0.5404; eval **76.5 min**; best
`checkpoint-968` with **eval_loss 0.3949** (epoch 2 = 0.4048). Eval ZIP 97 152
bytes, SHA256
`9f626900b48816744bdcc4298af93c6a4f0b11dc3a2ea6497ce7436c5765bb89`; all 14
internal checksums verified.

| task | metric | 3B SFT v3 | 3B base | 1.5B SFT v3 |
|---|---|---|---|---|
| code_generation | pass@1 | 0.6322 (153/242) | **0.7438** (180/242) | 0.5165 (125/242) |
| code_refactoring | pass@1 | 0.9667 (58/60) | 0.0000 | **0.9833** (59/60) |
| unit_test_generation | valid suites | **0.6000** (51/85) | 0.1176 (10/85) | 0.5412 (46/85) |
| unit_test_generation | mutation kill (aggregate) | 0.9389 (123/131) | 1.0000 (19/19) | 0.9286 (104/112) |
| unit_test_generation | valid + kills all mutants | **0.5529** (47/85) | 0.1176 (10/85) | 0.4824 (41/85) |
| code_explanation | ROUGE-L | **0.2093** | 0.1065 | 0.2092 |
| bug_detection | F1 | 0.0000 | **0.5470** | 0.0000 |
| code_completion | exact_match | 0.3133 (26/83) | 0.3253 | 0.2651 (22/83) |

- **Unit tests are the win**: 51/85 valid suites and 47/85 that also kill every
  mutant, versus 46/85 and 41/85 for the 1.5B v3. This is the best unit-test
  model of the project.
- **Explanation is a tie** (0.2093 vs 0.2092); extra 3B capacity does not help
  ROUGE-L.
- **Refactoring** is one example lower than the 1.5B v3 (58/60 vs 59/60).
- **Code generation** is better than the 1.5B v3 but still 11.2 pts below the
  3B base. **Bug detection remains collapsed** at F1 0.0 (0 TP / 0 FP / 50 FN /
  50 TN, valid JSON). The 3B SFT did not recover the two tasks it was meant to
  fix.
- **Completion** is below Phi-4 base and the 3B base.
- Cost: ~1.3–1.7× slower than the 1.5B v3 on generative tasks and ~8.5 GB VRAM
  vs ~4.8 GB.

## Final routing

Best model per task across Phi-4 base, Phi-4 SFT v2, Qwen 1.5B SFT v2/v3,
Qwen 3B base and Qwen 3B SFT v3 (ties broken by cost):

| task | best model | metric | runner-up |
|---|---|---|---|
| code_generation | **Qwen 3B base** | **0.7438** | Phi-4 base 0.6736 |
| code_refactoring | **Qwen 1.5B SFT v3** | **0.9833** | Qwen 3B SFT v3 0.9667 |
| unit_test_generation | **Qwen 3B SFT v3** | **0.6000** | Qwen 1.5B SFT v3 0.5412 |
| code_explanation | **Qwen 1.5B SFT v3** | **0.2092** (tie with 3B SFT 0.2093; 1.5B cheaper) | Qwen 1.5B SFT v2 0.1755 |
| bug_detection | **Qwen 3B base** | **0.5470** | Phi-4 base 0.4691 |
| code_completion | **Phi-4-mini base** | **0.3494** | Qwen 3B base 0.3253 |

**Recommended deployment:** Qwen 3B base for `code_generation` and
`bug_detection`; Qwen 1.5B SFT v3 for `code_refactoring` and
`code_explanation`; the Qwen 3B SFT v3 adapter for `unit_test_generation` only;
Phi-4 base for `code_completion`. The 3B SFT adapter shares the already-loaded
3B base, so it adds no base weights. It buys 5/85 valid suites and 6/85
valid+kill-all over the 1.5B v3, at ~1.7× unit-test latency.

**3-model simplification (current routing):** drop the 3B SFT adapter and let
the 1.5B v3 handle unit tests too. Unit tests fall from 0.6000 to 0.5412 (5
problems), but this is faster, lower-VRAM and unchanged elsewhere. This is the
default when simplicity or cost dominates.

**Alternative with two base weights:** Qwen 3B base for code_generation,
bug_detection and completion (0.3253 vs 0.3494, −2.4 pts), with the 3B SFT
adapter for refactoring, unit tests and explanation. This drops the 1.5B and
Phi-4, loses one refactoring example, gains five unit problems and ties
explanation.

The 3B SFT did **not** recover code_generation or bug_detection, so the 3B base
remains the model for those two tasks. The 3B SFT is a targeted unit-test
upgrade, not a replacement for the 3B base.
