# VISION — cockpit d'ingénierie logicielle (cible long terme)

> Statut (27/09/2026) : document de **vision**, hors périmètre d'implémentation.
> Référence pour le rapport (§ perspectives) et la démo. Seuls 3 items light sont au backlog S6
> (cf. PLAN_PROJET § SEMAINE 6) : Benchmark Lab lecture seule, carte modèle/transparence, stepper trajectoire.
> Le reste (auth/SSO, OAuth GitHub App, PostgreSQL, Celery/Redis, vLLM, Monaco, React Flow complet,
> SonarQube, export PDF...) est explicitement hors périmètre : budget 0 €, Ryzen sans CUDA, backend local non exposé.
> Origine : note "A qu'oi peut ressembler" (rangée ici le 27/09/2026).

---

L'idée directrice : la plateforme doit se présenter comme un cockpit d'ingénierie logicielle, dans l'esprit de GitHub, Datadog et SonarQube. Elle doit être claire, orientée données, avec un pipeline visible : Repository → Analyse → Review → Tests → Fix → Qualité → CI/CD → Monitoring.

1. Parcours utilisateur, étape par étape

Étape 1. Connexion et onboarding

Page de login sobre : SSO GitHub/GitLab (OAuth) ou email + 2FA.
Choix d'un rôle (Developer, Reviewer, DevOps, Admin), qui détermine les permissions (least privilege).
Assistant d'accueil en 3 étapes : connecter un dépôt, choisir un modèle, définir les règles de sécurité.

Étape 2. Connexion d'un dépôt

Bouton « Connect Repository » (GitHub via OAuth ou GitHub App) avec sélection de la branche.
Écran de permissions MCP, lisible et explicite : quels outils l'IA peut utiliser (lecture du repo, issues, exécution de tests, CI) avec un toggle par outil (tool allow-list). Par défaut, tout est en lecture seule.
Scan automatique du langage, du framework, de la taille du projet et des tests existants.

Étape 3. Configuration du modèle

Sélecteur de SLM (Qwen, Phi, version fine-tunée ou de base) avec une carte d'information : taille, quantization (FP16 / INT8 / INT4), mémoire GPU estimée, latence estimée.
Preset « Low-resource », « Balanced » ou « Max quality ».
Option de comparaison avec un LLM plus grand, utile pour la partie expérimentale.

Étape 4. Lancement d'une analyse

Un gros bouton « Run Analysis », avec choix des agents (Code Analysis, Test Generation, Debugging, Documentation, Code Review, DevOps).
Une barre de pipeline animée montre les étapes en direct : Clone → Analyse statique → Review IA → Génération de tests → Exécution → Rapport.
Les logs et l'état des agents sont diffusés en streaming (WebSocket/SSE).

Étape 5. Résultats

Redirection automatique vers le rapport de projet (voir §3), avec un score global et des actions proposées.

Étape 6. Actions humaines

Chaque suggestion sensible (modifier du code, ouvrir une PR, lancer une commande) passe par un bouton Approve / Reject / Edit.
Tout est enregistré dans un journal d'audit.
2. Structure de l'interface (layout)
Sidebar gauche : Dashboard, Repositories, Agents, Tests, Quality, Security, CI/CD, Benchmark Lab, LLMOps, Audit Logs, Settings.
Barre supérieure : sélecteur de projet, sélecteur de modèle actif, notifications, profil, mode clair/sombre.
Zone centrale : contenu de la page.
Panneau latéral droit (optionnel) : chat avec l'agent, contextuel à la page ou au fichier ouvert.
3. Les pages principales

Dashboard (page d'accueil)

Cartes KPI : score de qualité, couverture de tests, vulnérabilités, dette technique, dernier build.
Graphiques de tendance (qualité, couverture) sur les 30 derniers jours.
Activité récente des agents et alertes.

Repository Explorer

Arborescence des fichiers avec badges (complexité, bugs, vulnérabilités).
Vue du code avec annotations IA en ligne, comme dans une revue de PR.
Résumé et explication automatique du fichier.

Agents Workspace

Chat multi-agents avec un sélecteur d'agent.
Vue trajectoire : graphe LangGraph montrant quel agent a fait quoi, avec les tools appelés, les tokens consommés et le temps.
Bouton « Replay » pour rejouer une exécution.

Test Center

Tests générés (unitaires, intégration, API) avec preview du code.
Couverture avant/après, tests en échec, correctifs proposés (diff côte à côte).
Bouton « Run in sandbox ».

Quality & Security

Complexité, maintenabilité, standards de code, dette technique (intégration SonarQube, Ruff, ESLint, Bandit…).
Vulnérabilités classées par sévérité, avec correctif suggéré.
Panneau LLM Security : détections de prompt injection, secrets masqués, commandes bloquées, tentatives de jailbreak.

CI/CD

Pipeline visuel (GitHub Actions) avec statut de chaque étape.
Review automatique de PR, résumé de déploiement, recommandations de release.

Benchmark Lab (la partie recherche, très valorisante)

Sélection des configurations : modèle, fine-tuning, quantization, prompting, contexte, mono ou multi-agent.
Tableaux comparatifs et graphiques : pass@k, F1, TTFT, tokens/s, mémoire, coût, énergie.
Vue d'ablation (Base vs Fine-tuned, FP16 vs INT4, etc.) et export CSV/PDF pour le rapport.

LLMOps Monitoring

Versions des modèles et prompts, consommation de tokens, latence, coût par tâche.
Historique des évaluations et des trajectoires d'agents.

Audit & Settings

Journal d'audit complet et filtrable (qui, quoi, quand, quel outil).
Gestion des permissions, des outils MCP, des secrets et des règles d'approbation.
4. Ce qui donne un aspect professionnel
Design system cohérent (shadcn/ui, Tailwind ou MUI), typographie propre, thème sombre.
Temps réel : streaming des réponses et des logs, jamais d'écran figé sans retour visuel.
Transparence de l'IA : afficher toujours le modèle utilisé, les tokens consommés et le niveau de confiance.
Sécurité visible : badges « sandboxed », « approval required », « secrets masked ».
Diffs et revues à la GitHub pour toute modification de code.
Rapports exportables (PDF/Markdown) et partageables.
États soignés : loading, erreurs, écrans vides avec explication, messages clairs.
Responsive et accessible (contrastes, navigation au clavier).
Performance : lazy loading, pagination, cache (React Query).
5. Architecture technique associée
Frontend : React + TypeScript, React Router, TanStack Query, Zustand, Recharts ou ECharts, Monaco Editor (affichage du code et des diffs), React Flow (graphe des agents).
Backend : FastAPI (REST + WebSocket), agents LangGraph, serveurs MCP, workers asynchrones (Celery/Redis).
Inference : vLLM ou llama.cpp servant les modèles Qwen/Phi quantifiés.
Données : PostgreSQL (résultats, audit), MLflow ou Langfuse (LLMOps).
Exécution sûre : conteneurs Docker sandboxés.
