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

- Smoke test : **TERMINÉ** (COMPLETE, val loss 0.8345, SHA256 vérifié).
- Full run : **TERMINÉ** (COMPLETE, kernel `phi4-sft-full`, v1).
  - 3 epochs, 810 train / 90 val, 3 tâches (pilot data : code_generation,
    code_completion, unit_test_generation).
  - eval_loss final : **0.6511** (vs smoke 0.8345 → amélioration).
  - eval_loss par epoch : epoch1=0.5710, epoch2=0.5932, epoch3=0.6511 →
    légère sur-apprentissage à l'epoch 3 ; meilleur = epoch 1 (checkpoint-203).
  - Adapter-only (34 MB), SHA256 zip vérifié :
    `9111bf6f7c288a9c135ad8a43f48d23688c1072f91d665d76bf202c66a34dbeb`.
  - Page : https://www.kaggle.com/code/merouanefaik/phi4-sft-full
- Eval notebook : **PUSHÉ** (kernel `phi4-sft-eval`, v1).
  - Charge base Phi-4 FP16 + adapter checkpoint-203 (uploadé comme dataset).
  - Évalue sur les 6 tâches du benchmark (comparaison base vs fine-tuné).
  - Page : https://www.kaggle.com/code/merouanefaik/phi4-sft-eval
- Limitation connue : SFT couvre 3/6 tâches. Les 3 autres (bug_detection,
  code_explanation, code_refactoring) sont évaluées en zero-shot (pas de
  réponse canonique unique pour le SFT). Voir section 6 point 1.
- À venir : self-distillation filtrée pour les 3 tâches manquantes,
  quantization, Qwen 1.5B, scoring par exécution.

## 8. Optimisations retenues

- Adapter-only (pas de merged 16-bit) pour le run complet → ZIP léger.
- Évaluation sur Kaggle (pas en local) → pas de gros téléchargement.
- Téléchargement local limité aux petits artefacts (adapter, metrics, SHA256).
- Unsloth `--upgrade` pour profiter des gains QLoRA/T4.
- `unsloth eval` disponible pour l'évaluation post-training.