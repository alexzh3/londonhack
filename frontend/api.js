// api.js — thin fetch wrappers for the 6 MVP backend routes.
//
// Hostname-aware default:
//   - file://, localhost, or 127.0.0.1 → http://<page-host>:8000 (local dev)
//                                       Mirroring the page's hostname avoids
//                                       cross-origin video errors when the
//                                       static frontend is served on
//                                       127.0.0.1 but api.js hardcodes
//                                       localhost (some Chromium contexts
//                                       resolve those differently for media
//                                       resources, even with CORS allowed).
//   - any other hostname               → "" (same-origin; deployed Vercel
//                                           frontend uses /api/* rewrites
//                                           to the Render backend)
//
// Override `window.CAFETWIN_API_BASE` (set before this script loads) for
// custom setups, e.g. dev backend on a different port or staging origin.
function _defaultApiBase() {
  if (typeof window === "undefined" || !window.location) return "";
  const host = window.location.hostname;
  if (!host) return "http://127.0.0.1:8000";
  if (host === "localhost" || host === "127.0.0.1") {
    return `http://${host}:8000`;
  }
  return "";
}

const API_BASE =
  (typeof window !== "undefined" && typeof window.CAFETWIN_API_BASE === "string")
    ? window.CAFETWIN_API_BASE
    : _defaultApiBase();

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

// Resolve a backend-relative asset path (e.g. "demo_data/sessions/.../frame.jpg")
// against API_BASE so the browser fetches it from the FastAPI static mount.
// Pass through URLs that already have a scheme (http:// or https://).
function assetUrl(relativePath) {
  if (!relativePath) return "";
  if (/^https?:\/\//i.test(relativePath)) return relativePath;
  const base = API_BASE || "";
  const clean = relativePath.replace(/^\/+/, "");
  return base ? `${base}/${clean}` : `/${clean}`;
}

const cafetwinApi = {
  base: API_BASE,
  assetUrl,
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
  getMemories: (sessionId) =>
    _request("/api/memories", sessionId ? { query: { session_id: sessionId } } : {}),
  getLogfireUrl: () => _request("/api/logfire_url"),
};

window.cafetwinApi = cafetwinApi;
