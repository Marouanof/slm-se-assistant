# slm-se-assistant

Assistant d'ingénierie logicielle avec petits modèles de langage (SLM).
MVP solo, coût 0€.

## Périmètre
- Backend FastAPI : `/health`, `/analyze`, `/tests`, `/review`, `/runs/{id}`
- Frontend React + TypeScript
- 3 agents LangGraph : Analyse → Tests → Revue → Décision humaine
- Serveur MCP lecture seule
- QLoRA Qwen2.5-Coder-0.5B-Instruct (INT4) vs Phi-3-mini-4k-instruct
- CI GitHub Actions + sécurité + audit

## Traçabilité CDC (scope réduit solo)
- Code Analysis -> Agent 1 Analyse (Ruff + Bandit)
- Test Generation + Debugging -> Agent 2 Tests (pytest + couverture)
- Code Review -> Agent 3 Revue + correctif
- Documentation + DevOps -> CI + README + endpoints
- MCP -> lecture seule, dossier autorisé
- LLMOps minimal -> versionning prompts/datasets + runs SQLite/JSON

## Installation (S1)
```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn backend.main:app --reload
```

## Endpoints (S1)

| Méthode + route | Statut S1 | Description |
|---|---|---|
| `GET /health` | 200 | Sonde `{status: ok}` |
| `POST /analyze` | 200 | Analyse Ruff + Bandit (`code` ou `path` relatif, `../` → 422), log en `runs/` |
| `POST /tests` | 501 | Stub — génération de tests (S2) |
| `POST /review` | 501 | Stub — revue + correctif (S2) |
| `GET /runs/{id}` | 200/404 | Audit LLMOps : endpoint, latence, résumé requête/résultat (secrets filtrés) |
| `GET /runs` | 200 | Liste des runs (limite 50) |

Détails : `docs/ARCHITECTURE.md`, tests `backend/tests/test_api.py`.

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

## Limites connues (fin S1)

- Pas de LLM : `/analyze` = Ruff + Bandit déterministes, `/tests` et `/review` = 501.
- Pas d'UI (`frontend/` = stub, S3), pas de QLoRA (`training/` = stub, S4).
- Ollama / llama.cpp différés S4 (inférence GGUF-INT4 locale) ; entraînement QLoRA sur Colab/Kaggle.
- `runs/` ignoré par Git (audit local uniquement).

## Échéance
01/01/2027. Fin visée MVP : 11/2026.
