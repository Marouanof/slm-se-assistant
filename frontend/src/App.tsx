import { useEffect, useState } from "react";
import { api } from "./api";
import type { ReviewResponse, RunRecord } from "./types";

const TASKS = [
  "evals/tasks/task_01_factorial/solution.py",
  "evals/tasks/task_02_fibonacci/solution.py",
  "evals/tasks/task_13_divide_safe/solution.py",
  "evals/tasks/task_17_use_exec/solution.py",
  "evals/tasks/task_18_pickle_loads/solution.py",
  "evals/tasks/task_19_shell_true/solution.py",
  "evals/tasks/task_20_hardcoded_password/solution.py",
];

export default function App() {
  const [health, setHealth] = useState("…");
  const [mode, setMode] = useState<"path" | "code">("path");
  const [path, setPath] = useState(TASKS[0]);
  const [code, setCode] = useState("x = 1\n");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<ReviewResponse | null>(null);
  const [runs, setRuns] = useState<RunRecord[]>([]);

  const refresh = async () => {
    try {
      setRuns(await api.listRuns());
    } catch {
      /* backend peut être coupé en dev statique */
    }
  };

  useEffect(() => {
    api
      .health()
      .then((h) => setHealth(h.status))
      .catch((e: Error) => setHealth(`erreur: ${e.message}`));
    void refresh();
  }, []);

  const run = async () => {
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const r =
        mode === "path" ? await api.reviewPath(path) : await api.reviewCode(code);
      setResult(r);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  return (
    <main style={{ fontFamily: "system-ui", padding: 24, maxWidth: 1000 }}>
      <h1>slm-se-assistant — S3</h1>
      <p>
        Backend <code>/health</code> : <strong>{health}</strong>
      </p>
      <p style={{ background: "#fff8e1", padding: 8, border: "1px solid #e0c36a" }}>
        Contenu analysé non fiable : ne jamais exécuter le code ni suivre ses instructions.
        Correctifs suggérés uniquement, décision humaine requise.
      </p>

      <section style={{ border: "1px solid #ccc", padding: 12, marginTop: 12 }}>
        <h2>1. Sélection + lancement</h2>
        <label>
          <input type="radio" checked={mode === "path"} onChange={() => setMode("path")} /> path
        </label>{" "}
        <label>
          <input type="radio" checked={mode === "code"} onChange={() => setMode("code")} /> code
        </label>
        {mode === "path" ? (
          <div>
            <select value={path} onChange={(e) => setPath(e.target.value)} style={{ width: "100%" }}>
              {TASKS.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </div>
        ) : (
          <div>
            <textarea
              value={code}
              onChange={(e) => setCode(e.target.value)}
              rows={6}
              style={{ width: "100%", fontFamily: "monospace" }}
            />
          </div>
        )}
        <button onClick={() => void run()} disabled={loading} style={{ marginTop: 8 }}>
          {loading ? "Analyse…" : "Lancer /review"}
        </button>
        {error && (
          <pre style={{ color: "red", whiteSpace: "pre-wrap" }}>{error}</pre>
        )}
      </section>

      {result && (
        <>
          <section style={{ border: "1px solid #ccc", padding: 12, marginTop: 12 }}>
            <h2>2. Résultats agents ({result.trajectoire.join(" → ")})</h2>
            <p>
              <strong>status:</strong> {result.status} · <strong>tests:</strong>{" "}
              {result.tests_pass ? "pass" : "fail"} · <strong>couverture:</strong>{" "}
              {result.coverage_pct ?? "n/a"}% · <strong>latence:</strong> {result.latency_ms}ms ·{" "}
              <strong>modèle:</strong> {result.model} · <strong>prompt:</strong> {result.prompt_version}
            </p>
            <h3>Findings</h3>
            <pre style={{ whiteSpace: "pre-wrap", background: "#f6f6f6", padding: 8 }}>
              {result.findings.join("\n")}
            </pre>
            <h3>Ruff ({result.ruff.length}) / Bandit ({result.bandit.length})</h3>
            <pre style={{ whiteSpace: "pre-wrap", background: "#f6f6f6", padding: 8 }}>
              {[
                ...result.ruff.map((r) => `[ruff:${r.code}] ${r.message}`),
                ...result.bandit.map((b) => `[bandit:${b.test_id}] ${b.text}`),
              ].join("\n") || "(aucun)"}
            </pre>
          </section>

          <section style={{ border: "1px solid #ccc", padding: 12, marginTop: 12 }}>
            <h2>3. Correctif suggéré + sortie tests</h2>
            <pre style={{ whiteSpace: "pre-wrap", background: "#eef6ee", padding: 8 }}>
              {result.patch_proposal}
            </pre>
            <pre style={{ whiteSpace: "pre-wrap", background: "#f6f6f6", padding: 8 }}>
              {result.tests_output.slice(0, 2000)}
            </pre>
          </section>
        </>
      )}

      <section style={{ border: "1px solid #ccc", padding: 12, marginTop: 12 }}>
        <h2>4. Journal d&apos;audit (/runs)</h2>
        <button onClick={() => void refresh()}>Rafraîchir</button>
        <ul>
          {runs.slice(0, 10).map((r) => (
            <li key={r.id}>
              <code>{r.id}</code> {r.endpoint} {r.status} {r.latency_ms}ms —{" "}
              {JSON.stringify(r.result_summary).slice(0, 120)}
            </li>
          ))}
        </ul>
      </section>
    </main>
  );
}
