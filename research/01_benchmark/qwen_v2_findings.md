# Qwen2.5-Coder-1.5B SFT v2 — findings

> Historical. The six-task v3 adapter improves `code_refactoring`,
> `unit_test_generation`, `code_explanation` and `code_completion`; see
> `qwen_v3_findings.md` for the current numbers and routing.

## Setup

- Same harness-aligned `slm-sft-v2` dataset as Phi-4 (796 train / 89 validation,
  3 canonical-answer tasks: code_generation, unit_test_generation,
  code_completion).
- Training: 2 epochs, LR 1e-4, LoRA r=16 / alpha=32, batch 1 × grad-accum 4,
  max_seq_len 2048, Unsloth 4-bit.
- Best checkpoint: **checkpoint-199** (eval_loss **0.3156**; epoch 2 = 0.3439,
  overfitting). The eval notebook selects it automatically from
  `train_history.json`.
- Evaluation: Kaggle T4, FP16 base + PEFT adapter, `attn_implementation="sdpa"`,
  explicit `eos_token_id=[151645, 151643]`, sandboxed execution.

The first eval attempt used `eager` attention (copied from Phi-4) and no explicit
EOS, so it generated up to 512 tokens per example and projected 6–7 h. The fixed
run completed in **57 min** (1.3–8.6 s/example depending on the task).

## Results

| task | metric | Qwen SFT v2 |
|---|---|---|
| code_generation | pass@1 | **0.5372** (130/242) |
| code_refactoring | pass@1 | **0.9167** (55/60) |
| unit_test_generation | valid suites | **0.4588** (39/85) |
| unit_test_generation | mutation kill (mean on valid) | 0.9487 |
| unit_test_generation | mutation kill (aggregate) | 0.9140 |
| unit_test_generation | valid + kills all mutants | 0.4118 (35/85) |
| code_explanation | ROUGE-L | 0.1755 |
| bug_detection | F1 | 0.0000 |
| code_completion | exact_match | 0.2048 |
| code_completion | edit_similarity | 0.6330 |

ZIP SHA256 verified: `3d4411f7…ca6733`; all 14 result files match
`SHA256SUMS.txt`.

## Signatures: no rename failure

Qwen SFT copies the stub signature **242/242** times. The base model is also
good (239 correct, 2 syntax errors, 1 typo `check_occurences`). This is the
opposite of Phi-4 v2, where 102/242 outputs renamed the function; the signature
fix is therefore a no-op for Qwen and is not needed in its eval.

The 112 `code_generation` failures are genuine logic errors: 25 AssertionError,
6 ValueError, 4 IndexError, 4 TypeError, 2 AttributeError, 1 NameError,
1 RecursionError, plus assertion failures whose tail did not expose a typed
exception.

## Zero-shot behaviour

- `bug_detection` collapses: **100/100** outputs are `has_bug=false`, 100%
  parseable, F1 0.0 (base Qwen: F1 0.1818).
- `code_completion` regresses slightly: exact 0.2048 vs 0.253, edit 0.6330 vs
  0.6611.
- `code_explanation` **improves**: ROUGE-L 0.1755 vs 0.1179 (+5.8 pts).

## Unit tests

- 39/85 valid suites (45.9%), 4 syntax errors, 4 outputs hit the 512-token cap.
- 0.9487 mean mutation kill on valid suites, 0.9140 aggregate; 35/85 problems
  have a valid suite that kills every mutant.
- Compared with Phi-4 v2 (33/85 valid, 0.9858 mean, 0.9444 aggregate, 29/85
  valid+all), Qwen produces **more valid suites**; Phi-4 kills slightly more
  mutants per valid suite.

## Why refactoring jumps to 0.9167

The base Qwen often puts a `### Changes` prose block **inside** the code fence
(` ```python\n### Changes\n- ...`), so the extracted program does not compile
(38/60 `compile_ok`) or contains no code at all (53/60 `changed`). Qwen SFT v2
outputs a clean fenced function (60/60 compile, 60/60 changed). The gain is
mostly **output-format compliance**, not a different refactoring algorithm.

## Speed

| task | mean latency | mean visible tokens/s | mean output tokens |
|---|---|---|---|
| code_generation | 4.37 s | 13.83 | 60.8 |
| code_refactoring | 3.56 s | 13.81 | 49.5 |
| unit_test_generation | 8.59 s | 14.00 | 121.4 |
| code_explanation | 7.46 s | 14.12 | 105.5 |
| bug_detection | 2.17 s | 12.61 | 27.0 |
| code_completion | 1.26 s | 12.55 | 16.8 |

`tokens/s` counts visible (detokenized) tokens, not generated tokens; it is
lower than the base Qwen run (27.3) partly because the SFT outputs are longer
and the metric excludes special tokens.

## Base vs SFT v2 (same sandbox)

| task | metric | Qwen base | Qwen SFT v2 |
|---|---|---|---|
| code_generation | pass@1 | **0.6033** (146/242) | 0.5248 (127/242) |
| code_refactoring | pass@1 | 0.1000 (6/60) | **0.9167** (55/60) |
| unit_test_generation | valid suites | 0.0235 (2/85) | **0.4588** (39/85) |
| unit_test_generation | mutation kill (aggregate) | 0.0000 (0/2) | **0.9140** (85/93) |
| code_explanation | ROUGE-L | 0.1179 | **0.1755** |
| bug_detection | F1 | **0.1818** | 0.0000 |
| code_completion | exact_match | **0.2530** | 0.2048 |

The local SFT code_generation is 0.5248 vs 0.5372 in the Kaggle run; the
3-example gap is platform/sandbox noise. The base number uses the same local
sandbox, so the −7.9 pt regression is real.

## Routing implications

Qwen 1.5B SFT v2 is the best model for:

- `code_refactoring` (0.9167),
- `unit_test_generation` (0.4588 valid suites),
- `code_explanation` (0.1755 ROUGE-L).

Qwen 3B base is the best for:

- `code_generation` (0.7397),
- `bug_detection` (F1 0.5470).

Phi-4 base remains the best for:

- `code_completion` (0.3494).

The final routing table is in `comparison_qwen_v2.md`: three models. The 3B is
base-only; a 3B SFT was later run and is documented in
`qwen3_sft_v3_findings.md`.
