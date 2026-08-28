const API_BASE = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

async function parseError(res: Response, fallback: string) {
  try {
    const body = await res.json();
    return body.detail || fallback;
  } catch {
    return fallback;
  }
}

export async function fetchMeta() {
  const res = await fetch(`${API_BASE}/meta`);
  if (!res.ok) throw new Error(await parseError(res, "Failed to fetch meta"));
  return res.json();
}

export async function postDiscover(payload: Record<string, unknown>) {
  const res = await fetch(`${API_BASE}/discover`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(await parseError(res, "Failed to fetch next question"));
  return res.json();
}

export async function postSession(
  answers: Record<string, unknown>,
  file?: File | null,
  sample?: string | null,
) {
  const form = new FormData();
  form.append("answers", JSON.stringify(answers));
  if (file) form.append("file", file);
  if (sample) form.append("sample", sample);
  const res = await fetch(`${API_BASE}/session`, { method: "POST", body: form });
  if (!res.ok) throw new Error(await parseError(res, "Failed to run session"));
  return res.json();
}

export async function fetchHistory() {
  const res = await fetch(`${API_BASE}/history`);
  if (!res.ok) throw new Error(await parseError(res, "Failed to fetch history"));
  return res.json();
}

export async function downloadReport(session: Record<string, unknown>) {
  const res = await fetch(`${API_BASE}/report`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(session),
  });
  if (!res.ok) throw new Error(await parseError(res, "Failed to build PDF"));
  return res.blob();
}

export function sampleUrl(name: string) {
  return `${API_BASE}/samples/${encodeURIComponent(name)}`;
}

export { API_BASE };
