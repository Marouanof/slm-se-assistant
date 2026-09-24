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

## Échéance
01/01/2027. Fin visée MVP : 11/2026.
