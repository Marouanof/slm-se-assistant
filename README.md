# slm-se-assistant

Assistant d'ingénierie logicielle avec petits modèles de langage (SLM).
MVP solo, coût 0€.

## Périmètre
- Backend FastAPI : `/health`, `/analyze`, `/tests`, `/review`, `/runs/{id}`
- Frontend React + TypeScript
- 6 agents LangGraph : Analyse → Tests → Debug → Revue → Documentation → DevOps → Décision humaine
- Serveur MCP lecture seule
- QLoRA Qwen2.5-Coder-0.5B-Instruct (INT4) vs Phi-3-mini-4k-instruct
- CI GitHub Actions + sécurité + audit

## Traçabilité CDC (scope réduit solo)
- Code Analysis -> Agent 1 Analyse (Ruff + Bandit)
- Test Generation -> Agent 2 Tests (pytest + couverture)
- Debugging -> Agent 3 Debug (cause + correctif suggéré)
- Code Review -> Agent 4 Revue (findings + verdict)
- Documentation -> Agent 5 Documentation (doc générée depuis AST)
- DevOps -> Agent 6 DevOps (quality-gates go/no-go) + CI + README + endpoints
- MCP -> lecture seule, dossier autorisé
- LLMOps minimal -> versionning prompts/datasets + runs SQLite/JSON

## Installation (S3)
```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload --port 8000
# UI
cd frontend
npm ci
npm run dev     # http://localhost:5173
# MCP lecture seule (stdio)
.\.venv\Scripts\python.exe -m mcp_server.server
```

## Endpoints (S2)

| Méthode + route | Statut S2 | Description |
|---|---|---|
| `GET /health` | 200 | Sonde `{status: ok}` |
| `POST /analyze` | 200 | Analyse Ruff + Bandit (`code` ou `path` relatif, `../` → 422), log en `runs/` |
| `POST /tests` | 200 | Agent2 : smoke pytest + couverture en tmp, `trajectoire=[analyse,tests,debug,revue,documentation,devops,humain]` |
| `POST /review` | 200 | Pipeline complet 6 agents : Ruff+Bandit+tests+debug+doc+verdict DevOps (diff suggéré, `needs_review`) |
| `GET /runs/{id}` | 200/404 | Audit LLMOps : endpoint, latence, trajectoire, modèle `template-s2`, prompt `v1` (secrets filtrés) |
| `GET /runs` | 200 | Liste des runs (limite 50) |

Détails : `docs/ARCHITECTURE.md`, tests `backend/tests/test_api.py`, `backend/tests/test_agents.py`.
Pipeline : `backend/agents/graph.py` (`run_pipeline`), outils allow-list `backend/agents/tools.py`, prompts `backend/agents/prompts/v1/`.

## Benchmark (S1)

- 20 tâches `evals/tasks/` : 6 algo, 6 string/list, 4 bug-handling, 4 owasp-like (Bandit).
- Référence S1 : **20/20 pass** en local (`run.py` mesure pass, latence, tokens, mémoire, Ruff/Bandit).
- Dataset versionné : `evals/DATASET.md` + `evals/hashes.txt` (sha256, MIT-maison).
- Usage :
```powershell
.\.venv\Scripts\python.exe evals/run.py --limit 20 --out evals/results.json
.\.venv\Scripts\python.exe -m pytest backend/tests evals/tests/test_runner.py -q
.\.venv\Scripts\ruff.exe check backend evals
```
- `evals/results.json` est régénérable en local (non commité) ; CI : smoke `--limit 2` via `.github/workflows/ci-s1.yml`.

## S3 — UI + MCP + sécurité (gel features majeures après S3)

- UI Vite React TS : `frontend/src/App.tsx` (sélection path/code, `/review`, findings, patch, métriques, audit),
  proxy `/api`→8000, CORS backend limité à `localhost:5173`, contenu rendu en texte seul.
- MCP stdio sans SDK : `python -m mcp_server.server` (`list_files`, `read_file`, `search_symbols`),
  `../`/absolus refusés, secrets filtrés, aucune écriture.
- Sécurité : 5 scénarios verts `backend/tests/test_security.py`, détails `docs/SECURITY.md`.
- Docker préparé sans bloquer : `backend/Dockerfile`, `frontend/Dockerfile` (compose final S6).
- Démo : backend 8000 + `npm run dev` 5173 → `/review evals/tasks/task_20_hardcoded_password/solution.py` → `B105` + `needs_review`.

## Limites connues (fin S3)

- Pas de LLM : pipeline `template-s2` déterministe, LLM Qwen/Phi branchés en S4.
- Pas de QLoRA (`training/` = stub, S4), pas d'ablations 700 générations (S5).
- `runs/` + `frontend/dist/` + `node_modules/` ignorés par Git (audit/build locaux).
- Benchmark conservé : **20/20 pass** (`evals/run.py --limit 20`), CI backend + frontend vertes.
- Gel : toute nouvelle feature majeure → S6/baclog uniquement.

## Échéance
01/01/2027. Fin visée MVP : 11/2026.
