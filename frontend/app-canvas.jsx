// app-canvas.jsx — Center canvas with split compare + sim time scrubber

// Layer toggles wired to actual overlay rendering. Other entries in the chip
// row (geom/people/paths) flip state but have no visible effect yet — they
// are kept as design intent for Tier 2 and visually marked as stubs.
const ACTIVE_LAYERS = new Set(["heat", "grid"]);

function CanvasToolbar({ split, setSplit, layers, setLayers, zoom, setZoom }) {
  const toggle = (k) => setLayers({ ...layers, [k]: !layers[k] });
  return (
    <div className="cv-toolbar">
      <div className="cv-tg">
        <span className="cv-lbl">view</span>
        <div className="cv-seg">
          <button className="active" title="isometric view">iso</button>
          <button className="cv-stub" disabled title="plan view — not implemented in MVP">plan</button>
          <button className="cv-stub" disabled title="3D view — not implemented in MVP">3d</button>
        </div>
      </div>
      <div className="cv-tg">
        <span className="cv-lbl">layer</span>
        <div className="cv-chips">
          {["geom", "people", "heat", "paths", "grid"].map((k) => {
            const wired = ACTIVE_LAYERS.has(k);
            const cls = `cv-chip ${layers[k] ? "on" : ""}${wired ? "" : " cv-chip-stub"}`;
            const tip = wired ? `${k} layer` : `${k} layer — preview only (no overlay yet)`;
            return (
              <span key={k} className={cls} onClick={() => toggle(k)} title={tip}>{k}</span>
            );
          })}
        </div>
      </div>
      <span className="cv-spacer" />
      <div className="cv-tg">
        <span className="cv-lbl">compare</span>
        <button className={`cv-toggle ${split ? "on" : ""}`} onClick={() => setSplit(!split)}>
          <span className="cv-toggle-dot" />
          <span>{split ? "split.on" : "split.off"}</span>
        </button>
      </div>
      <div className="cv-zoom">
        <button onClick={() => setZoom(Math.max(0.5, zoom - 0.1))}>−</button>
        <span>{zoom.toFixed(2)}×</span>
        <button onClick={() => setZoom(Math.min(2, zoom + 0.1))}>+</button>
      </div>
    </div>
  );
}

function CanvasOverlay({ label, sub, side, kpi }) {
  return (
    <div className={`cv-overlay cv-overlay-${side}`}>
      <div className="cv-ov-tag">
        <span className={`cv-ov-dot ${side}`} />
        <span className="cv-ov-name">{label}</span>
        <span className="cv-ov-sub">{sub}</span>
      </div>
      <div className="cv-ov-kpis">
        {kpi.map((k, i) => (
          <div key={i} className="cv-ov-kpi"><span>{k.l}</span><b>{k.v}</b></div>
        ))}
      </div>
    </div>
  );
}

function CanvasPane({ scn, side, zoom, layers, simTime, running, speed, recommendation }) {
  const k = scn.kpis;
  return (
    <div className="cv-pane">
      <div className="cv-axes">
        <span>x →</span><span>↓ y</span><span>↗ z</span>
      </div>
      <div className="cv-stage" style={{ transform: `scale(${zoom})` }}>
        <CafeScene seats={scn.seats} baristas={scn.baristas} style={scn.style}
          scenarioName={scn.name} footfall={scn.footfall}
          simTime={simTime} running={running} speed={speed}
          recommendation={recommendation} />
      </div>
      {layers.heat && <div className="cv-heat" />}
      {layers.grid && <div className="cv-grid-overlay" />}
      <CanvasOverlay label={scn.name} sub={`${k.footprint} m² · ${scn.seats}s/${scn.baristas}b`} side={side}
        kpi={[
          { l: "thru", v: `${k.throughput}/h` },
          { l: "wait", v: k.wait },
          { l: "rev",  v: fmtMoney(k.revenue) },
        ]} />
    </div>
  );
}

// Time bar: scrubbable timeline, play/pause, speed
function TimeBar({ simTime, setSimTime, running, setRunning, speed, setSpeed, dayLength }) {
  // Sim "minute" maps to clock 07:00 → 19:00 across simTime 0..dayLength
  const totalMin = 12 * 60;
  const clockMin = 7 * 60 + Math.floor((simTime / dayLength) * totalMin);
  const hh = Math.floor(clockMin / 60) % 24;
  const mm = clockMin % 60;
  const stamp = `${String(hh).padStart(2, "0")}:${String(mm).padStart(2, "0")}`;
  const pct = Math.min(100, (simTime / dayLength) * 100);

  // labels under the track
  const hours = ["07", "09", "11", "13", "15", "17", "19"];

  const speeds = [0.5, 1, 2, 4, 8, 16];

  const onScrub = (e) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const x = (e.clientX - rect.left) / rect.width;
    const t = Math.max(0, Math.min(1, x)) * dayLength;
    setSimTime(t);
  };

  return (
    <div className="cv-footer">
      <div className="cv-time-ctrls">
        <button className={`cv-pp ${running ? "playing" : ""}`} onClick={() => setRunning(!running)}
          title={running ? "pause" : "play"}>
          {running
            ? <svg width="10" height="10" viewBox="0 0 10 10"><rect x="2" y="1" width="2.4" height="8" fill="currentColor"/><rect x="5.6" y="1" width="2.4" height="8" fill="currentColor"/></svg>
            : <svg width="10" height="10" viewBox="0 0 10 10"><path d="M2 1v8l7-4z" fill="currentColor"/></svg>}
        </button>
        <button className="cv-pp cv-pp-rw" onClick={() => setSimTime(0)} title="reset">
          <svg width="10" height="10" viewBox="0 0 10 10"><path d="M3 1v8M9 1L4 5l5 4z" fill="currentColor"/></svg>
        </button>
      </div>
      <div className="cv-time-lbl">sim.t</div>
      <div className="cv-time" onMouseDown={(e) => { onScrub(e);
        const move = (ev) => onScrub(ev);
        const up = () => { window.removeEventListener("mousemove", move); window.removeEventListener("mouseup", up); };
        window.addEventListener("mousemove", move);
        window.addEventListener("mouseup", up);
      }}>
        <div className="cv-time-fill" style={{ width: `${pct}%` }} />
        <div className="cv-time-thumb" style={{ left: `${pct}%` }} />
        <div className="cv-time-marks">
          {Array.from({ length: 13 }).map((_, i) => (
            <span key={i} style={{ left: `${(i / 12) * 100}%` }} />
          ))}
        </div>
        <div className="cv-time-axis">
          {hours.map((h, i) => (
            <span key={i} style={{ left: `${(i / (hours.length - 1)) * 100}%` }}>{h}:00</span>
          ))}
        </div>
      </div>
      <div className="cv-time-stamp">
        <span className="cv-clock">{stamp}</span>
        <span className="cv-day">day 1</span>
      </div>
      <div className="cv-speed">
        {speeds.map((s) => (
          <button key={s} className={`cv-speed-btn ${speed === s ? "active" : ""}`}
            onClick={() => setSpeed(s)}>×{s}</button>
        ))}
      </div>
    </div>
  );
}

function MainCanvas({ split, setSplit, active, base, layers, setLayers, zoom, setZoom,
                     simTime, setSimTime, running, setRunning, speed, setSpeed, dayLength,
                     recommendation }) {
  // The agent's LayoutChange is always rendered against the *active*
  // scenario (right pane in split mode, the only pane otherwise). The
  // baseline pane stays untouched so the user can see "before vs proposed"
  // without the proposal contaminating the baseline frame.
  return (
    <div className="canvas">
      <CanvasToolbar split={split} setSplit={setSplit} layers={layers} setLayers={setLayers} zoom={zoom} setZoom={setZoom} />
      <div className={`cv-stage-wrap ${split ? "cv-split" : ""}`}>
        {split ? (
          <>
            <CanvasPane scn={base} side="left" zoom={zoom} layers={layers}
              simTime={simTime} running={running} speed={speed} />
            <div className="cv-divider"><div className="cv-divider-handle"><span>‖</span></div></div>
            <CanvasPane scn={active} side="right" zoom={zoom} layers={layers}
              simTime={simTime} running={running} speed={speed}
              recommendation={recommendation} />
          </>
        ) : (
          <CanvasPane scn={active} side="right" zoom={zoom} layers={layers}
            simTime={simTime} running={running} speed={speed}
            recommendation={recommendation} />
        )}
      </div>
      <TimeBar simTime={simTime} setSimTime={setSimTime}
        running={running} setRunning={setRunning}
        speed={speed} setSpeed={setSpeed} dayLength={dayLength} />
    </div>
  );
}

Object.assign(window, { MainCanvas });
