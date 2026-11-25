# Comparaison Phi-4 base vs Phi-4 fine-tuné (checkpoint-203)

> ⚠️ **Comparaison statique de la v1, supersédée.** Voir
> [`execution_eval_results.md`](execution_eval_results.md) pour les scores
> d'exécution réels : la SFT v1 est une **régression** (code_generation pass@1
> 0.6736 → 0.2727, code_refactoring 0.6667 → 0.4167). Les métriques
> `compile_ok`/`syntax_ok` ci-dessous saturent et ne mesurent pas la correction
> fonctionnelle.

- Base run: `phi4mini\phi4mini_full_20261120-043821_6ab5d9022c0e_0a9e6e8e`
- SFT run: `phi4mini_sft\phi4mini_sft_full_20261125-103518_ffec6cd80cff_36442c36`
- Génération: greedy (temp 0), max 512 tokens, seed 42
- Exécution de code: **non** (EXECUTION_BACKEND=none → pass@k/test pass rate skipped)

## Métriques statiques par tâche

| Tâche | Métrique | Base | Fine-tuné | Δ |
|---|---|---|---|---|
| code_generation | compile_ok | 1.0000 | 0.9545 | 🔴 -0.0455 |
| code_explanation | ROUGE-L | 0.1531 | 0.1534 | ⚪ +0.0003 |
| code_explanation | headings_ok | 1.0000 | 0.9900 | 🔴 -0.0100 |
| bug_detection | precision | 0.6129 | 0.4808 | 🔴 -0.1321 |
| bug_detection | recall | 0.3800 | 0.5000 | 🟢 +0.1200 |
| bug_detection | F1 | 0.4691 | 0.4902 | 🟢 +0.0211 |
| code_refactoring | compile_ok | 0.9667 | 0.9833 | 🟢 +0.0167 |
| code_refactoring | changed | 1.0000 | 1.0000 | ⚪ +0.0000 |
| unit_test_generation | syntax_ok | 0.7529 | 0.7765 | 🟢 +0.0235 |
| code_completion | exact_match | 0.3494 | 0.3373 | 🔴 -0.0120 |
| code_completion | edit_similarity | 0.7500 | 0.7662 | 🟢 +0.0162 |

## Notes

- 🟢 = fine-tuné meilleur, 🔴 = base meilleur, ⚪ = identique (tolérance 0.001)
- `compile_ok` / `syntax_ok` = parsing AST statique uniquement (pas d'exécution)
- Tâches exécution-dépendantes (pass@k, test pass rate) : **skipped** (pas de sandbox)
- Le fine-tuné a été entraîné sur 3 tâches (code_generation, code_completion, unit_test_generation)
