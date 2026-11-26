# Qwen2.5-Coder-3B base — findings

## Setup

- **Base model only, zero-shot**: no SFT, no adapter.
- Same prompts, private tests and `sandbox_runner.py` as the other runs.
- 242 code_generation / 60 refactoring / 85 unit_test / 100 explanation /
  100 bug_detection / 83 completion examples.

## Results

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

## Reading

- **Best code_generation of the project**: 0.7397 vs Phi-4 base 0.6736,
  Qwen 1.5B base 0.6033, Phi-4 SFT v2 0.2851.
- **Best bug_detection of the project**: F1 0.5470 vs Phi-4 base 0.4691,
  Qwen 1.5B base 0.1818, SFT v2 0.0. The 3B predicts 67/100 as buggy
  (32 TP, 35 FP, 18 FN, 14 TN), so it trades precision for recall.
- **Refactoring 0.0**: same format failure as the 1.5B base. `compile_ok` is
  0.65, but the `### Changes` prose inside the fence means no test passes.
  The Qwen 1.5B SFT v2 (0.9167) is the fix.
- **Unit tests**: only 10/85 valid suites, but all 19 mutants are killed on
  those suites (mutation kill 1.0). Coverage is too low versus Qwen 1.5B SFT
  (39/85 valid, 0.914 aggregate).
- **Explanation** (0.1065) is below Phi-4 base (0.1531) and Qwen 1.5B SFT
  (0.1755).
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

- **Qwen 3B base** for `code_generation` and `bug_detection`.
- **Qwen 1.5B SFT v3** for `code_refactoring` (0.9833), `unit_test_generation`
  (0.5412) and `code_explanation` (0.2092).
- **Phi-4 base** for `code_completion`.

A 2-model simplification is possible: Qwen 3B base for code_generation,
bug_detection and completion (0.3253 vs 0.3494, −2.4 pts on completion), Qwen
1.5B SFT v3 for the other three. It avoids loading Phi-4 for a single task.

The **3B SFT v3** ablation is now running (`merouanefaik/qwen3-sft-v3`) because
the 1.5B v3 showed gains on three tasks. It could combine the 3B base strength
with the v3 output-format gains; eval pending.
