// app-state.jsx — Scenarios, KPI computation, dialog modals

// ── Scenario presets ──────────────────────────────────────────────────────
const SCENARIO_PRESETS = {
  "baseline":     { id: "00", name: "baseline",     style: "default",  seats: 18,  baristas: 2,  footfall: 42,  hours: 10 },
  "10x.size":     { id: "01", name: "10x.size",     style: "default",  seats: 180, baristas: 12, footfall: 480, hours: 14 },
  "brooklyn":     { id: "02", name: "brooklyn",     style: "brooklyn", seats: 32,  baristas: 3,  footfall: 78,  hours: 12 },
  "+2.baristas":  { id: "03", name: "+2.baristas",  style: "default",  seats: 18,  baristas: 4,  footfall: 64,  hours: 10 },
  "tokyo":        { id: "04", name: "tokyo",        style: "tokyo",    seats: 14,  baristas: 2,  footfall: 95,  hours: 16 },
};
const SCENARIO_ORDER = ["baseline", "10x.size", "brooklyn", "+2.baristas", "tokyo"];

// ── Made-up KPI model ─────────────────────────────────────────────────────
// Throughput cap is min(barista_capacity, footfall). Wait grows with queue
// pressure (footfall vs capacity). Revenue per cust ~ $5.50 * avg_dwell.
function computeKpis({ seats, baristas, footfall, hours, style }) {
  const baristaCap = baristas * 18;            // ~18 customers/hr per barista
  const seatThroughput = seats * 1.4;          // turns per hour
  const cap = Math.min(baristaCap, seatThroughput * 1.6, footfall);
  const throughput = Math.round(cap);

  const pressure = footfall / Math.max(1, baristaCap);
  const waitSec = Math.round(60 + pressure * 240 + (style === "tokyo" ? -30 : 0));
  const wait = `${Math.floor(waitSec / 60)}:${String(waitSec % 60).padStart(2, "0")}`;

  const ticket = style === "brooklyn" ? 7.2 : style === "tokyo" ? 6.8 : 5.4;
  const revenue = Math.round(throughput * hours * ticket);

  const seatUtil = Math.min(99, Math.round((throughput / Math.max(1, seatThroughput)) * 100));
  const baristaUtil = Math.min(99, Math.round((throughput / Math.max(1, baristaCap)) * 100));
  const queueLen = Math.max(0, Math.round(pressure * 4 - 1));

  // NPS — best when wait is short and util ≈ 75
  const utilPenalty = Math.abs(baristaUtil - 75) / 5;
  const waitPenalty = Math.max(0, (waitSec - 120) / 8);
  const nps = Math.max(-20, Math.min(85, Math.round(80 - utilPenalty - waitPenalty)));

  // margin — drops if too many baristas idle
  const margin = Math.max(8, Math.min(58, Math.round(40 + (throughput / Math.max(1, baristas)) - baristas * 1.5)));

  // footprint estimate m² — seats * 1.6 + counter
  const footprint = Math.round(seats * 1.6 + baristas * 4 + 30);

  return { throughput, wait, waitSec, revenue, seatUtil, baristaUtil, queueLen, nps, margin, footprint };
}

function fmtMoney(n) {
  if (n >= 1000) return `$${(n / 1000).toFixed(1)}k`;
  return `$${n}`;
}

function deltaStr(curr, base, kind = "abs") {
  if (base == null) return "—";
  const d = curr - base;
  if (kind === "pct") {
    const pct = base === 0 ? 0 : Math.round((d / base) * 100);
    return (pct >= 0 ? "+" : "") + pct + "%";
  }
  if (kind === "x") {
    if (base === 0) return "—";
    const r = curr / base;
    return r >= 2 ? `+${r.toFixed(1)}×` : ((d >= 0 ? "+" : "") + Math.round((d / base) * 100) + "%");
  }
  if (kind === "pp") return (d >= 0 ? "+" : "") + d + "pp";
  return (d >= 0 ? "+" : "") + d;
}

// ── useBackend ────────────────────────────────────────────────────────────
// Drives /api/state + /api/run on mount per session_id. Holds {state, run,
// loading, error}. submitFeedback() is exposed for the Accept/Reject buttons
// so the panel doesn't need to thread session_id / pattern_id / fingerprint
// itself. Mounts even when api.js failed to load — exposes a clear error so
// we don't silently degrade to mock data.
function useBackend(sessionId) {
  const [state, setState] = React.useState(null);
  const [run, setRun] = React.useState(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState(null);

  const refresh = React.useCallback(async () => {
    if (!sessionId) return;
    if (typeof cafetwinApi === "undefined") {
      setError("cafetwinApi not loaded — check api.js script tag");
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const s = await cafetwinApi.getState(sessionId);
      setState(s);
      if (s.missing_required && s.missing_required.length) {
        throw new Error(`session ${sessionId} missing fixtures: ${s.missing_required.join(", ")}`);
      }
      const r = await cafetwinApi.postRun(sessionId);
      setRun(r);
    } catch (err) {
      setError((err && err.message) || String(err));
    } finally {
      setLoading(false);
    }
  }, [sessionId]);

  React.useEffect(() => { refresh(); }, [refresh]);

  const submitFeedback = React.useCallback(async ({ decision, reason } = {}) => {
    if (!run || !state || !state.pattern) {
      throw new Error("cannot submit feedback before run completes");
    }
    return cafetwinApi.postFeedback({
      sessionId,
      patternId: state.pattern.id,
      proposalFingerprint: run.layout_change.fingerprint,
      decision,
      reason,
    });
  }, [run, state, sessionId]);

  return { state, run, loading, error, refresh, submitFeedback };
}

// Stage timing helpers for the AgentFlow panel. Backend returns 3 stages
// (evidence_pack, optimization_agent, memory_write); the existing JSX shows
// 5 visual nodes — see overview_plan.md "Visual node ← StageTiming.name".
const AGENT_FLOW_NODE_TO_STAGE = {
  vision: "evidence_pack",
  kpi: "evidence_pack",
  pattern: "evidence_pack",
  optimize: "optimization_agent",
  simulate: "memory_write",
};

function stageDurationMs(stage) {
  if (!stage) return null;
  const start = Date.parse(stage.started_at);
  const end = Date.parse(stage.ended_at);
  if (Number.isNaN(start) || Number.isNaN(end)) return null;
  return Math.max(0, end - start);
}

function fmtLatency(ms) {
  if (ms == null) return "—";
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(2)}s`;
}

// ── Modal component ───────────────────────────────────────────────────────
function Modal({ open, onClose, title, sub, children, footer }) {
  if (!open) return null;
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-hd">
          <div>
            <div className="modal-title">{title}</div>
            {sub && <div className="modal-sub">{sub}</div>}
          </div>
          <button className="modal-x" onClick={onClose}>✕</button>
        </div>
        <div className="modal-body">{children}</div>
        {footer && <div className="modal-ft">{footer}</div>}
      </div>
    </div>
  );
}

Object.assign(window, {
  SCENARIO_PRESETS, SCENARIO_ORDER,
  computeKpis, fmtMoney, deltaStr,
  Modal,
  useBackend, AGENT_FLOW_NODE_TO_STAGE, stageDurationMs, fmtLatency,
});
