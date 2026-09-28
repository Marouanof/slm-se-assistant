# Agent 3 — Debug (v1, déterministe)
# Entrées: ruff + bandit + résultats pytest (tests_pass, tests_output).
# Règles: tests en échec→cause = sortie tronquée ; sinon premier finding bloquant
#   (mêmes tables que la revue) ; sinon "aucun défaut détecté".
# Sortie: debug_cause + patch_proposal (diff suggéré, jamais appliqué auto).
