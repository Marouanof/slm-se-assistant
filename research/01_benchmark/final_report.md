# SLM software-engineering benchmark — evaluation report

**Status: baseline, SFT v2/v3 and six-task execution evaluation complete.
Quantization, GGUF, pass@k, coverage, security, quality, energy and the demo are
not yet done.** This report does not claim those missing deliverables.

All GPU work ran on Kaggle T4. Local work was limited to data preparation,
aggregation, sandbox replay and writing. The private benchmark tests and hidden
data are not committed.

## 1. Scope

Six software-engineering tasks:

| task | benchmark | n | metric |
|---|---|---:|---|
| code_generation | HumanEval+ | 242 | pass@1 (execution) |
| code_refactoring | MBPP+ | 60 | pass@1 (behaviour preserved) |
| unit_test_generation | MBPP+ | 85 | valid suites, mutation kill |
| code_explanation | CodeXGLUE code-to-text | 100 | ROUGE-L, headings |
| bug_detection | CodeXGLUE defect detection | 100 | precision/recall/F1 |
| code_completion | CodeXGLUE code completion | 83 | exact match, edit similarity |

Models compared: Phi-4-mini base and SFT v2; Qwen2.5-Coder-1.5B base and SFT
v2/v3; Qwen2.5-Coder-3B base and SFT v3.

## 2. Harness

- Same prompts from `harness/prompts/prompt_registry.py` for every model.
- Same private tests and `harness/scripts/sandbox_runner.py`.
- Execution tasks are scored inside a fresh `python -I` subprocess with
  `RLIMIT_CPU/AS/NPROC/FSIZE`, a wall-clock timeout, and a static pre-check
  rejecting dangerous imports/calls.
- `pass@1 = 1` iff the generated program exits 0. Unit-test suites must pass on
  the canonical solution, then are run against stored mutants.
- The Kaggle eval reported `sandbox_subprocess`; results are not static-only.
- The local `compare_runs.py` replay reproduces the 1.5B v3 numbers exactly.
  The 3B SFT column is its Kaggle eval run; local recomputation was not rerun.

## 3. Results

### code_generation (pass@1, 242)

| model | pass@1 | passed | compile_ok |
|---|---:|---:|---:|
| Qwen 3B base | **0.7438** local (0.7397 Kaggle) | 180/242 (179 Kaggle) | 1.0000 |
| Phi-4 base | 0.6736 | 163/242 | 1.0000 |
| Qwen 3B SFT v3 | 0.6322 | 153/242 | 0.9917 |
| Qwen 1.5B base | 0.6074 local (0.6033 Kaggle) | 147/242 | 0.9917 |
| Qwen 1.5B SFT v2 | 0.5372 | 130/242 | 1.0000 |
| Qwen 1.5B SFT v3 | 0.5165 | 125/242 | 0.9959 |
| Phi-4 SFT v2 | 0.2851 raw / 0.4959 signature-forced | 69/242 / 120/242 | — |

Qwen 3B base is the clear winner. SFT v3 still loses ~11 points to the 3B base;
the six-task data did not fix the SFT code-generation regression.

### code_refactoring (pass@1, 60)

| model | pass@1 | passed | compile_ok |
|---|---:|---:|---:|
| Qwen 1.5B SFT v3 | **0.9833** | 59/60 | 1.0000 |
| Qwen 3B SFT v3 | 0.9667 | 58/60 | 1.0000 |
| Qwen 1.5B SFT v2 | 0.9167 | 55/60 | 1.0000 |
| Phi-4 base | 0.6667 | 40/60 | 0.9667 |
| Phi-4 SFT v2 | 0.4000 | 24/60 | — |
| Qwen 1.5B base | 0.1000 | 6/60 | 0.6333 |
| Qwen 3B base | 0.0000 | 0/60 | 0.6500 |

The gain is mostly output-format learning: the base models put `### Changes`
prose inside the code fence; the SFT models return a clean function. Refactoring
targets are identity copies, so this measures format/behaviour preservation, not
refactoring strategy.

### unit_test_generation (85)

| model | valid suites | mutation kill (aggregate) | valid + kills all |
|---|---:|---:|---:|
| Qwen 3B SFT v3 | **0.6000** (51/85) | 0.9389 (123/131) | **0.5529** (47/85) |
| Qwen 1.5B SFT v3 | 0.5412 (46/85) | 0.9286 (104/112) | 0.4824 (41/85) |
| Qwen 1.5B SFT v2 | 0.4588 (39/85) | 0.9140 (85/93) | 0.4118 (35/85) |
| Phi-4 SFT v2 | 0.3882 (33/85) | 0.9444 | 0.3412 (29/85) |
| Qwen 3B base | 0.1176 (10/85) | 1.0000 (19/19) | 0.1176 (10/85) |
| Phi-4 base | 0.1059 (9/85) | 1.0000 (23/23) | 0.1059 (9/85) |
| Qwen 1.5B base | 0.0235 (2/85) | 0.0000 | 0.0000 |

The 3B SFT is the best unit-test model: +5/85 valid suites and +6/85
valid+kill-all over the 1.5B v3. The 3B base's mutation-kill 1.0 is on only 19
mutants from 10 valid suites, so coverage is too low to compete.

### code_explanation (ROUGE-L, 100)

| model | ROUGE-L | headings_ok |
|---|---:|---:|
| Qwen 3B SFT v3 | **0.2093** | 0.9900 |
| Qwen 1.5B SFT v3 | 0.2092 | 0.9800 |
| Qwen 1.5B SFT v2 | 0.1755 | 1.0000 |
| Phi-4 base | 0.1531 | 1.0000 |
| Phi-4 SFT v2 | 0.1272 | — |
| Qwen 1.5B base | 0.1179 | 1.0000 |
| Qwen 3B base | 0.1065 | 1.0000 |

The two v3 models are tied within noise. The 3B capacity does not improve
ROUGE-L. Explanations are CodeXGLUE docstrings, so this measures docstring
overlap, not free-form explanation quality.

### bug_detection (F1, 100)

| model | F1 | TP | FP | FN | TN |
|---|---:|---:|---:|---:|---:|
| Qwen 3B base | **0.5470** | 32 | 35 | 18 | 14 |
| Phi-4 base | 0.4691 | — | — | — | — |
| Qwen 1.5B base | 0.1818 | — | — | — | — |
| Phi-4 SFT v2 | 0.0000 | 0 | 0 | 50 | 50 |
| Qwen 1.5B SFT v2/v3 | 0.0000 | 0 | 0 | 50 | 50 |
| Qwen 3B SFT v3 | 0.0000 | 0 | 0 | 50 | 50 |

All SFT v3 predictions are `has_bug=false` with valid JSON, so this is not a
parsing failure. The 3B SFT did not learn the C-defect signal from 1 200
balanced examples. Qwen 3B base remains the only useful bug detector.

### code_completion (83)

| model | exact_match | edit_similarity |
|---|---:|---:|
| Phi-4 base | **0.3494** (29/83) | 0.7500 |
| Qwen 3B base | 0.3253 | 0.6893 |
| Qwen 3B SFT v3 | 0.3133 (26/83) | **0.7229** |
| Qwen 1.5B SFT v3 | 0.2651 (22/83) | 0.6721 |
| Qwen 1.5B base | 0.2530 | 0.6611 |
| Qwen 1.5B SFT v2 | 0.2048 (17/83) | 0.6330 |

Phi-4 base wins exact match; the 3B SFT has better edit similarity than the 3B
base but does not beat Phi-4.

## 4. Routing

Best model per task (ties broken by cost):

| task | model | metric |
|---|---|---|
| code_generation | Qwen 3B base | 0.7438 |
| code_refactoring | Qwen 1.5B SFT v3 | 0.9833 |
| unit_test_generation | Qwen 3B SFT v3 | 0.6000 |
| code_explanation | Qwen 1.5B SFT v3 | 0.2092 (3B SFT 0.2093, tie) |
| bug_detection | Qwen 3B base | 0.5470 |
| code_completion | Phi-4 base | 0.3494 |

**Recommended deployment:** Qwen 3B base for code_generation and bug_detection;
Qwen 1.5B SFT v3 for refactoring and explanation; the Qwen 3B SFT v3 adapter for
unit_test_generation only; Phi-4 base for completion. The 3B SFT adapter shares
the already-loaded 3B base, so it adds no base weights. It buys 5/85 valid suites
at ~1.7× unit-test latency.

**3-model simplification (current routing):** drop the 3B SFT adapter and let
the 1.5B v3 handle unit tests too. Unit tests fall from 0.6000 to 0.5412 (5
problems), but the deployment is faster and lower-VRAM.

**2-base-weight alternative:** Qwen 3B base for code_generation, bug_detection
and completion (0.3253 vs Phi-4 0.3494, −2.4 pts), with the 3B SFT adapter for
refactoring, unit tests and explanation. This drops the 1.5B and Phi-4, loses one
refactoring example, gains five unit problems and ties explanation.

The 3B SFT did **not** recover code_generation or bug_detection; it is a targeted
unit-test upgrade, not a replacement for the 3B base.

## 5. Ablations and findings

- **Base vs SFT:** SFT v2/v3 fixes output formats (refactoring, unit-test
  structure, completion fences) but does not improve code_generation or bug
  detection. SFT v2 was catastrophic for bug detection; v3 did not fix it.
- **1.5B vs 3B:** the 3B base wins code_generation and bug_detection; the 1.5B
  SFT v3 wins refactoring and is cheaper; the 3B SFT wins unit tests and ties
  explanation.
- **v3 vs v2:** v3 improves refactoring (+0.0666), unit valid suites (+0.0824),
  explanation (+0.0337) and completion (+0.0603), but code_generation is
  −0.0207 and bug F1 stays 0.0.
- **Data limitations:** bug `location/description/fix` are templated; refactoring
  targets are identity copies; explanations are docstrings; 500 code-generation
  rows replay real-repository functions. A good score therefore does not imply
  general SE competence.
- **Leakage audit:** exact-match only, not semantic near-duplicate.

## 6. Cost

1.5B SFT v3 (Kaggle T4, FP16 base + PEFT adapter):

| task | latency | output tokens | tokens/s | VRAM |
|---|---:|---:|---:|---:|
| code_generation | 5.22 s | 78.1 | 14.87 | 3.2 GB |
| code_refactoring | 5.41 s | 80.6 | 14.88 | 4.8 GB |
| unit_test_generation | 6.22 s | 92.7 | 14.85 | 4.8 GB |
| code_explanation | 4.89 s | 73.0 | 14.80 | 3.3 GB |
| bug_detection | 2.08 s | 27.0 | 13.25 | 4.1 GB |
| code_completion | 1.42 s | 20.4 | 13.28 | 4.8 GB |

3B SFT v3:

| task | latency | VRAM |
|---|---:|---:|
| code_generation | 8.03 s | 6.4 GB |
| code_refactoring | 7.12 s | 8.5 GB |
| unit_test_generation | 10.59 s | 8.5 GB |
| code_explanation | 5.20 s | 6.4 GB |
| bug_detection | 2.90 s | 7.5 GB |
| code_completion | 1.39 s | 8.5 GB |

Training: 1.5B v3 55.9 min; 3B v3 80.3 min. Six-task eval: 1.5B v3 ~55 min;
3B v3 76.5 min. Both fit a T4; the 3B is up to ~1.7× slower on
code_generation/refactoring/unit tests (explanation and completion are similar)
and uses ~1.7× the VRAM.

## 7. Reproducibility and artifacts

- 1.5B v3 train ZIP SHA256:
  `873532da1bf5e6f96e48e412dae6e17dae2bd52be4ca77a9fed82f784dc886ff`.
- 1.5B v3 eval ZIP SHA256:
  `269615a681c0674e8200aa0fb5fa4c0afe0fbb799eb81d9b8ae1f7e4ba10f4a6`
  (100,159 bytes, 14 internal checksums).
- 3B v3 train ZIP sidecar SHA256:
  `2ee0438c377b1916df419183a531e41f295a46c8be8faf2e7017505104bf75fe`
  (large ZIP not downloaded locally; eval mounted it).
- 3B v3 eval ZIP SHA256:
  `9f626900b48816744bdcc4298af93c6a4f0b11dc3a2ea6497ce7436c5765bb89`
  (97,152 bytes, 14 internal checksums).
- Kaggle kernels: `merouanefaik/qwen15-sft-v3`,
  `qwen15-sft-v3-eval`, `qwen3-sft-v3`, `qwen3-sft-v3-eval`.
- Detailed reports: `qwen_v3_findings.md`, `qwen3_sft_v3_findings.md`,
  `qwen3_base_findings.md`, `comparison_qwen_v3.md`,
  `execution_eval_results.md`, `sft_v3_data_card.md`.
- Private tests and benchmark datasets stay out of git.

## 8. CDC gaps (not yet delivered)

1. **Quantization + weights**: INT8/INT4 quantized adapters/merged models and
   GGUF; FP16 vs quantized ablation. Not done.
2. **Token/prompt optimization**: optimized prompts, reduced context, KV cache,
   batching, latency/throughput/memory and cost per task. Not done.
3. **Metrics**: pass@k beyond pass@1, test coverage, security (prompt injection,
   dangerous-code refusal, secret leakage), code-quality metrics, energy. Not
   done.
4. **Final demo ≤ 5 min** of the SLM steps. Not done.

These are required for the full CDC deliverable and must not be inferred from
the current results.
