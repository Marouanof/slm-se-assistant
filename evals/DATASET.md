# DATASET evals v0.1-s1

- 20 tâches handcrafted, licence MIT-maison, origine `s1-handcrafted`.
- Catégories : 6 algo (01-06), 6 string/list (07-12), 4 bug-handling (13-16), 4 owasp-like (17-20).
- Chaque tâche : `prompt.md + solution.py + test_hidden.py + meta.json`.
- Usage : `python evals/run.py --limit 20 --out evals/results.json`.
- Contrainte hardware Ryzen 3 3250U : correctness sur 20, latence/mémoire détaillée sur sous-ensemble 10 en S5.
- Hashes sha256 : voir `evals/hashes.txt` (généré en build, à versionner).
