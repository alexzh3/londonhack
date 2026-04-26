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
//                                           frontend uses rewrites for /api/*,
//                                           /demo_data/*, and /cafe_videos/*
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

async function _streamRequest(path, { method = "GET", body, onEvent } = {}) {
  const res = await fetch(API_BASE + path, {
    method,
    headers: {
      "Content-Type": "application/json",
      "Accept": "text/event-stream",
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!res.ok) {
    const text = await res.text();
    const data = text ? JSON.parse(text) : null;
    const detail = data && (data.detail ?? data.error ?? data);
    const err = new Error(`${method} ${path} → ${res.status}`);
    err.status = res.status;
    err.detail = detail;
    throw err;
  }
  if (!res.body || !res.body.getReader) {
    return _request("/api/run", { method: "POST", body });
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let finalResponse = null;
  let streamError = null;

  const dispatch = (block) => {
    let event = "message";
    const dataLines = [];
    for (const raw of block.split(/\r?\n/)) {
      if (raw.startsWith("event:")) event = raw.slice(6).trim();
      if (raw.startsWith("data:")) dataLines.push(raw.slice(5).trimStart());
    }
    if (!dataLines.length) return;
    const data = JSON.parse(dataLines.join("\n"));
    if (onEvent) onEvent({ event, data });
    if (event === "run_completed") finalResponse = data.response;
    if (event === "error") {
      streamError = new Error(`${method} ${path} → ${data.status_code || "stream error"}`);
      streamError.detail = data.detail;
    }
  };

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const blocks = buffer.split(/\n\n/);
    buffer = blocks.pop() || "";
    blocks.forEach(dispatch);
  }
  buffer += decoder.decode();
  if (buffer.trim()) dispatch(buffer);
  if (streamError) throw streamError;
  if (!finalResponse) throw new Error(`${method} ${path} ended without run_completed`);
  return finalResponse;
}

// Resolve a backend-relative asset path (e.g. "demo_data/sessions/.../frame.jpg")
// against API_BASE so the browser fetches it from the FastAPI static mount. On
// Vercel deployments API_BASE is empty and vercel.json rewrites these paths to
// Render.
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
  postRunStream: (sessionId, { onEvent } = {}) =>
    _streamRequest("/api/run/stream", {
      method: "POST",
      body: { session_id: sessionId },
      onEvent,
    }),
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
  // SimAgent: natural-language scenario prompt → ScenarioCommand. The agent
  // reads the currently-active scenario as context (so "half staff" scales
  // from the current value, not baseline) and returns new seats/baristas/
  // footfall/style + a short rationale the UI can render in chat.
  postSimPrompt: ({ sessionId, prompt, activeScenario }) =>
    _request("/api/sim/prompt", {
      method: "POST",
      body: {
        session_id: sessionId,
        prompt,
        active_scenario: {
          name: activeScenario.name,
          seats: activeScenario.seats,
          baristas: activeScenario.baristas,
          footfall: activeScenario.footfall,
          style: activeScenario.style,
          hours: activeScenario.hours,
        },
      },
    }),
  getMemories: (sessionId) =>
    _request("/api/memories", sessionId ? { query: { session_id: sessionId } } : {}),
  getLogfireUrl: () => _request("/api/logfire_url"),
};

window.cafetwinApi = cafetwinApi;
