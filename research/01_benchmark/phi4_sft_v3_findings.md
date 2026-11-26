# Phi-4-mini SFT v3 — findings

**Status: training and six-task evaluation complete.** The v3 adapter does
**not** earn a routing slot. It is numerically best on `code_explanation` but
the gain over Qwen 1.5B SFT v3 is not statistically robust, and it remains far
below the base models on code generation, bug detection and completion.

## Setup

- Base model: `microsoft/Phi-4-mini-instruct` (4-bit QLoRA, Unsloth).
- Dataset: `merouanefaik/slm-sft-v3`, **3 872 train / 298 validation**, six tasks.
- Same prompts, private tests and `sandbox_subprocess` as the Qwen v3 and base
  runs.
- Training: 2 epochs, LR 1e-4, LoRA r=16 / alpha=32, batch 1 × grad-accum 4,
  max_seq_len 2048, seed 42.
- Kept rows: **3 871 / 3 872** train (1 dropped), **298 / 298** validation.
- Best checkpoint: **checkpoint-1936**, `eval_loss` **0.5214** (epoch 1 =
  0.5363 at checkpoint-968, epoch 2 = 0.5214). Checkpoint selected by lowest
  `eval_loss`.
- Training: **1 936 steps**, `train_runtime` **6 517 s (108.6 min)**,
  `train_loss` **0.7628**.
- Training ZIP sidecar SHA256:
  `5d601b7df1c08f3871b86d3ca16aa1cc392c52b540f90fae7b8c47818ec49580`.
  The large ZIP was not downloaded locally; the eval mounted the training output.
- Eval kernel: `merouanefaik/phi4-sft-v3-eval`, adapter `checkpoint-1936`,
  `sandbox_subprocess`; wall time **3 066 s (51.1 min)**.
- Eval ZIP SHA256:
  `d8715eedf23d57cff927b89fa2f41a2f27b5ce4b7bf7bb9be17f8fc0e4f7442e`
  (104 728 bytes); all **14** internal checksums verified.

## Results

| task | metric | Phi-4 SFT v3 | Phi-4 SFT v2 | Phi-4 base | best other model |
|---|---|---:|---:|---:|---:|
| code_generation | pass@1 | 0.2975 (72/242) | 0.2851 (69/242) | **0.6736** (163/242) | Qwen 3B base 0.7438 |
| code_refactoring | pass@1 | 0.6000 (36/60) | 0.4000 (24/60) | **0.6667** (40/60) | Qwen 1.5B v3 0.9833 |
| unit_test_generation | valid suites | 0.3647 (31/85) | **0.3882** (33/85) | 0.1059 (9/85) | Qwen 3B SFT v3 0.6000 |
| unit_test_generation | mutation kill (aggregate) | 0.9505 (211/222) | 0.9444 | **1.0000** (23/23) | Qwen 3B SFT v3 0.9389 |
| unit_test_generation | valid + kills all | 0.2941 (25/85) | **0.3412** (29/85) | 0.1059 (9/85) | Qwen 3B SFT v3 0.5529 |
| code_explanation | ROUGE-L | **0.2209** | 0.1272 | 0.1531 | Qwen 3B SFT v3 0.2093 |
| bug_detection | F1 | 0.0000 | 0.0000 | **0.4691** | Qwen 3B base 0.5470 |
| code_completion | exact_match | 0.3373 (28/83) | 0.3373 (28/83) | **0.3494** (29/83) | Phi-4 base 0.3494 |
| code_completion | edit_similarity | 0.7587 | — | 0.7500 | Phi-4 base 0.7500 |

`code_generation`: 213/242 compiled and executed; 29 syntax errors. The pass
rate is 1.2 pts above Phi-4 SFT v2, but **37.6 pts below Phi-4 base** and far
from the Qwen models.

`code_refactoring`: 50/60 compiled, 49/60 executed (10 syntax errors, 1
`forbidden_call:compile`), 36/60 passed. This is +12 examples over Phi-4 v2 but
below Phi-4 base and far below the Qwen SFT v3 models.

`unit_test_generation`: 76/85 syntax-valid, 31/85 valid suites, 211/222 mutants
killed, 25/85 valid suites kill every mutant. The conditional mutation rate is
high, but only 31 suites are valid; this is **below Phi-4 v2** (33/85, 29/85)
and far below Qwen 3B SFT v3 (51/85, 47/85).

`code_explanation`: ROUGE-L **0.2209**, all 100 outputs have the required
headings. This is the highest ROUGE-L of any model in the project. A paired
bootstrap over the 100 common examples gives a +0.0117 mean gain over Qwen 1.5B
SFT v3, with a 95% CI of **[-0.0029, +0.0263]**. The interval includes zero, so
the improvement is not statistically robust at this sample size. Phi-4 v3 is
faster on this task (3.51 s vs 4.89 s) but uses about 8.0 GB of VRAM for the
task (and up to 12.1 GB on long prompts) versus about 3.3 GB for Qwen 1.5B v3.

`bug_detection`: 0 TP / 1 FP / 50 FN / 49 TN, accuracy 0.49, F1 0.0. Unlike the
Qwen SFT runs, the model predicts `has_bug=true` once instead of always false,
but the signal is still not learned. Qwen 3B base remains the only useful bug
detector (F1 0.5470).

`code_completion`: 28/83 exact matches (0.3373), edit similarity 0.7587. This
ties Phi-4 v2 on exact match and is one example below Phi-4 base. Phi-4 base
remains the completion model.

## Cost

| task | latency | output tokens | tokens/s | max VRAM |
|---|---:|---:|---:|---:|
| code_generation | 5.31 s | 106.8 | 20.09 | 7.9 GB |
| code_refactoring | 5.00 s | 94.2 | 18.85 | 12.1 GB |
| unit_test_generation | 6.21 s | 117.2 | 18.94 | 12.1 GB |
| code_explanation | 3.51 s | 66.8 | 18.84 | 8.0 GB |
| bug_detection | 2.06 s | 28.2 | 14.33 | 12.1 GB |
| code_completion | 0.66 s | 11.9 | 16.76 | 12.1 GB |

The eval used FP16 base + PEFT adapter on a T4. The larger VRAM footprint comes
from the 3.8B base and long prompts; it still fits a 16 GB T4. Training took
108.6 min and eval 51.1 min.

## Routing

**No routing change.** The selected models remain:

| task | selected model | metric |
|---|---|---|
| code_generation | Qwen 3B base | 0.7438 |
| code_refactoring | Qwen 1.5B SFT v3 | 0.9833 |
| unit_test_generation | Qwen 3B SFT v3 | 0.6000 |
| code_explanation | Qwen 1.5B SFT v3 | 0.2092 (Phi-4 v3 0.2209 numeric best; paired CI includes 0) |
| bug_detection | Qwen 3B base | 0.5470 |
| code_completion | Phi-4 base | 0.3494 |

Phi-4 SFT v3 is a useful negative result: more capacity and two epochs did not
recover the SFT code-generation regression, did not learn the bug label, and did
not beat the base model on completion. The only numeric win is explanation, and
it is not robust enough to justify another model/adapter in the default route.
The optional quality upgrade remains the Qwen 3B SFT v3 adapter for
`unit_test_generation`; adding Phi-4 v3 for explanation would trade ~2.4× the
VRAM for a 1.2-pt ROUGE-L change whose confidence interval crosses zero.

## Known limitations

- Same data limitations as the Qwen v3 runs: templated bug fields, identity
  refactoring targets, docstring-based explanations, and replay code-generation
  rows.
- The six-task eval is 670 examples; differences of a few examples are within
  sandbox/platform noise. The explanation paired CI makes this explicit.
- The Phi-4 v3 adapter was evaluated on Kaggle; the saved outputs were not
  replayed locally with `compare_runs.py`. The eval used the same harness and
  sandbox as the other runs.
