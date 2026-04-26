// api.js — thin fetch wrappers for the 6 MVP backend routes.
//
// The frontend ships as flat HTML and is loaded either via file:// or a
// separate static server during dev. The backend runs on uvicorn default
// port 8000. Override `window.CAFETWIN_API_BASE` in cafetwin.html (or before
// this script loads) to point elsewhere — leave empty string when the same
// origin serves both backend and frontend.
const API_BASE =
  (typeof window !== "undefined" && typeof window.CAFETWIN_API_BASE === "string")
    ? window.CAFETWIN_API_BASE
    : "http://localhost:8000";

async function _request(path, { method = "GET", body, query } = {}) {
  let url = API_BASE + path;
  if (query) {
    const qs = new URLSearchParams(query).toString();
    if (qs) url += (url.includes("?") ? "&" : "?") + qs;
  }
  const init = { method, headers: {} };
  if (body !== undefined) {
    init.headers["Content-Type"] = "application/json";
    init.body = JSON.stringify(body);
  }
  const res = await fetch(url, init);
  const text = await res.text();
  const data = text ? JSON.parse(text) : null;
  if (!res.ok) {
    const detail = data && (data.detail ?? data.error ?? data);
    const err = new Error(`${method} ${path} → ${res.status}`);
    err.status = res.status;
    err.detail = detail;
    throw err;
  }
  return data;
}

const cafetwinApi = {
  base: API_BASE,
  listSessions: () => _request("/api/sessions"),
  getState: (sessionId) => _request("/api/state", { query: { session_id: sessionId } }),
  postRun: (sessionId) => _request("/api/run", { method: "POST", body: { session_id: sessionId } }),
  postFeedback: ({ sessionId, patternId, proposalFingerprint, decision, reason }) =>
    _request("/api/feedback", {
      method: "POST",
      body: {
        session_id: sessionId,
        pattern_id: patternId,
        proposal_fingerprint: proposalFingerprint,
        decision,
        reason: reason ?? null,
      },
    }),
  getMemories: () => _request("/api/memories"),
  getLogfireUrl: () => _request("/api/logfire_url"),
};

window.cafetwinApi = cafetwinApi;
