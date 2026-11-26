# Qwen2.5-Coder-3B SFT v3 — findings

**Status: training and six-task evaluation complete.** The 3B SFT is a quality
upgrade for unit-test generation, but it does **not** fix bug_detection and does
not beat the 3B base on code_generation.

## Setup

- Base model: `Qwen/Qwen2.5-Coder-3B-Instruct` (4-bit QLoRA, Unsloth).
- Dataset: `merouanefaik/slm-sft-v3`, **3 872 train / 298 validation**, six tasks.
- Same prompts, private tests and sandbox as the 1.5B v3 and base runs.
- Training: 2 epochs, LR 1e-4, LoRA r=16 / alpha=32, batch 1 × grad-accum 4,
  max_seq_len 2048, seed 42.
- Kept rows: **3 870 / 3 872** train (2 dropped), **298 / 298** validation.
- Best checkpoint: **checkpoint-968**, `eval_loss` **0.3949** (epoch 2 = 0.4048).
- Training: **1 936 steps**, `train_runtime` **4 821 s (80,3 min)**,
  `train_loss` **0.5404**.
- Training ZIP sidecar SHA256:
  `2ee0438c377b1916df419183a531e41f295a46c8be8faf2e7017505104bf75fe`.
  The large ZIP was not downloaded locally; the eval mounted the training output.
- Eval ZIP SHA256:
  `9f626900b48816744bdcc4298af93c6a4f0b11dc3a2ea6497ce7436c5765bb89`
  (97 152 bytes); 14 internal checksums verified.
- Eval kernel: `merouanefaik/qwen3-sft-v3-eval`, adapter `checkpoint-968`,
  `sandbox_subprocess`; eval wall time **4 590 s (76.5 min)**.

## Results

| task | metric | 3B SFT v3 | 3B base | 1.5B SFT v3 |
|---|---|---:|---:|---:|
| code_generation | pass@1 | 0.6322 (153/242) | **0.7438** (180/242) | 0.5165 |
| code_refactoring | pass@1 | 0.9667 (58/60) | 0.0000 | **0.9833** (59/60) |
| unit_test_generation | valid suites | **0.6000** (51/85) | 0.1176 (10/85) | 0.5412 (46/85) |
| unit_test_generation | mutation kill (aggregate) | 0.9389 (123/131) | 1.0000 (19/19) | 0.9286 (104/112) |
| unit_test_generation | valid + kills all mutants | **0.5529** (47/85) | 0.1176 (10/85) | 0.4824 (41/85) |
| code_explanation | ROUGE-L | **0.2093** | 0.1065 | 0.2092 |
| bug_detection | F1 | 0.0000 | **0.5470** | 0.0000 |
| code_completion | exact_match | 0.3133 (26/83) | 0.3253 | 0.2651 |
| code_completion | edit_similarity | 0.7229 | 0.6893 | 0.6721 |

The 3B SFT executed 240/242 code_generation rows (one `forbidden_call:compile`,
one syntax error) and 59/60 refactoring rows (one `forbidden_call:compile`);
syntax_ok is 1.0 on unit tests.
`bug_detection` is again 100/100 `has_bug=false` with valid JSON.

## Reading

- **Unit tests are the clear win**: 51/85 valid suites vs 46/85 for the 1.5B v3
  and 10/85 for the 3B base; 47/85 suites kill every mutant vs 41/85 for the
  1.5B v3. This is the best unit-test model of the project by a meaningful
  margin (5 problems, +5.9 pts).
- **Explanation is a tie**: 0.2093 vs 0.2092 for the 1.5B v3. The extra 3B
  capacity does not help ROUGE-L.
- **Refactoring is slightly lower** than the 1.5B v3 (58/60 vs 59/60, one
  example); both are format wins over the base.
- **Code generation is better than the 1.5B v3** (0.6322 vs 0.5165) but still
  **11.2 pts below the 3B base** (0.7438). SFT still degrades code generation.
- **Bug detection is still collapsed**: 0 TP / 0 FP / 50 FN / 50 TN, F1 0.0.
  The 3B base remains the only model that detects bugs (F1 0.5470). The SFT
  data/label format does not teach the binary signal, even at 3B.
- **Completion** (0.3133) is better than the 1.5B v3 but below Phi-4 base
  (0.3494) and the 3B base (0.3253).

## Cost

The 3B SFT is heavier than the 1.5B v3:

| task | 3B SFT latency | 1.5B v3 latency | 3B SFT VRAM |
|---|---:|---:|---:|
| code_generation | 8.03 s | 5.22 s | 6.4 GB |
| code_refactoring | 7.12 s | 5.41 s | 8.5 GB |
| unit_test_generation | 10.59 s | 6.22 s | 8.5 GB |
| code_explanation | 5.20 s | 4.89 s | 6.4 GB |
| bug_detection | 2.90 s | 2.08 s | 7.5 GB |
| code_completion | 1.39 s | 1.42 s | 8.5 GB |

It is ~1.3–1.7× slower on the generative tasks and uses ~1.7× the VRAM. It is
still a small model that fits a T4, but the 1.5B is cheaper for the tasks it
wins.

## Routing

**Best model per task (cost tie-break):**

| task | best model | metric |
|---|---|---|
| code_generation | **Qwen 3B base** | 0.7438 |
| code_refactoring | **Qwen 1.5B SFT v3** | 0.9833 |
| unit_test_generation | **Qwen 3B SFT v3** | 0.6000 |
| code_explanation | **Qwen 1.5B SFT v3** | 0.2092 (3B SFT 0.2093, tie; 1.5B cheaper) |
| bug_detection | **Qwen 3B base** | 0.5470 |
| code_completion | **Phi-4-mini base** | 0.3494 |

**Recommended deployment:** Qwen 3B base for `code_generation` and
`bug_detection`; Qwen 1.5B SFT v3 for `code_refactoring` and
`code_explanation`; the Qwen 3B SFT v3 adapter for `unit_test_generation` only;
Phi-4 base for `code_completion`. The 3B SFT adapter shares the already-loaded
3B base, so it adds no base weights. It adds **5/85 valid suites** and **6/85
valid + kill-all** over the 1.5B v3, at ~1.7× unit-test latency (10.6 s vs
6.2 s). This uses 3 base models (3B, 1.5B, Phi-4) plus one adapter.

**3-model simplification (keep current routing):** drop the 3B SFT adapter and
let Qwen 1.5B SFT v3 handle unit tests too. Unit tests fall from 0.6000 to
0.5412 (5 problems), but it is faster, lower-VRAM, and unchanged everywhere
else. This is the default if deployment simplicity or cost dominates.

**Alternative if unit quality is the priority and model count matters:** Qwen 3B
base for code_generation/bug_detection and completion (0.3253 vs Phi-4 0.3494,
−2.4 pts), with the 3B SFT adapter for refactoring, unit tests and explanation.
This drops the 1.5B and Phi-4, loses one refactoring example, gains five unit
problems and ties explanation; two base weights total.

## Known limitations

- Same data limitations as the 1.5B v3: templated bug fields, identity
  refactoring targets, docstring-based explanations, and replay code-generation
  rows.
- The 3B SFT was trained on the same 3 870 rows as the 1.5B; it did not add
  capacity for bug detection, and the 100% negative predictions confirm the
  limitation.
- The six-task eval is 670 examples; differences of 1–5 examples are within
  sandbox/platform noise.
