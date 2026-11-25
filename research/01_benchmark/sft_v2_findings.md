# SFT v2 — résultats et diagnostic

## Rappel du protocole

- Modèle : `microsoft/Phi-4-mini-instruct` (FP16) + adapter LoRA.
- Dataset : `slm-sft-v2` (796 train / 89 val), prompts **identiques** au harness,
  rendu par `apply_chat_template`, `|` supprimé, code fencé.
- Entraînement : 2 epochs, LR 1e-4, LoRA r=16/α=32, 4-bit Unsloth.
- Meilleur checkpoint : **checkpoint-398** (epoch 2, eval_loss **0.3745**).
- Évaluation : 6 tâches, 670 exemples, greedy, sandbox d'exécution sur les 3
  tâches vérifiables.

## Résultats (base vs SFT v1 vs SFT v2)

| tâche | métrique | base | SFT v1 | SFT v2 |
|---|---|---|---|---|
| code_generation (242) | **pass@1** | **0.6736** | 0.2727 | 0.2851 |
| code_refactoring (60) | **pass@1** | **0.6667** | 0.4167 | 0.4000 |
| unit_test_generation (85) | **suites valides** | 0.1059 | 0.2706 | **0.3882** |
| unit_test_generation (85) | mutation kill rate (agrégé) | 1.0000 | 0.8871 | 0.9444 |
| unit_test_generation (85) | mutation kill rate (moyenne par problème) | 1.0000 | 0.8871 | 0.9858 |
| unit_test_generation (85) | suites valides + tuent tous les mutants | 0.1059 | 0.2353 | **0.3412** |
| code_explanation (100) | ROUGE-L | **0.1531** | 0.1534 | 0.1272 |
| bug_detection (100) | F1 | 0.4691 | **0.4902** | **0.0000** |
| code_completion (83) | exact_match | **0.3494** | 0.3373 | 0.3373 |
| code_completion (83) | edit_similarity | 0.7500 | 0.7662 | **0.7673** |

## Le seul vrai gain : unit_test_generation

- Suites valides : **10,6 % → 38,8 %** (×3,7 vs base, +43 % vs v1).
- Sur les suites valides, le taux de mutation est de **98,6 %** : les tests sont
  non seulement valides mais efficaces.
- **34,1 %** des problèmes ont une suite valide qui tue tous les mutants
  (vs 10,6 % base, 23,5 % v1).

C'est cohérent : le SFT a appris le style des assertions MBPP, et l'évaluation
unit_test utilise MBPP+ (même famille).

## Pourquoi code_generation régresse

Analyse statique des 242 sorties :

| modèle | bon nom de fonction | mauvais nom | erreur de syntaxe |
|---|---|---|---|
| base | **242** | 0 | 0 |
| SFT v1 | 143 | 88 | 11 |
| SFT v2 | 126 | **102** | 14 |

➡️ **Le modèle SFT ne recopie plus la signature.** Il invente un nom
(`has_close_elements` → `has_come_close_elements`, `below_zero` → `below_Zero`,
`parent_string` → `paren_tring`). Le test appelle `check(entry_point)` et échoue
avec `NameError` avant même d'évaluer la logique.

C'est un échec d'**instruction-following**, pas de logique : le stub contient
pourtant la signature exacte. Le base model la recopie parfaitement (242/242).

### Correctif de signature (test CPU)

On force le nom de la fonction générée vers l'`entry_point` du stub avant
d'exécuter les tests, puis on relance le sandbox.

| modèle | pass@1 brut | renommages | récupérés | pass@1 corrigé |
|---|---|---|---|---|
| SFT v1 | 0.2727 | 87 | 30 | **0.3967** |
| SFT v2 | 0.2851 | 101 | 51 | **0.4959** |

➡️ Le renommage explique **+21 pts** de pass@1 pour v2 (0.285 → 0.496) et
**+12 pts** pour v1. C'est la confirmation que l'échec dominant est la
signature. Mais même corrigé, v2 reste **18 pts sous le base** (0.496 vs
0.674) : les ~50 échecs restants sont de vraies erreurs de logique.

Conséquence : la normalisation de signature est un garde-fou utile à intégrer
au harness (gratuit, no-op pour le base model), mais elle ne suffit pas à
rendre la SFT compétitive sur `code_generation`.

## Pourquoi les tâches zero-shot régressent

- **bug_detection** : le modèle v2 prédit `has_bug=false` sur **92/100** exemples
  (8 non parsables) → F1 = 0. Le v1 prédisait un mélange (F1 0.49). Effondrement
  sur la classe négative.
- **code_explanation** : ROUGE-L 0.1531 → 0.1272.
- **code_refactoring** : 0.6667 → 0.4000 (le modèle renomme aussi les fonctions).
- **code_completion** : stable (0.3373 vs 0.3494), léger gain de similarité.

➡️ Le SFT sur 3 tâches avec des system prompts spécifiques **dégrade
l'instruction-following général** et les tâches non vues (catastrophic
forgetting).

## Conclusion provisoire

La SFT v2 **n'est pas un gain net** :

- ✅ unit_test_generation : nette amélioration ;
- ❌ code_generation : -39 pts de pass@1 ;
- ❌ code_refactoring : -27 pts ;
- ❌ bug_detection : F1 0.47 → 0.00 ;
- ⚪ code_completion, code_explanation : stables ou légèrement en baisse.

## Pistes (par ordre de coût)

1. **Post-traitement de signature** : ✅ testé, +21 pts pour v2. À intégrer au
   harness comme garde-fou (forcer le nom de fonction vers l'`entry_point` du
   stub). No-op pour le base model, donc comparable. Ne suffit pas seul.
2. **Routage par tâche** : utiliser le modèle SFT pour unit_test_generation et
   le base model pour les 5 autres tâches. C'est immédiat et probablement le
   meilleur rapport qualité/coût. **Recommandé.**
3. **Ré-entraînement moins agressif** : LR 5e-5, 1 epoch, LoRA r=8, éventuellement
   des données de replay pour les tâches zero-shot. Optionnel, gain incertain.
4. **SFT ciblé unit_test uniquement** : un adapter dédié à une seule tâche, sans
   contaminer les autres. Optionnel.
5. **GRPO avec le sandbox comme reward** : la seule piste qui attaque vraiment
   la logique de `code_generation`, mais chantier lourd. Hors périmètre immédiat.

## Reproductibilité

- Training : `kaggle_runs/phi4_sft_v2/` (notebook + metadata).
- Eval : `kaggle_runs/phi4_sft_v2_eval/` (notebook + metadata, sandbox embarqué).
- Dataset : `merouanefaik/slm-sft-v2`.
- Résultats bruts : `results/baseline/phi4mini_sft_v2/<run_id>/`.
