// app-panels.jsx — Side panels (data-driven)

const Icon = {
  eye: () => (<svg width="12" height="12" viewBox="0 0 16 16" fill="none">
    <path d="M1 8s2.5-5 7-5 7 5 7 5-2.5 5-7 5-7-5-7-5z" stroke="currentColor" strokeWidth="1.2"/>
    <circle cx="8" cy="8" r="2" stroke="currentColor" strokeWidth="1.2"/></svg>),
  bar: () => (<svg width="12" height="12" viewBox="0 0 16 16" fill="none">
    <path d="M3 13V8M8 13V4M13 13V10" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/></svg>),
  grid: () => (<svg width="12" height="12" viewBox="0 0 16 16" fill="none">
    <rect x="2" y="2" width="5" height="5" stroke="currentColor" strokeWidth="1.2"/>
    <rect x="9" y="2" width="5" height="5" stroke="currentColor" strokeWidth="1.2"/>
    <rect x="2" y="9" width="5" height="5" stroke="currentColor" strokeWidth="1.2"/>
    <rect x="9" y="9" width="5" height="5" stroke="currentColor" strokeWidth="1.2"/></svg>),
  flask: () => (<svg width="12" height="12" viewBox="0 0 16 16" fill="none">
    <path d="M6 2v4l-3 7a2 2 0 0 0 1.8 2.8h6.4A2 2 0 0 0 13 13l-3-7V2M5 2h6" stroke="currentColor" strokeWidth="1.2"/></svg>),
  play: () => (<svg width="12" height="12" viewBox="0 0 16 16" fill="none">
    <path d="M4 2v12l10-6L4 2z" fill="currentColor"/></svg>),
  send: () => (<svg width="13" height="13" viewBox="0 0 16 16" fill="none">
    <path d="M2 8l12-6-4 12-2-5-6-1z" stroke="currentColor" strokeWidth="1.2" strokeLinejoin="round"/></svg>),
  paperclip: () => (<svg width="13" height="13" viewBox="0 0 16 16" fill="none">
    <path d="M11 5L5.5 10.5a2 2 0 0 0 2.8 2.8l6-6a4 4 0 0 0-5.7-5.7l-6.3 6.3a6 6 0 0 0 8.5 8.5L14 13" stroke="currentColor" strokeWidth="1.1"/></svg>),
  mic: () => (<svg width="13" height="13" viewBox="0 0 16 16" fill="none">
    <rect x="6" y="2" width="4" height="8" rx="2" stroke="currentColor" strokeWidth="1.2"/>
    <path d="M3 8a5 5 0 0 0 10 0M8 13v2" stroke="currentColor" strokeWidth="1.2"/></svg>),
  rec: () => (<svg width="10" height="10" viewBox="0 0 10 10"><circle cx="5" cy="5" r="4" fill="#b53a2a"/></svg>),
  chevR: () => (<svg width="9" height="9" viewBox="0 0 10 10" fill="none"><path d="M3 1l4 4-4 4" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/></svg>),
  plus: () => (<svg width="12" height="12" viewBox="0 0 12 12" fill="none"><path d="M6 1v10M1 6h10" stroke="currentColor" strokeWidth="1.4"/></svg>),
  sun: () => (<svg width="12" height="12" viewBox="0 0 16 16" fill="none">
    <circle cx="8" cy="8" r="3" stroke="currentColor" strokeWidth="1.3"/>
    <path d="M8 1.5v1.8M8 12.7v1.8M2.6 8h1.8M11.6 8h1.8M3.7 3.7l1.3 1.3M11 11l1.3 1.3M3.7 12.3l1.3-1.3M11 5l1.3-1.3" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/></svg>),
  moon: () => (<svg width="12" height="12" viewBox="0 0 16 16" fill="none">
    <path d="M13.4 9.6A5.6 5.6 0 0 1 6.4 2.6a5.6 5.6 0 1 0 7 7z" stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round"/></svg>),
};

// ── Top bar ────────────────────────────────────────────────────────────────
function TopBar({ scenarioName, onOpenSession, onOpenTrace, logfireUrl, backendStatus, sessionId, darkTheme, onToggleTheme }) {
  const traceLabel = logfireUrl
    ? `logfire ↗ trace#${logfireUrl.split("/").pop().slice(-8)}`
    : "logfire ↗ no trace yet";
  // When a real trace URL exists we open it in a new tab; otherwise fall
  // back to the existing decorative modal so the click still does something.
  const openTrace = (e) => {
    if (logfireUrl) {
      e.preventDefault();
      window.open(logfireUrl, "_blank", "noopener,noreferrer");
    } else {
      onOpenTrace && onOpenTrace();
    }
  };
  const statusClass = backendStatus === "loading" ? "warn"
                    : backendStatus === "error" ? "bad"
                    : "ok";
  const statusLabel = backendStatus === "loading" ? "running /api/run"
                    : backendStatus === "error" ? "backend error"
                    : "backend ready";
  return (
    <div className="topbar">
      <div className="topbar-left">
        <div className="brand">
          <span className="brand-mark">◤◢</span>
          <span className="brand-name">cafetwin</span>
          <span className="brand-ver">v0.4.2</span>
        </div>
        <div className="sep" />
        <button className="tb-btn" onClick={onOpenSession}>
          <span className="rec-dot"><Icon.rec /></span>
          <span>recording · 04:12</span>
        </button>
        <button className="tb-btn" onClick={onOpenSession}>
          <span className="ico"><Icon.play /></span>
          <span>session.replay</span>
        </button>
        <button className={`tb-btn ${logfireUrl ? "" : "tb-btn-disabled"}`}
          onClick={openTrace} title={logfireUrl || "Logfire trace URL not set — see app/logfire_setup.py"}>
          <span className="logfire-mark" />
          <span>{traceLabel}</span>
        </button>
      </div>
      <div className="topbar-right">
        <div className="status"><span className={`status-dot ${statusClass}`} /><span>session:{sessionId || "?"} · {statusLabel}</span></div>
        <div className="status"><span className="status-dot warn" /><span>tokens 142.3k / 200k</span></div>
        <button className={`tb-btn tb-theme ${darkTheme ? "tb-theme-dark" : ""}`}
          onClick={() => onToggleTheme && onToggleTheme(!darkTheme)}
          title={darkTheme ? "switch to light theme" : "switch to dark theme"}
          aria-label={darkTheme ? "switch to light theme" : "switch to dark theme"}>
          <span className="ico">{darkTheme ? <Icon.sun /> : <Icon.moon />}</span>
          <span>{darkTheme ? "light" : "dark"}</span>
        </button>
        <button className="tb-btn">share · {scenarioName}</button>
        <div className="avatar">JK</div>
      </div>
    </div>
  );
}

// ── Agent flow + controls + KPI panel ──────────────────────────────────────
function AgentNode({ I, name, state, latency, traceId }) {
  return (
    <div className={`agent-node state-${state}`}>
      <div className="an-row">
        <span className="an-ico"><I /></span>
        <span className="an-name">{name}</span>
        <span className="an-state">{state}</span>
      </div>
      <div className="an-meta">
        <span className="an-latency">{latency}</span>
        <span className="an-trace">{traceId}</span>
      </div>
      {state === "running" && <div className="an-progress" />}
    </div>
  );
}

function AgentFlow({
  active, base, scenario,
  stages, backendLoading, backendError, usedFallback,
  onTweakSeats, onTweakBaristas, onTweakFootfall, onOpenKpi,
}) {
  // Backend RunResponse.stages[] carries 3 stage timings; the existing flow
  // shows 5 visual nodes (vision/kpi/pattern share evidence_pack; optimize ↔
  // optimization_agent; memory ↔ memory_write). See overview_plan §Frontend
  // stage timestamps → flow canvas nodes.
  const stageByName = {};
  if (Array.isArray(stages)) for (const s of stages) stageByName[s.name] = s;

  const nodeState = (stageName) => {
    if (backendError) return "error";
    if (stageByName[stageName]) return "ok";
    if (backendLoading) return "running";
    return "queued";
  };
  const nodeLatency = (stageName) => fmtLatency(stageDurationMs(stageByName[stageName]));

  const traceShort = (() => {
    const first = Array.isArray(stages) && stages[0];
    if (!first) return "—";
    const t = Date.parse(first.started_at);
    return Number.isNaN(t) ? "—" : `t${String(t).slice(-6)}`;
  })();

  const nodes = [
    { I: Icon.eye, name: "vision", state: nodeState("evidence_pack"), latency: nodeLatency("evidence_pack"), traceId: traceShort },
    { I: Icon.bar, name: "kpi", state: nodeState("evidence_pack"), latency: nodeLatency("evidence_pack"), traceId: traceShort },
    { I: Icon.grid, name: "pattern", state: nodeState("evidence_pack"), latency: nodeLatency("evidence_pack"), traceId: traceShort },
    { I: Icon.flask, name: "optimize", state: nodeState("optimization_agent"), latency: nodeLatency("optimization_agent"), traceId: traceShort },
    { I: Icon.play, name: "memory", state: nodeState("memory_write"), latency: nodeLatency("memory_write"), traceId: traceShort },
  ];

  const flowSubLabel = backendError
    ? "backend error"
    : backendLoading
      ? "running /api/run…"
      : usedFallback
        ? "5 nodes · DAG · cached fallback"
        : "5 nodes · DAG";

  const k = active.kpis;
  const b = base.kpis;
  return (
    <div className="panel panel-flow">
      <div className="panel-hd"><span className="panel-title">agent_graph</span><span className="panel-sub">{flowSubLabel}</span></div>
      <div className="agent-flow">
        {nodes.map((n, i) => (
          <React.Fragment key={n.name}>
            <AgentNode {...n} />
            {i < nodes.length - 1 && <div className="an-edge" />}
          </React.Fragment>
        ))}
      </div>
      <div className="panel-hd panel-hd-sub">
        <span className="panel-title">controls</span>
        <span className="panel-sub">edits ↦ <b className="ctrl-target">{scenario.name}</b></span>
      </div>
      <div className="ctrl-applies">
        <span className="ctrl-applies-dot" />
        <span>live edit · canvas re-flows on drag</span>
        <span className="ctrl-applies-spacer" />
        <span className="ctrl-applies-meta">{Math.ceil(scenario.seats / 3)} tables · {scenario.seats} chairs · {scenario.baristas} staff</span>
      </div>
      <div className="ctrl-grid">
        <ControlSlider label="seats" value={scenario.seats} min={6} max={240} onChange={onTweakSeats}
          hint={`≈ ${Math.ceil(scenario.seats / 3)} tables`} />
        <ControlSlider label="baristas" value={scenario.baristas} min={1} max={20} onChange={onTweakBaristas}
          hint={`${(scenario.footfall / Math.max(1, scenario.baristas)).toFixed(0)}/hr per`} />
        <ControlSlider label="footfall.λ" value={scenario.footfall} min={0} max={600} unit="/hr" onChange={onTweakFootfall}
          hint={scenario.footfall > 200 ? "rush" : scenario.footfall > 80 ? "steady" : "quiet"} />
      </div>
      <div className="panel-hd panel-hd-sub">
        <button className="kpi-link" onClick={onOpenKpi}><span className="panel-title">kpi · {scenario.name}</span></button>
        <span className="panel-sub">vs baseline</span>
      </div>
      <div className="kpi-grid">
        <KpiCard label="throughput" value={k.throughput} unit="/hr" delta={deltaStr(k.throughput, b.throughput, "x")} up={k.throughput >= b.throughput} />
        <KpiCard label="avg.wait"   value={k.wait} unit="m:s" delta={deltaStr(b.waitSec, k.waitSec, "pct")} up={k.waitSec <= b.waitSec} />
        <KpiCard label="revenue/d"  value={fmtMoney(k.revenue)} unit="" delta={deltaStr(k.revenue, b.revenue, "x")} up={k.revenue >= b.revenue} />
        <KpiCard label="seat.util"  value={`${k.seatUtil}%`} unit="" delta={deltaStr(k.seatUtil, b.seatUtil, "pp")} warn={k.seatUtil > 90} />
        <KpiCard label="barista.util" value={`${k.baristaUtil}%`} unit="" delta={deltaStr(k.baristaUtil, b.baristaUtil, "pp")} warn={k.baristaUtil > 90} />
        <KpiCard label="queue.len"  value={k.queueLen} unit="avg" delta={deltaStr(k.queueLen, b.queueLen)} warn={k.queueLen > 3} />
        <KpiCard label="nps"        value={k.nps} unit="" delta={deltaStr(k.nps, b.nps)} up={k.nps >= b.nps} />
        <KpiCard label="margin"     value={`${k.margin}%`} unit="" delta={deltaStr(k.margin, b.margin, "pp")} up={k.margin >= b.margin} />
      </div>
    </div>
  );
}

function ControlSlider({ label, value, min, max, unit = "", onChange, hint }) {
  const pct = ((Number(value) - min) / (max - min)) * 100;
  return (
    <div className="ctrl-row">
      <div className="ctrl-lbl">
        <span>{label}</span>
        {hint && <span className="ctrl-hint">{hint}</span>}
        <span className="ctrl-val">{value}{unit && <em>{unit}</em>}</span>
      </div>
      <input type="range" className="ctrl-input" min={min} max={max} value={value}
        onChange={(e) => onChange && onChange(Number(e.target.value))} />
      <div className="ctrl-track-vis">
        <div className="ctrl-fill" style={{ width: `${pct}%` }} />
        <div className="ctrl-thumb" style={{ left: `${pct}%` }} />
      </div>
      <div className="ctrl-scale"><span>{min}</span><span>{max}{unit}</span></div>
    </div>
  );
}

function KpiCard({ label, value, unit, delta, up, warn }) {
  const cls = "kpi-card" + (up ? " kpi-up" : "") + (warn ? " kpi-warn" : "");
  return (
    <div className={cls}>
      <div className="kpi-lbl">{label}</div>
      <div className="kpi-val">{value}<span className="kpi-unit">{unit}</span></div>
      <div className="kpi-delta">{delta}</div>
    </div>
  );
}

// ── Chat ────────────────────────────────────────────────────────────────
function ToolCall({ name, args, status, result }) {
  return (
    <div className={`tool-call status-${status}`}>
      <div className="tc-hd">
        <span className="tc-bar" /><span className="tc-name">tool · {name}</span>
        <span className="tc-status">{status}</span>
        {status === "running" && <span className="tc-spinner" />}
      </div>
      <pre className="tc-args">{args}</pre>
      {result && <div className="tc-result">{result}</div>}
    </div>
  );
}

function ChatMessage({ from, time, children, traceId }) {
  return (
    <div className={`chat-msg from-${from}`}>
      <div className="cm-hd">
        <span className="cm-from">{from === "user" ? "you" : "cafetwin.agent"}</span>
        <span className="cm-time">{time}</span>
        {traceId && <span className="cm-trace">{traceId}</span>}
      </div>
      <div className="cm-body">{children}</div>
    </div>
  );
}

// LiveRecommendation — renders the real OptimizationAgent LayoutChange
// inside the existing ToolCall visual frame, with Accept/Reject controls
// wired to /api/feedback via onSubmitFeedback. Replaces the previous mocked
// optimize.layout ToolCall.
function LiveRecommendation({
  layoutChange,
  priorRecommendationCount,
  usedFallback,
  loading,
  error,
  onSubmitFeedback,
  onDecision,
}) {
  const [feedback, setFeedback] = React.useState(null);
  const [submitting, setSubmitting] = React.useState(false);
  const [submitError, setSubmitError] = React.useState(null);

  // Reset internal feedback state when a fresh recommendation arrives so the
  // accept/reject buttons re-appear (and the iso scene's pending overlay
  // re-shows). Without this, a successful submit would lock the card on the
  // first fingerprint forever.
  const fingerprint = layoutChange && layoutChange.fingerprint;
  React.useEffect(() => {
    setFeedback(null);
    setSubmitError(null);
  }, [fingerprint]);

  const submit = async (decision) => {
    if (!onSubmitFeedback || submitting) return;
    setSubmitting(true);
    setSubmitError(null);
    try {
      const res = await onSubmitFeedback({ decision });
      const final = (res && res.decision) || decision;
      setFeedback({
        decision: final,
        mubitId: res && res.memory_record && res.memory_record.mubit_id,
        fallbackOnly: !!(res && res.memory_record && res.memory_record.fallback_only),
      });
      // Tell the parent so the iso canvas can switch from "pending overlay"
      // to "apply animation" (accept) or "stay put, hide overlay" (reject).
      if (onDecision) onDecision(final);
    } catch (e) {
      setSubmitError((e && e.message) || String(e));
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <ToolCall
        name="optimize.layout"
        status="running"
        args={JSON.stringify({
          phase: "evidence_pack → optimization_agent → memory_write",
        }, null, 2)}
      />
    );
  }
  if (error) {
    const apiBase = (typeof cafetwinApi !== "undefined" && cafetwinApi.base) || "?";
    return (
      <ToolCall
        name="optimize.layout"
        status="error"
        args={JSON.stringify({ error }, null, 2)}
        result={<>backend unavailable · check <code>{apiBase}</code></>}
      />
    );
  }
  if (!layoutChange) return null;

  const lc = layoutChange;
  const sim = lc.simulation;
  const args = JSON.stringify({
    target_id: lc.target_id,
    action: sim.action,
    from: sim.from_position,
    to: sim.to_position,
    evidence_ids: lc.evidence_ids,
  }, null, 2);
  const deltas = Object.entries(lc.expected_kpi_delta || {});
  const decisionControls = feedback ? (
    <div className={`rec-actions rec-done rec-${feedback.decision}`}>
      <span className="rec-done-label">
        {feedback.decision === "accept" ? "✓ accepted" : "✗ rejected"}
      </span>
      {feedback.mubitId && <code>{feedback.mubitId}</code>}
      {feedback.fallbackOnly && <span className="rec-meta-jl">jsonl-only</span>}
    </div>
  ) : (
    <div className="rec-actions">
      <button className="rec-btn rec-btn-accept" disabled={submitting}
        onClick={() => submit("accept")}>accept + apply</button>
      <button className="rec-btn rec-btn-reject" disabled={submitting}
        onClick={() => submit("reject")}>reject</button>
      {submitting && <span className="rec-meta-jl">writing memory…</span>}
      {submitError && <span className="rec-err">{submitError}</span>}
    </div>
  );

  return (
    <ToolCall
      name="optimize.layout"
      status="ok"
      args={args}
      result={
        <div className="rec-card">
          <div className="rec-hd">
            <span className="rec-title">{lc.title}</span>
            <span className={`rec-pill rec-risk-${lc.risk}`}>risk · {lc.risk}</span>
            <span className="rec-pill rec-conf">conf · {Math.round((lc.confidence || 0) * 100)}%</span>
            {priorRecommendationCount > 0 && (
              <span className="rec-pill rec-prior">seen {priorRecommendationCount}× before</span>
            )}
            {usedFallback && <span className="rec-pill rec-fallback">cached fallback</span>}
          </div>
          {decisionControls}
          <p className="rec-rationale">{lc.rationale}</p>
          <div className="rec-deltas">
            {deltas.map(([k, v]) => (
              <span key={k} className={`rec-delta ${v < 0 ? "good" : v > 0 ? "bad" : ""}`}>
                <em>{k}</em>
                <b>{v >= 0 ? "+" : ""}{v}</b>
              </span>
            ))}
          </div>
          <div className="rec-meta">
            <span>evidence:</span>
            {(lc.evidence_ids || []).map((eid) => <code key={eid}>{eid}</code>)}
            <span className="rec-meta-spacer" />
            <span><code>{sim.action}</code> · <code>{lc.target_id}</code></span>
          </div>
        </div>
      }
    />
  );
}

function ChatPanel({ scenario, kpis, base, onSend, draft, setDraft,
    layoutChange, priorRecommendationCount, usedFallback,
    backendLoading, backendError, onSubmitFeedback, onRecDecision }) {
  const isBaseline = scenario.name === "baseline";
  const args = JSON.stringify({
    scenario_id: scenario.name,
    seats: scenario.seats,
    baristas: scenario.baristas,
    footfall_per_hr: scenario.footfall,
    style: scenario.style,
    venue_footprint_m2: kpis.footprint,
  }, null, 2);

  // Scroll the *recommendation card* into view whenever a fresh one arrives
  // (new fingerprint). The buttons live right under the rec-hd inside the
  // card, so aligning the rec-card to the top of the chat-stream guarantees
  // the user sees title + accept/reject without further scrolling.
  // For the loading/error flip, just scroll to bottom so the spinner / error
  // tool-call lands in view.
  const streamRef = React.useRef(null);
  const fingerprint = layoutChange && layoutChange.fingerprint;
  React.useEffect(() => {
    const el = streamRef.current;
    if (!el) return;
    requestAnimationFrame(() => {
      const rec = el.querySelector(".rec-card");
      if (rec) {
        // Compute target scroll: align rec-card's top to chat-stream's top
        // (with a small offset for breathing room above).
        const elRect = el.getBoundingClientRect();
        const recRect = rec.getBoundingClientRect();
        const offset = (recRect.top - elRect.top) + el.scrollTop - 8;
        el.scrollTop = Math.max(0, offset);
      } else {
        el.scrollTop = el.scrollHeight;
      }
    });
  }, [fingerprint, backendLoading, backendError, scenario.name]);

  return (
    <div className="panel panel-chat">
      <div className="panel-hd"><span className="panel-title">scenario.chat</span><span className="panel-sub">claude-haiku · ctx 18.2k</span></div>
      <div className="chat-stream" ref={streamRef}>
        <div className="chat-divider"><span>session opened · 14:02:18</span></div>
        <ChatMessage from="agent" time="14:02:21" traceId="01h9k2..">
          <p>scanned <code>cafe_floor.mp4</code> · detected <b>{base.seats / 3 | 0} tables</b>, <b>{base.seats} chairs</b>, <b>{base.baristas} baristas</b>. footprint ≈ <b>{base.kpis.footprint} m²</b>.</p>
        </ChatMessage>

        {/* Live OptimizationAgent recommendation — replaces the previous mocked
            optimize.layout ToolCall. Always shown when the backend has produced
            a LayoutChange, regardless of the active scenario chip. */}
        <LiveRecommendation
          layoutChange={layoutChange}
          priorRecommendationCount={priorRecommendationCount}
          usedFallback={usedFallback}
          loading={backendLoading}
          error={backendError}
          onSubmitFeedback={onSubmitFeedback}
          onDecision={onRecDecision}
        />

        {!isBaseline && (
          <>
            <ChatMessage from="user" time="14:03:04">
              <p>simulate <b>{scenario.name}</b> — what changes?</p>
            </ChatMessage>
            <ChatMessage from="agent" time="14:03:06">
              <p>spawning scenario · holding constraints.</p>
            </ChatMessage>
            <ToolCall name="scenario.spawn" status="ok" args={args}
              result={<>✓ scenario <code>{scenario.name}</code> · {scenario.seats} seats · {scenario.baristas} baristas · footprint {kpis.footprint} m²</>} />
            <ChatMessage from="agent" time="14:03:09">
              <p>kpi delta: throughput <b>{deltaStr(kpis.throughput, base.kpis.throughput, "x")}</b>, wait <b>{deltaStr(base.kpis.waitSec, kpis.waitSec, "pct")}</b>, revenue/d <b>{fmtMoney(kpis.revenue)}</b>.</p>
            </ChatMessage>
          </>
        )}
        {isBaseline && (
          <ChatMessage from="agent" time="14:02:30">
            <p>baseline locked. type a prompt below to spawn a scenario, or pick one from the rail.</p>
          </ChatMessage>
        )}
      </div>
      <div className="chat-input">
        <div className="ci-row">
          <input className="ci-field" value={draft} onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && draft.trim()) { onSend(draft); } }}
            placeholder="describe a scenario… e.g. 'cut staff by half, weekday mornings only'" />
          <button className="ci-send" onClick={() => draft.trim() && onSend(draft)}><Icon.send /></button>
        </div>
        <div className="ci-tools">
          <button className="ci-tool"><Icon.paperclip /><span>image</span></button>
          <button className="ci-tool"><Icon.mic /><span>mic</span></button>
          <span className="ci-spacer" />
          <span className="ci-meta">⏎ send · ⌘⏎ run sim</span>
        </div>
      </div>
    </div>
  );
}

// ── Scenario rail ──────────────────────────────────────────────────────────
function Sparkline({ kpi, base, color }) {
  // generate sparkline based on throughput delta
  const ratio = kpi.throughput / Math.max(1, base.throughput);
  const pts = Array.from({ length: 11 }, (_, i) => {
    const baseY = 12;
    const target = baseY - Math.min(10, (ratio - 1) * 4 + (i / 10) * 1.5);
    const noise = ((i * 47) % 7) / 7 * 1.4 - 0.7;
    return `${i * 8},${(target + noise).toFixed(1)}`;
  }).join(" ");
  return (
    <svg viewBox="0 0 80 18" preserveAspectRatio="none" width="100%" height="18">
      <polyline fill="none" stroke={color || "currentColor"} strokeWidth="1" points={pts} />
    </svg>
  );
}

function Scenario({ scn, base, active, onClick, onOpen, ghost }) {
  const k = scn.kpis;
  const isRec = !!scn.isRecommended;
  const cls = `scn ${active ? "scn-active" : ""} ${ghost ? "scn-ghost" : ""} ${isRec ? "scn-recommended" : ""}`;
  // Recommended chip: surfaced from LayoutChange.expected_kpi_delta — these
  // are agent-native KPIs (staff_customer_crossings, queue_obstruction_seconds,
  // congestion_score, table_detour_score, staff_walk_distance_px), NOT the
  // decorative throughput/wait/revenue used by the rest of the rail. We pick
  // the two strongest signals (most-negative deltas) and render them as the
  // chip's two meta rows so the AI's promised wins are visible at a glance.
  if (isRec) {
    const lc = scn.layoutChange;
    const deltas = Object.entries(lc.expected_kpi_delta || {});
    // Sort by absolute magnitude (largest impact first); always show the
    // top 2 so the chip stays visually balanced.
    const ranked = [...deltas].sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]));
    const [topA, topB] = [ranked[0], ranked[1]];
    const fmtDelta = (v) => {
      if (v === 0) return "0";
      const formatted = Number.isInteger(v) ? v.toString() : v.toFixed(1);
      return v > 0 ? `+${formatted}` : formatted;  // toFixed already includes the "-" sign for negatives
    };
    // Compact labels for the 5 KPI fields the agent actually emits today.
    // Falling back to the raw key keeps the chip readable if the schema
    // grows without us updating this mapping.
    const KPI_LABEL = {
      staff_customer_crossings: "crossings",
      queue_obstruction_seconds: "queue obstr",
      congestion_score: "congestion",
      table_detour_score: "detour",
      staff_walk_distance_px: "walk dist",
    };
    const shortKey = (k) => KPI_LABEL[k] || k.replace(/_/g, " ");
    return (
      <div className={cls} onClick={onClick} onDoubleClick={onOpen}>
        <div className="scn-hd">
          <span className="scn-ai-badge" title="agent recommendation">AI</span>
          <span className="scn-name">{scn.name}</span>
          <span className="scn-id">#{scn.id}</span>
        </div>
        <div className="scn-spark"><Sparkline kpi={k} base={base.kpis} color="var(--accent-2)" /></div>
        {topA && (
          <div className="scn-meta">
            <span className="scn-kpi">{shortKey(topA[0])}</span>
            <span className={`scn-kpi-v ${topA[1] < 0 ? "good" : topA[1] > 0 ? "bad" : ""}`}>{fmtDelta(topA[1])}</span>
          </div>
        )}
        {topB ? (
          <div className="scn-meta">
            <span className="scn-kpi">{shortKey(topB[0])}</span>
            <span className={`scn-kpi-v ${topB[1] < 0 ? "good" : topB[1] > 0 ? "bad" : ""}`}>{fmtDelta(topB[1])}</span>
          </div>
        ) : (
          <div className="scn-meta">
            <span className="scn-kpi">conf</span>
            <span className="scn-kpi-v">{Math.round((lc.confidence || 0) * 100)}%</span>
          </div>
        )}
      </div>
    );
  }
  return (
    <div className={cls} onClick={onClick} onDoubleClick={onOpen}>
      <div className="scn-hd">
        <span className={`scn-dot ${active ? "on" : ""}`} />
        <span className="scn-name">{scn.name}</span>
        <span className="scn-id">#{scn.id}</span>
      </div>
      <div className="scn-spark"><Sparkline kpi={k} base={base.kpis} /></div>
      <div className="scn-meta">
        <span className="scn-kpi">Δ thru</span>
        <span className="scn-kpi-v">{scn.name === "baseline" ? "—" : deltaStr(k.throughput, base.kpis.throughput, "x")}</span>
      </div>
      <div className="scn-meta">
        <span className="scn-kpi">{scn.seats}s · {scn.baristas}b</span>
        <span className="scn-kpi-v">{fmtMoney(k.revenue)}</span>
      </div>
    </div>
  );
}

function ScenarioRail({ scenarios, base, activeName, onSelect, onOpen, onNew }) {
  return (
    <div className="rail">
      <div className="rail-hd">
        <span className="rail-title">scenarios</span>
        <span className="rail-sub">click ↦ switch · double-click ↦ inspect · ⇧+click ↦ pin</span>
        <span className="rail-spacer" />
        <span className="rail-meta">{scenarios.length} of {scenarios.length} · synced</span>
      </div>
      <div className="rail-track">
        {scenarios.map((s, i) => (
          <React.Fragment key={s.name}>
            <Scenario scn={s} base={base} active={s.name === activeName}
              onClick={() => onSelect(s.name)} onOpen={() => onOpen(s.name)} />
            {i < scenarios.length - 1 && <div className="rail-arrow"><Icon.chevR /></div>}
          </React.Fragment>
        ))}
        <button className="scn-add" onClick={onNew}><Icon.plus /><span>new scenario</span></button>
      </div>
    </div>
  );
}

Object.assign(window, { TopBar, AgentFlow, ChatPanel, ScenarioRail, LiveRecommendation });
