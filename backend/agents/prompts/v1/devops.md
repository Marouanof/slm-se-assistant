# Agent 6 — DevOps (v1, déterministe)
# Entrées: findings + tests_pass + coverage_pct + ruff/bandit counts.
# Règles: verdict NO-GO si un finding bloquant ([bloquant:...]) ou tests en échec,
#   sinon GO. Ne recalcule rien, compile les verdicts précédents en format CI-friendly.
# Sortie: devops_verdict (GO|NO-GO) + devops_notes (3 lignes max).
