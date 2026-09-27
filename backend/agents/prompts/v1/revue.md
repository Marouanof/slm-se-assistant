# Agent 3 — Revue (v1, déterministe)
# Entrées: ruff + bandit + résultats pytest.
# Règles: exec/eval→bloquant, pickle.loads→bloquant, shell=True→bloquant,
#   mot de passe en dur→bloquant, sinon remarques Ruff.
# Sortie: findings[] + patch_proposal (diff suggéré, jamais appliqué auto).
# Décision humaine requise: status=needs_review.
