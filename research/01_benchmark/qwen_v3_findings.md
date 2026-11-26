# Qwen2.5-Coder-1.5B SFT v3 — findings

**Status: training and six-task evaluation complete. The 3B SFT v3 ablation is
running.** The numbers below come from the Kaggle eval sandbox; a local
`compare_runs.py` recomputation is in progress and will be recorded in
`comparison_qwen_v3.md`.

## Setup

- Dataset `merouanefaik/slm-sft-v3`: **3 872 train / 298 validation**, six tasks.
- Same harness-aligned prompts as v2, plus the three missing tasks
  (`bug_detection`, `code_explanation`, `code_refactoring`).
- Training: 2 epochs, LR 1e-4, LoRA r=16 / alpha=32, batch 1 × grad-accum 4,
  max_seq_len 2048, Unsloth 4-bit, seed 42.
- Token-length filter: **3 870 / 3 872** train rows kept (2 dropped),
  **298 / 298** validation rows kept.
- Best checkpoint: **checkpoint-968** (`eval_loss` **0.4206**, epoch 1).
  Epoch 2 = 0.4240, so epoch 2 slightly overfits.
- Training: **1 936 steps**, `train_runtime` **3 353 s (55,9 min)**,
  `train_loss` **0.5801**.
- Output ZIP: 278 451 244 bytes, SHA256
  `873532da1bf5e6f96e48e412dae6e17dae2bd52be4ca77a9fed82f784dc886ff`.
- Evaluation: Kaggle T4, FP16 base + PEFT adapter, `sdpa`, explicit EOS,
  `checkpoint-968` selected automatically from `train_history.json`, same
  prompts/private tests/sandbox as the previous runs.

## Results

Kaggle eval run `qwen15_sft_v3_full_20261126-010051_2fcc6d06785f_eaca474f`,
adapter `checkpoint-968` (`eval_loss` 0.42056). ZIP SHA256
`269615a681c0674e8200aa0fb5fa4c0afe0fbb799eb81d9b8ae1f7e4ba10f4a6`; all 14
internal `SHA256SUMS.txt` files verified.

| task | metric | v3 | v2 | delta vs v2 |
|---|---|---:|---:|---:|
| code_generation | pass@1 | 0.5165 (125/242) | 0.5372 (130/242) | −0.0207 |
| code_generation | compile_ok | 0.9959 (241/242) | — | — |
| code_refactoring | pass@1 | **0.9833** (59/60) | 0.9167 (55/60) | **+0.0666** |
| unit_test_generation | valid suites | **0.5412** (46/85) | 0.4588 (39/85) | **+0.0824** |
| unit_test_generation | mutation kill (aggregate) | 0.9286 (104/112) | 0.9140 (85/93) | +0.0146 |
| unit_test_generation | valid + kills all mutants | 0.4824 (41/85) | 0.4118 (35/85) | **+0.0706** |
| code_explanation | ROUGE-L | **0.2092** | 0.1755 | **+0.0337** |
| code_explanation | headings_ok | 0.9800 | — | — |
| bug_detection | F1 | **0.0000** | 0.0000 | 0.0000 |
| code_completion | exact_match | 0.2651 (22/83) | 0.2048 (17/83) | **+0.0603** |
| code_completion | edit_similarity | 0.6721 | 0.6330 | +0.0391 |

The v3 eval touched all six tasks. For the execution tasks: 240/242
code_generation rows actually executed (1 `forbidden_call:compile`, 1
syntax error), 59/60 refactoring rows executed (1 `forbidden_call:compile`), and
the unit-test suites ran through the pytest shim.

## Reading

- **v3 is a net gain over v2**: it improves refactoring, unit tests, explanation
  and completion. It becomes the best model on `code_refactoring` (0.9833),
  `unit_test_generation` (0.5412) and `code_explanation` (0.2092).
- **code_generation** is slightly below v2 and still far below Qwen 3B base
  (0.7397); the six-task data did not fix the SFT code-generation regression.
- **bug_detection remains collapsed**: all 100 predictions are
  `has_bug=false` (0 TP / 0 FP / 50 FN / 50 TN), so F1 = 0.0. This is not a
  parsing issue — every output is valid JSON. The 1.5B model did not learn the
  C-defect signal from 1 200 balanced examples; Qwen 3B base remains at F1
  0.5470.
- **code_completion** improves over v2 but stays below Phi-4 base (0.3494).

The 1.5B v3 gains are real but task-specific. The current three-model routing
should replace SFT v2 with SFT v3 on the three tasks it wins; code_generation
and bug_detection stay on Qwen 3B base, completion stays on Phi-4 base.

## 3B SFT v3 ablation

The 1.5B v3 showed gains, so the planned 3B SFT v3 ablation is running
(`merouanefaik/qwen3-sft-v3`, same dataset/hyperparameters). It is the only
remaining chance to combine the 3B base strength on code_generation and
bug_detection with the SFT output-format gains. It will be evaluated with the
same six-task harness only if training completes.

## Cost

The six-task eval (670 examples) ran in about **55 min** on the Kaggle T4:
242 code_generation + 100 explanation + 100 bug_detection + 60 refactoring +
85 unit_test + 83 completion. Mean latency/tokens per task:

| task | latency | output tokens | tokens/s | VRAM |
|---|---:|---:|---:|---:|
| code_generation | 5.22 s | 78.1 | 14.87 | 3.2 GB |
| code_refactoring | 5.41 s | 80.6 | 14.88 | 4.8 GB |
| unit_test_generation | 6.22 s | 92.7 | 14.85 | 4.8 GB |
| code_explanation | 4.89 s | 73.0 | 14.80 | 3.3 GB |
| bug_detection | 2.08 s | 27.0 | 13.25 | 4.1 GB |
| code_completion | 1.42 s | 20.4 | 13.28 | 4.8 GB |

The 1.5B v3 is cheaper than the 3B base (which used ~8.5 GB and was 20–80%
slower depending on the task), but it is not the best model on
code_generation/bug_detection/completion.

## Known limitations

- Bug `location` / `description` / `fix` are templated; only `has_bug` is real.
- Refactoring targets are identity copies; a good score means output-format and
  behaviour preservation, not refactoring quality.
- Explanations are CodeXGLUE docstrings; ROUGE-L measures docstring overlap.
- 500 code-generation rows replay real-repository functions; 105 of those
  functions also appear in the explanation set with a different prompt.
- The leakage audit is exact-match only, not semantic near-duplicate.
