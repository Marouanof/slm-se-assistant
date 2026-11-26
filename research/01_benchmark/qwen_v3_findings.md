# Qwen2.5-Coder-1.5B SFT v3 — findings

**Status: training and six-task evaluation complete, including the 3B SFT v3
ablation.** The numbers below come from the Kaggle eval sandbox; the local
`compare_runs.py` recomputation is recorded in
`comparison_sft_v3_all_models.md`. The 3B SFT details are in
`qwen3_sft_v3_findings.md`; the later Phi-4 v3 run is in
`phi4_sft_v3_findings.md`.

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
  and completion. It is the best model at 1.5B on `code_refactoring` (0.9833),
  `unit_test_generation` (0.5412) and `code_explanation` (0.2092); the 3B SFT
  later edges unit tests to 0.6000 and ties explanation at 0.2093. Phi-4 SFT v3
  later reached 0.2209 on explanation, but its paired 95% CI includes zero, so
  the 1.5B v3 remains selected.
- **code_generation** is slightly below v2 and still far below Qwen 3B base
  (0.7438 locally); the six-task data did not fix the SFT code-generation
  regression.
- **bug_detection remains collapsed**: all 100 predictions are
  `has_bug=false` (0 TP / 0 FP / 50 FN / 50 TN), so F1 = 0.0. This is not a
  parsing issue — every output is valid JSON. The 1.5B model did not learn the
  C-defect signal from 1 200 balanced examples; Qwen 3B base remains at F1
  0.5470.
- **code_completion** improves over v2 but stays below Phi-4 base (0.3494).

The 1.5B v3 gains are real but task-specific. The current default keeps Qwen 3B
base for code_generation and bug_detection, uses Qwen 1.5B SFT v3 for
refactoring, explanation and unit tests, and keeps Phi-4 base for completion.
The Qwen 3B SFT adapter is an optional unit-test upgrade (see below).

## 3B SFT v3 ablation

The 1.5B v3 showed gains, so the planned 3B SFT v3 ablation was run
(`merouanefaik/qwen3-sft-v3`, same dataset/hyperparameters). Training completed:
2 epochs, 1 936 steps, **80.3 min**, `train_loss` 0.5404; best
`checkpoint-968` with **eval_loss 0.3949** (epoch 2 = 0.4048). 3 870/3 872 train
and 298/298 validation rows kept. Six-task eval completed with the same
prompts/private tests/sandbox: ZIP SHA256
`9f626900b48816744bdcc4298af93c6a4f0b11dc3a2ea6497ce7436c5765bb89`, 14
internal checksums verified.

- Best **unit_test_generation** of the project: **0.6000** (51/85 valid suites;
  47/85 valid + kill-all) vs 0.5412 (46/85; 41/85) for the 1.5B v3.
- **code_explanation** is a tie: 0.2093 vs 0.2092.
- **code_refactoring** is one example lower: 0.9667 (58/60) vs 0.9833 (59/60).
- **code_generation** is 0.6322 (153/242), still 11.2 pts below the 3B base
  (0.7438); **bug_detection remains F1 0.0** (100/100 `has_bug=false`). The 3B
  SFT did not recover the two tasks it was meant to fix.
- **code_completion** is 0.3133, below Phi-4 base (0.3494) and the 3B base
  (0.3253).

The 3B SFT is therefore a targeted **unit-test upgrade**, not a replacement for
the 3B base. The recommended deployment keeps the 3B base for
code_generation/bug_detection, the 1.5B v3 for refactoring/explanation, adds the
3B SFT adapter for unit tests only, and keeps Phi-4 for completion. Dropping
the adapter returns to the three-model routing and costs 5/85 unit tests.

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
