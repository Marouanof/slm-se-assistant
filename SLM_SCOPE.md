# SLM Scope — Tâches SLM uniquement (CDC filtré)

> Dérivé de `LLM Software Engineering 2026 LSI.pdf` (CDC). Ne conserve que les
> tâches **liées aux SLMs** (fine-tuning, benchmark, optimisation, évaluation).
> Les tâches backend/frontend/app/infra sont hors périmètre (ami).

## 0. Environnement de calcul (contrainte matérielle)

- **PC local faible** : AMD Ryzen 3 3250U (2 cœurs/4 threads), ~18 Go RAM,
  GPU intégré AMD Radeon (2 Go) — **pas de GPU NVIDIA dédié**.
- **Conséquence** : aucune tâche d'entraînement/inférence/évaluation lourde ne
  tourne en local. Tout le compute (fine-tuning, benchmark, quantization,
  évaluation) se fait sur **Kaggle (GPU T4)**.
- **Local = données uniquement** : préparation de datasets, merge/validation/
  agrégation des résultats, rédaction du rapport. Jamais de charge GPU locale.
- **Règle** : si une étape nécessite un GPU, elle est écrite comme notebook
  Kaggle et exécutée sur T4, jamais sur le PC.

## 1. Objectif (partie SLM)

Concevoir et évaluer un assistant d'ingénierie logicielle basé sur des **Small
Language Models (SLMs)** (Qwen, Phi), avec un focus sur le fine-tuning
efficace, l'inférence basse ressource, l'optimisation des tokens, la qualité
logicielle, les tests automatisés et l'évaluation.

Investiguer comment des modèles compacts peuvent être spécialisés pour les
tâches d'ingénierie logicielle tout en réduisant la mémoire GPU, la latence,
le coût de calcul et l'usage de tokens, par rapport aux LLMs généralistes plus
gros.

## 2. Composants SLM (à réaliser)

- **SLM Benchmarking** : comparer Qwen, Phi et autres SLMs sur les tâches SE :
  génération de code, complétion, détection de bugs, explication, refactoring,
  génération de tests.
- **Efficient Fine-Tuning** : Unsloth + LoRA/QLoRA/PEFT pour spécialiser les
  SLMs pour le SE avec peu de ressources.
- **Performance Optimization** : quantization 4/8-bit, KV cache, attention
  efficace, batching, compression de contexte, optimisation de prompts,
  réduction de tokens ; mesurer latence, throughput, mémoire, coût.
- **Software Quality (niveau modèle)** : analyse automatique de la qualité,
  maintenabilité, complexité, vulnérabilités, standards, dette technique (via
  le SLM).
- **Automated Testing (niveau modèle)** : génération de tests unitaires/
  intégration/API, couverture, tests de régression, détection de tests qui
  échouent, proposition de fixes (via le SLM).
- **LLM Security (niveau modèle)** : robustesse aux prompt injections, refus de
  code dangereux, filtrage des sorties, non-fuite de secrets/code.

## 3. Évaluation expérimentale (SLM)

Benchmark reproductible couvrant :
SLM → Fine-tuning → Quantization → Token Optimization → (Agentic Workflow) →
Software Engineering Tasks.

Métriques :
- Correction du code ; pass@k ; taux de réussite des tests unitaires ;
  couverture ; précision/rappel/F1 de détection de bugs ; métriques de qualité
  de code ; détection de vulnérabilités ; succès de compilation/exécution ;
  taux d'hallucination/erreur ; latence ; TTFT ; tokens/s ; mémoire GPU/CPU ;
  nombre de tokens I/O ; coût par tâche ; énergie si mesurable.

Études d'ablation :
- SLM de base vs fine-tuné ; FP16 vs INT8/INT4 ; prompt standard vs optimisé ;
  contexte complet vs réduit.

## 4. Livrable SLM (à remettre à l'ami)

- Modèles SLM prêts à l'emploi (poids fine-tunés + quantisés).
- Rapport d'évaluation (métriques + ablations) en markdown.
- Benchmark reproductible (données, prompts, scripts, résultats).
- Démonstration ≤ 5 min des étapes SLM.

Deadline : 01/01/2027.

## 5. Hors périmètre (ami — backend/frontend/infra)

Exclus de ce document (gérés par l'ami) :
- Application web React/TypeScript + backend FastAPI.
- Orchestration d'agents (LangGraph), MCP, accès aux outils/repos/DB.
- DevOps/CI-CD, intégration GitHub, pipelines.
- LLMOps (monitoring infra, versions, trajectoires).
- Hébergement, déploiement, audit logging infra, sécurité applicative/infra.
- Sécurité au niveau application (sandbox d'exécution des outils, allow-lists,
  approbation humaine).

> Note : les agents/MCP/CI-CD **utilisent** les SLMs, mais leur orchestration
> et leur infra sont la partie de l'ami. Ton livrable = modèles + évaluation +
> benchmark, prêts à être branchés.

## 6. Prochaine étape logique (next step)

Le baseline d'inférence est fait. L'étape suivante,
dans l'ordre du CDC et compatible avec la contrainte Kaggle-only, est :

1. **Préparer les données de fine-tuning** (local, CPU) : générer les splits
   train/dev pour les 6 tâches SE à partir de `datasets/processed/`.
2. **Notebook Kaggle de fine-tuning** (Unsloth + LoRA/QLoRA) pour les 3 SLMs
   sur T4, avec checkpointing et export ZIP (comme le baseline).
3. **Compléter le scoring par exécution** (pass@k, test pass rate) via un
   backend sandboxé sur Kaggle (ou différer si bloqué — garder `skipped`).
4. **Quantization + optimisation** (INT4/8, KV cache, prompts) sur Kaggle.
5. **Évaluation complète + ablations** sur Kaggle, puis agrégation locale.

> Règle : toute étape GPU = notebook Kaggle. Local = données + merge + rapport.

## 7. État actuel

### Sandbox d'exécution — FAIT

`harness/scripts/sandbox_runner.py` : exécution isolée (subprocess `python -I`,
`RLIMIT_CPU/AS/NPROC/FSIZE`, timeout wall-clock, pré-check AST des imports/appels
dangereux, fichier temporaire supprimé). CPU uniquement.

Résultats re-calculés **sur les sorties déjà sauvegardées** (aucun GPU) :

| tâche | métrique | base | SFT v1 |
|---|---|---|---|
| code_generation (242) | pass@1 | **0.6736** | 0.2727 |
| code_refactoring (60) | pass@1 (comportement préservé) | **0.6667** | 0.4167 |
| unit_test_generation (85) | suites valides | 0.1059 | **0.2706** |
| unit_test_generation (85) | mutation kill rate (suites valides) | **1.0000** (23/23) | 0.8871 (55/62) |

➡️ **SFT v1 est une régression** sur la génération et le refactoring. Détail et
causes racines : `research/01_benchmark/execution_eval_results.md`.

Causes racines identifiées : (1) les 900 complétions du dataset pilote finissent
par un `|` parasite avant `<|endoftext|>` ; (2) prompt/template d'entraînement
différents de `prompt_registry.py` ; (3) complétions non fencées et sans imports ;
(4) 300 exemples/tâche, LR 2e-4, 3 epochs → sur-apprentissage (meilleur epoch 1).

### SFT v2 — TERMINÉ (entraînement + évaluation)

- Dataset `merouanefaik/slm-sft-v2` généré par `harness/scripts/build_sft_v2.py` :
  796 train / 89 val, prompts **exactement** alignés sur le harness, rendu par
  `tokenizer.apply_chat_template`, `|` supprimé, code fencé, imports conservés.
- Notebook `phi4-sft-v2` : **COMPLETE** (2 epochs, LR 1e-4, 199 steps/epoch).
  Page : https://www.kaggle.com/code/merouanefaik/phi4-sft-v2
- **eval_loss** : epoch 1 = **0.3864**, epoch 2 = **0.3745** (meilleur).
  Checkpoints : `checkpoint-199`, `checkpoint-398` (retenu), + `adapter/`.
- Éval `phi4-sft-v2-eval` : **COMPLETE**, `kernel_sources` (0 MB de modèle),
  sandbox d'exécution intégré. Détails : `sft_v2_findings.md`,
  `comparison_phi4_v2.md`.

| tâche | métrique | base | SFT v1 | SFT v2 |
|---|---|---|---|---|
| code_generation | pass@1 | **0.6736** | 0.2727 | 0.2851 |
| code_refactoring | pass@1 | **0.6667** | 0.4167 | 0.4000 |
| unit_test_generation | suites valides | 0.1059 | 0.2706 | **0.3882** |
| unit_test_generation | mutation kill (agrégé) | 1.0000 | 0.8871 | 0.9444 |
| code_explanation | ROUGE-L | **0.1531** | 0.1534 | 0.1272 |
| bug_detection | F1 | 0.4691 | **0.4902** | 0.0000 |
| code_completion | exact_match | **0.3494** | 0.3373 | 0.3373 |

➡️ **La v2 n'est pas un gain net.** Seule `unit_test_generation` progresse
nettement. `code_generation` reste cassée : **102/242** sorties inventent le nom
de la fonction au lieu de recopier la signature du stub (base : 0/242). Les
tâches zero-shot s'effondrent (bug_detection prédit toujours `has_bug=false`).
Conclusion : **routage par tâche** (base pour 5 tâches, SFT v2 pour unit_test)
ou ré-entraînement moins agressif.

### Qwen2.5-Coder-1.5B — TERMINÉ (entraînement + évaluation)

- Notebook `qwen15-sft-v2` : **COMPLETE** (même dataset `slm-sft-v2`, 2 epochs).
- **eval_loss** : epoch 1 = **0.3156** (meilleur), epoch 2 = 0.3439
  (sur-apprentissage) → checkpoint retenu = **checkpoint-199**.
- Éval `qwen15-sft-v2-eval` : **COMPLETE** en **57 min** (corrigée : `sdpa` au
  lieu de `eager`, `eos_token_id` explicite, checkpoint-199 auto-sélectionné).
  Résultats : `comparison_qwen_v2.md`.
- Page : https://www.kaggle.com/code/merouanefaik/qwen15-sft-v2

| tâche | métrique | Qwen SFT v2 |
|---|---|---|
| code_generation | pass@1 | **0.5372** (130/242) |
| code_refactoring | pass@1 | **0.9167** (55/60) |
| unit_test_generation | suites valides | **0.4588** (39/85) |
| unit_test_generation | mutation kill (agrégé) | 0.9140 |
| code_explanation | ROUGE-L | 0.1755 |
| bug_detection | F1 | 0.0000 |
| code_completion | exact_match | 0.2048 |

- Contrairement à Phi-4 v2, Qwen SFT **recopie parfaitement les signatures**
  (242/242 noms corrects) : ses échecs de `code_generation` sont de vraies
  erreurs de logique, pas du renommage.
- `bug_detection` s'effondre aussi (100/100 prédictions `has_bug=false`).

**Base vs SFT v2 (même sandbox) :**

| tâche | métrique | Qwen base | Qwen SFT v2 |
|---|---|---|---|
| code_generation | pass@1 | **0.6033** | 0.5248 |
| code_refactoring | pass@1 | 0.1000 | **0.9167** |
| unit_test_generation | suites valides | 0.0235 | **0.4588** |
| unit_test_generation | mutation kill (agrégé) | 0.0000 | **0.9140** |
| code_explanation | ROUGE-L | 0.1179 | **0.1755** |
| bug_detection | F1 | **0.1818** | 0.0000 |
| code_completion | exact_match | **0.2530** | 0.2048 |

Le 0.5248 est le recalcul local (même sandbox que le base) ; le run Kaggle
officiel donne 0.5372 (3 exemples d'écart, bruit de sandbox).

Le gain en refactoring est surtout un gain de **format** : le Qwen base met un
bloc `### Changes` en prose *dans* le code (38/60 compilent, 6/60 passent), le
SFT sort une fonction propre (60/60 compilent, 55/60 passent).

**Routing final (meilleur modèle par tâche, tous modèles confondus) :**

| tâche | meilleur modèle | métrique |
|---|---|---|
| code_generation | **Phi-4-mini base** | **0.6736** |
| code_refactoring | **Qwen SFT v2** | **0.9167** |
| unit_test_generation | **Qwen SFT v2** | **0.4588** |
| code_explanation | **Qwen SFT v2** | **0.1755** |
| bug_detection | **Phi-4-mini base** | **0.4691** |
| code_completion | **Phi-4-mini base** | **0.3494** |

Deux modèles, trois tâches chacun. Cela remplace la recommandation précédente
« base pour 5 tâches, SFT pour unit_test seulement ».

### Rappels

- Smoke test v1 : TERMINÉ (val loss 0.8345).
- Full run v1 : TERMINÉ (eval_loss 0.6511 ; par epoch 0.5710/0.5932/0.6511 ;
  meilleur = checkpoint-203, adapter 34 MB, SHA256 zip vérifié).
- Eval v1 : TERMINÉ (6 tâches, comparaison base vs SFT).
- Limitation connue : SFT couvre 3/6 tâches. Les 3 autres (bug_detection,
  code_explanation, code_refactoring) restent en zero-shot.


## 8. Optimisations retenues

- Adapter-only (pas de merged 16-bit) pour le run complet → ZIP léger.
- Évaluation sur Kaggle (pas en local) → pas de gros téléchargement.
- Téléchargement local limité aux petits artefacts (adapter, metrics, SHA256).
- Unsloth `--upgrade` pour profiter des gains QLoRA/T4.
- `unsloth eval` disponible pour l'évaluation post-training.