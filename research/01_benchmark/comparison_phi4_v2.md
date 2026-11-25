# Benchmark comparison

## code_generation

| metric | base | SFT v1 | SFT v2 |
|---|---|---|---|
| pass@1 | 0.6736 | 0.2727 | 0.2851 |
| compile_ok | 1.0000 | 0.9545 | 0.9421 |

n = 242 problems per model.

## code_explanation

| metric | base | SFT v1 | SFT v2 |
|---|---|---|---|
| rouge_l | 0.1531 | 0.1534 | 0.1272 |
| headings_ok | 1.0000 | 0.9900 | 0.9900 |

n = 100 problems per model.

## bug_detection

| metric | base | SFT v1 | SFT v2 |
|---|---|---|---|
| f1 | 0.4691 | 0.4902 | 0.0000 |
| accuracy | 0.5700 | 0.4800 | 0.5000 |

n = 100 problems per model.

## code_refactoring

| metric | base | SFT v1 | SFT v2 |
|---|---|---|---|
| pass@1 | 0.6667 | 0.4167 | 0.4000 |
| compile_ok | 0.9667 | 0.9833 | 1.0000 |

n = 60 problems per model.

## unit_test_generation

| metric | base | SFT v1 | SFT v2 |
|---|---|---|---|
| valid_suite_rate | 0.1059 | 0.2706 | 0.3882 |
| mutation_kill_rate | 1.0000 | 0.8871 | 0.9444 |
| syntax_ok | 0.7529 | 0.7765 | 0.9529 |

n = 85 problems per model.

## code_completion

| metric | base | SFT v1 | SFT v2 |
|---|---|---|---|
| exact_match | 0.3494 | 0.3373 | 0.3373 |
| edit_similarity | 0.7500 | 0.7662 | 0.7673 |

n = 83 problems per model.

