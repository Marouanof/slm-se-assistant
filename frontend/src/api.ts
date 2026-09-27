/** Client API — passe par /api en dev (proxy Vite), direct en prod via VITE_API_URL. */

const BASE = (import.meta.env.VITE_API_URL as string | undefined) ?? "/api";

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!r.ok) {
    const txt = await r.text();
    throw new Error(`${r.status} ${txt.slice(0, 300)}`);
  }
  return (await r.json()) as T;
}

export const api = {
  health: () => req<{ status: string }>("/health"),
  reviewCode: (code: string) =>
    req<import("./types").ReviewResponse>("/review", {
      method: "POST",
      body: JSON.stringify({ code }),
    }),
  reviewPath: (path: string) =>
    req<import("./types").ReviewResponse>("/review", {
      method: "POST",
      body: JSON.stringify({ path }),
    }),
  testsCode: (code: string) =>
    req<import("./types").TestsResponse>("/tests", {
      method: "POST",
      body: JSON.stringify({ code }),
    }),
  testsPath: (path: string) =>
    req<import("./types").TestsResponse>("/tests", {
      method: "POST",
      body: JSON.stringify({ path }),
    }),
  getRun: (id: string) => req<import("./types").RunRecord>(`/runs/${id}`),
  listRuns: () => req<import("./types").RunRecord[]>("/runs"),
};
