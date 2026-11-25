# Sandbox d'exécution — portée et limites

## Rôle

Le benchmark doit mesurer si le code généré **fonctionne**, pas seulement s'il
compile. `harness/scripts/sandbox_runner.py` exécute le code généré contre les
tests de référence cachés, dans un sous-processus isolé, puis renvoie un verdict
`pass@1` / `valid_suite` / `mutation_kill_rate`.

Il est utilisé de deux façons :

1. **Post-hoc local** (`harness/scripts/eval_saved_outputs.py`) : recalcule les
   métriques d'exécution sur les sorties déjà sauvegardées des runs baseline
   (`EXECUTION_BACKEND="none"` à l'époque). Aucun GPU.
2. **Pendant l'évaluation** (notebook `phi4-sft-v2-eval`) : le sandbox est
   embarqué dans le notebook et score les sorties au fil de la génération.

## Mécanismes de protection

- **Sous-processus séparé** : `python -I <fichier_temporaire>`, jamais dans
  l'interpréteur hôte.
- **Limites noyau (POSIX / Kaggle)** via `preexec_fn` :
  `RLIMIT_CPU`, `RLIMIT_AS` (2 Go), `RLIMIT_NPROC`, `RLIMIT_FSIZE` (16 Mo),
  `RLIMIT_CORE=0`.
- **Timeout wall-clock** (`timeout + 5 s`) au-dessus de la limite CPU.
- **Pré-check AST** : refus des imports `os`, `sys`, `subprocess`, `socket`,
  `ctypes`, `importlib`, … et des appels `eval`, `exec`, `open`,
  `__import__`, `compile`, `input`.
- **Environnement minimal** : `PYTHONHASHSEED=0`,
  `PYTHONDONTWRITEBYTECODE=1`, `cwd` = répertoire temporaire, fichier supprimé
  après exécution.
- **Déterminisme** : même programme → même verdict.

## Limites (à lire avant de déployer)

Ce n'est **pas** un sandbox de production durci. C'est une protection
« défense en profondeur » pour exécuter du code généré dans un conteneur Kaggle
**éphémère**, pas pour exécuter du code hostile dans une application.

- **Pas d'isolation réseau** : le sous-processus n'est pas dans un namespace
  réseau. Le pré-check bloque `socket`/`urllib`/`http`, mais un contournement
  (ex. `ctypes`, `getattr` dynamique) reste possible.
- **Pas d'isolation fichiers** : pas de chroot/read-only FS. `open` est bloqué
  statiquement, mais peut être contourné.
- **Le pré-check AST est contournable** : il attrape les cas évidents, pas un
  adversaire déterminé.
- **RLIMIT_AS** peut être indisponible/ignoré selon le noyau ; le timeout
  wall-clock reste le garde-fou principal.
- **Windows** : seules les limites POSIX sont désactivées ; le timeout
  wall-clock reste actif. Le sandbox est prévu pour Kaggle (Linux).

**Conclusion** : adapté au scoring de sorties de modèles dans un notebook Kaggle
jetable. Pour la production (l'ami : backend/infra), utiliser un vrai backend
isolé (conteneur sans réseau, FS read-only, non-root, cgroups, seccomp).

## Ce qui est exécuté

Uniquement du code Python généré par les modèles du benchmark, plus les tests
cachés du benchmark. Aucun credential, clé API ou donnée privée n'est placé dans
l'environnement du sous-processus.

## Métriques produites

| tâche | métrique | définition |
|---|---|---|
| code_generation | `pass@1` | 1 si tous les tests HumanEval+ passent |
| code_refactoring | `pass@1` | 1 si les tests MBPP+ passent (comportement préservé) |
| unit_test_generation | `valid_suite` | 1 si les tests générés passent sur la solution canonique |
| unit_test_generation | `mutation_kill_rate` | mutants tués / mutants totaux, sur les suites valides |
