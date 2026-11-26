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

Le baseline, le SFT v2/v3 (1.5B et 3B) et l'évaluation six tâches sont faits.
Reste, dans l'ordre du CDC et compatible avec la contrainte Kaggle-only :

1. **Quantization** INT8/INT4 sur Kaggle, export des poids quantifiés et GGUF,
   puis ablation FP16 vs quantifié (métriques + latence/mémoire).
2. **Optimisation tokens/prompts** (prompt optimisé, contexte réduit, KV cache,
   batching) avec mesures de latence, throughput, mémoire et coût par tâche.
3. **Métriques manquantes** : pass@k, couverture des tests, sécurité
   (prompt injection / code dangereux), qualité de code, énergie si mesurable.
4. **Rapport final consolidé** et **démo ≤ 5 min** des étapes SLM.

Le rapport consolidé actuel (statut partiel, gaps CDC listés) est
`research/01_benchmark/final_report.md`.

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

### Qwen2.5-Coder-3B — base zero-shot (pas de SFT)

- Modèle **base uniquement**, mêmes prompts/private tests/sandbox.
- **code_generation : pass@1 0.7397** (179/242) → meilleur score du projet.
- **bug_detection : F1 0.5470** → meilleur score du projet.
- **code_refactoring : 0.0000** (0/60) : même problème de format que le 1.5B
  base (`### Changes` dans le code).
- **unit_test_generation : 10/85 suites valides** (0.1176), mais 19/19 mutants
  tués sur ces suites ; couverture trop faible face au 1.5B SFT (39/85, 0.914
  agrégé).
- **code_explanation : ROUGE-L 0.1065**, sous Phi-4 base (0.1531) et Qwen 1.5B
  SFT (0.1755).
- **code_completion : exact 0.3253**, légèrement sous Phi-4 base (0.3494).
- Coût : ~20–80 % plus lent que le 1.5B selon la tâche, VRAM ~8,5 Go.
- Le **SFT 3B v3** a été réalisé : il ne récupère pas code_generation /
  bug_detection, mais devient le meilleur modèle sur les tests unitaires
  (0,6000) ; voir la section SFT v3 ci-dessous.

**Routing final (meilleur modèle par tâche, tous modèles confondus ; égalités
tranchées par le coût) :**

| tâche | meilleur modèle | métrique |
|---|---|---|
| code_generation | **Qwen 3B base** | **0.7438** (local ; 0.7397 Kaggle) |
| code_refactoring | **Qwen 1.5B SFT v3** | **0.9833** |
| unit_test_generation | **Qwen 3B SFT v3** | **0.6000** |
| code_explanation | **Qwen 1.5B SFT v3** | **0.2092** (3B SFT 0.2093, égalité) |
| bug_detection | **Qwen 3B base** | **0.5470** |
| code_completion | **Phi-4-mini base** | **0.3494** |

**Déploiement recommandé** : Qwen 3B base (code_generation, bug_detection),
Qwen 1.5B SFT v3 (refactoring, explication), **adapter Qwen 3B SFT v3 pour
unit_test_generation uniquement**, Phi-4 base (completion). L'adapter 3B SFT
partage les poids du 3B base déjà chargé ; il apporte **+5/85 suites valides**
et **+6/85 valides + tuent tous les mutants** par rapport au 1.5B v3, au prix
d'une latence ~1,7× sur cette tâche (10,6 s vs 6,2 s).

**Simplification 3 modèles (routing actuel)** : retirer l'adapter 3B SFT et
laisser le 1.5B v3 faire les tests unitaires. On perd 5 problèmes (0,6000 →
0,5412) mais on garde le modèle le plus rapide et le moins gourmand en VRAM.
C'est le choix par défaut si la simplicité/le coût priment.

**Alternative 2 modèles de base** : 3B base pour code_generation, bug_detection
et completion (0,3253 vs Phi-4 0,3494, −2,4 pts), adapter 3B SFT pour
refactoring / unit / explication. On retire le 1.5B et Phi-4, on perd 1 exemple
de refactoring, on gagne 5 tests unitaires et on égalise l'explication.

### SFT v3 — dataset 6 tâches (terminé : entraînement + évaluation)

Le SFT v2 ne couvrait que 3/6 tâches et faisait s'effondrer `bug_detection`.
Le dataset v3 (`slm-sft-v3`, privé sur Kaggle) couvre les 6 tâches :

- **3 872 train / 298 validation**, validation équilibrée à ~50 exemples/tâche.
- Sources : MBPP full train+validation via le pilote v2 (les IDs MBPP+ du
  benchmark sont exclus), CodeXGLUE defect detection train/validation, et
  CodeXGLUE code-to-text **validation** (16,7 Mo au lieu du train de 291 Mo).
- `bug_detection` : 1 200 exemples équilibrés 600/600, labels réels ; les
  champs `location` / `description` / `fix` sont **templatés**, seul `has_bug`
  est supervisé.
- `code_explanation` : 1 200 exemples ; la docstring CodeXGLUE est placée sous
  `## Purpose`, les autres sections restent courtes.
- `code_refactoring` : 236 exemples d'**identité** (même fonction en entrée et
  sortie) pour apprendre le contrat de sortie, pas une stratégie de refactoring.
- `code_generation` : 236 exemples MBPP + 500 exemples de replay CodeXGLUE
  (fonctions réelles, filtre auto-contenu), soit 736.
- Aucun overlap exact avec le benchmark ; le test privé n'est lu que pour
  calculer les hashes de contrôle, jamais écrit dans le dataset.
- Le notebook filtre les exemples > 2 048 tokens avant entraînement pour ne pas
  tronquer silencieusement les complétions (surtout les fonctions C longues).

**Entraînement : TERMINÉ** — kernel `merouanefaik/qwen15-sft-v3`, 2 epochs,
1 936 steps, `train_runtime` 3 353 s (**55,9 min**), `train_loss` 0,5801.
`eval_loss` : epoch 1 = **0,4206** (meilleur, `checkpoint-968`), epoch 2 =
0,4240. ZIP 278 451 244 octets, SHA256
`873532da1bf5e6f96e48e412dae6e17dae2bd52be4ca77a9fed82f784dc886ff`.

**Évaluation : TERMINÉE** — kernel `merouanefaik/qwen15-sft-v3-eval`,
`checkpoint-968`, sandbox `sandbox_subprocess`. ZIP résultats 100 159 octets,
SHA256 `269615a681c0674e8200aa0fb5fa4c0afe0fbb799eb81d9b8ae1f7e4ba10f4a6`,
14 fichiers internes vérifiés.

| tâche | métrique | v3 | v2 | delta vs v2 |
|---|---|---:|---:|---:|
| code_generation | pass@1 | 0.5165 (125/242) | 0.5372 | −0.0207 |
| code_refactoring | pass@1 | **0.9833** (59/60) | 0.9167 | **+0.0666** |
| unit_test_generation | suites valides | **0.5412** (46/85) | 0.4588 | **+0.0824** |
| unit_test_generation | mutation kill agrégé | 0.9286 | 0.9140 | +0.0146 |
| unit_test_generation | valide + tue tous | 0.4824 (41/85) | 0.4118 | **+0.0706** |
| code_explanation | ROUGE-L | **0.2092** | 0.1755 | **+0.0337** |
| bug_detection | F1 | **0.0000** | 0.0000 | 0.0000 |
| code_completion | exact_match | 0.2651 (22/83) | 0.2048 | **+0.0603** |
| code_completion | edit_similarity | 0.6721 | 0.6330 | +0.0391 |

La v3 est un **gain net sur v2** : meilleure sur refactoring, tests unitaires,
explication et completion. Elle reste sous le 3B base pour code_generation et
bug_detection. `bug_detection` reste effondrée : 100/100 prédictions
`has_bug=false`, JSON valide, F1 0.0 — le signal C n'est pas appris par le 1.5B.

**SFT 3B v3 — entraînement + évaluation : TERMINÉS** — kernel
`merouanefaik/qwen3-sft-v3`, 2 epochs, 1 936 steps, `train_runtime` 4 821 s
(**80,3 min**), `train_loss` 0,5404. `eval_loss` : epoch 1 = **0,3949**
(meilleur, `checkpoint-968`), epoch 2 = 0,4048. 3 870/3 872 train et 298/298
validation conservés. ZIP d'entraînement SHA256 (sidecar)
`2ee0438c377b1916df419183a531e41f295a46c8be8faf2e7017505104bf75fe` (non
re-téléchargé localement). Évaluation `merouanefaik/qwen3-sft-v3-eval`,
`checkpoint-968`, sandbox `sandbox_subprocess` : ZIP 97 152 octets, SHA256
`9f626900b48816744bdcc4298af93c6a4f0b11dc3a2ea6497ce7436c5765bb89`,
14 checksums internes vérifiés ; durée d'évaluation **4 590 s (76,5 min)**.

| tâche | métrique | 3B SFT v3 | 3B base | 1.5B SFT v3 |
|---|---|---:|---:|---:|
| code_generation | pass@1 | 0.6322 (153/242) | **0.7438** (180/242) | 0.5165 |
| code_refactoring | pass@1 | 0.9667 (58/60) | 0.0000 | **0.9833** (59/60) |
| unit_test_generation | suites valides | **0.6000** (51/85) | 0.1176 (10/85) | 0.5412 (46/85) |
| unit_test_generation | mutation kill agrégé | 0.9389 (123/131) | 1.0000 (19/19) | 0.9286 (104/112) |
| unit_test_generation | valide + tue tous | **0.5529** (47/85) | 0.1176 (10/85) | 0.4824 (41/85) |
| code_explanation | ROUGE-L | **0.2093** | 0.1065 | 0.2092 |
| bug_detection | F1 | 0.0000 | **0.5470** | 0.0000 |
| code_completion | exact_match | 0.3133 (26/83) | 0.3253 | 0.2651 |

Le 3B SFT **ne récupère pas** les deux tâches visées : code_generation reste
11,2 pts sous le 3B base et bug_detection reste effondrée (100/100
`has_bug=false`, JSON valide). Il est en revanche **meilleur sur les tests
unitaires** (51/85 vs 46/85 pour le 1.5B v3 ; 47/85 valides + tuent tous les
mutants vs 41/85) et fait **jeu égal en explication** (0,2093 vs 0,2092). Le
refactoring perd 1 exemple face au 1.5B v3 (58/60 vs 59/60). Il est jusqu'à
~1,7× plus lent sur code_generation / refactoring / tests unitaires
(explication et completion sont proches) et utilise ~1,7× plus de VRAM que le
1.5B v3.

### Rappels

- Smoke test v1 : TERMINÉ (val loss 0.8345).
- Full run v1 : TERMINÉ (eval_loss 0.6511 ; par epoch 0.5710/0.5932/0.6511 ;
  meilleur = checkpoint-203, adapter 34 MB, SHA256 zip vérifié).
- Eval v1 : TERMINÉ (6 tâches, comparaison base vs SFT).
- Limitation connue : le SFT **v2** ne couvrait que 3/6 tâches. Le dataset
  **v3** couvre 6/6 et est évalué. Il améliore refactoring, tests unitaires,
  explication et completion, mais `bug_detection` reste à F1 0.0 (classe
  négative uniquement) et code_generation reste sous le 3B base.


## 8. Optimisations retenues

- Adapter-only (pas de merged 16-bit) pour le run complet → ZIP léger.
- Évaluation sur Kaggle (pas en local) → pas de gros téléchargement.
- Téléchargement local limité aux petits artefacts (adapter, metrics, SHA256).
- Unsloth `--upgrade` pour profiter des gains QLoRA/T4.
- `unsloth eval` disponible pour l'évaluation post-training.