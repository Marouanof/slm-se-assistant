# Frontend — S3 (Vite React TS)

UI pipeline : sélection path/code, lancement `/review`, résultats agents, patch suggéré,
métriques (latence, couverture, tokens), audit `/runs`. Contenu analysé affiché en texte
seul (`<pre>`), bandeau non fiable, décision humaine requise.

## Dev

```powershell
cd frontend
npm ci
npm run lint
npm run dev      # http://localhost:5173 (proxy /api → http://localhost:8000)
npm run build
```

Prod : `VITE_API_URL=http://localhost:8000 npm run build`.
Docker (préparé, compose final S6) : voir `Dockerfile`.
