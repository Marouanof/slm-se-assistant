# Qwen2.5-Coder-3B base — findings

## Setup

- **Base model only, zero-shot**: no SFT, no adapter.
- Same prompts, private tests and `sandbox_runner.py` as the other runs.
- 242 code_generation / 60 refactoring / 85 unit_test / 100 explanation /
  100 bug_detection / 83 completion examples.

## Results

| task | metric | Qwen 3B base |
|---|---|---|
| code_generation | pass@1 | **0.7397** (179/242); local recompute 0.7438 (180/242) |
| code_refactoring | pass@1 | 0.0000 (0/60) |
| unit_test_generation | valid suites | 0.1176 (10/85) |
| unit_test_generation | mutation kill (aggregate) | 1.0000 (19/19) |
| code_explanation | ROUGE-L | 0.1065 |
| bug_detection | F1 | **0.5470** |
| code_completion | exact_match | 0.3253 |
| code_completion | edit_similarity | 0.6893 |

## Reading

- **Best code_generation of the project**: 0.7397 (local recompute 0.7438) vs
  Phi-4 base 0.6736, Qwen 1.5B base 0.6033, Phi-4 SFT v2 0.2851.
- **Best bug_detection of the project**: F1 0.5470 vs Phi-4 base 0.4691,
  Qwen 1.5B base 0.1818, SFT v2 0.0. The 3B predicts 67/100 as buggy
  (32 TP, 35 FP, 18 FN, 14 TN), so it trades precision for recall.
- **Refactoring 0.0**: same format failure as the 1.5B base. `compile_ok` is
  0.65, but the `### Changes` prose inside the fence means no test passes.
  Qwen 1.5B SFT v3 (0.9833) is the fix.
- **Unit tests**: only 10/85 valid suites, but all 19 mutants are killed on
  those suites (mutation kill 1.0). Coverage is too low versus Qwen 3B SFT v3
  (51/85 valid, 0.9389 aggregate) and Qwen 1.5B SFT v3 (46/85, 0.9286).
- **Explanation** (0.1065) is below Phi-4 base (0.1531) and Qwen 1.5B SFT v3
  (0.2092).
- **Completion** (0.3253) is slightly below Phi-4 base (0.3494).

## Cost

The 3B is heavier and slower on T4:

| task | 3B latency | 1.5B latency |
|---|---|---|
| code_generation | 5.25 s | 4.37 s |
| unit_test_generation | 15.58 s | 8.59 s |
| code_explanation | 9.85 s | 7.46 s |

VRAM ~8.5 GB vs ~5 GB for the 1.5B. Both fit on T4, but the 3B is less
efficient per example.

## Routing

- **Qwen 3B base** for `code_generation` (0.7438) and `bug_detection` (0.5470).
- **Qwen 1.5B SFT v3** for `code_refactoring` (0.9833) and
  `code_explanation` (0.2092).
- **Qwen 3B SFT v3 adapter** for `unit_test_generation` only (0.6000, 51/85
  valid suites): it shares the already-loaded 3B base and beats the 1.5B v3
  (0.5412) by 5 problems.
- **Phi-4 base** for `code_completion` (0.3494).

A 3-model simplification drops the 3B SFT adapter and lets the 1.5B v3 handle
unit tests too (0.5412, 5 fewer); it is faster and lower-VRAM. A 2-base-weight
alternative uses the 3B base for code_generation/bug_detection/completion
(0.3253 vs Phi-4 0.3494, −2.4 pts) and the 3B SFT adapter for the other three
tasks.

The **3B SFT v3** ablation completed (`merouanefaik/qwen3-sft-v3`): best
`checkpoint-968`, eval_loss 0.3949, 80.3 min. It did **not** recover
code_generation (0.6322 vs 3B base 0.7438) or bug_detection (F1 0.0 vs 0.5470),
so the 3B base remains the model for those tasks. The 3B SFT is a targeted
unit-test upgrade, not a replacement for the 3B base.
