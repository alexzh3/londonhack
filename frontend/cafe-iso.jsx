// cafe-iso.jsx — Procedural isometric SVG cafe with live simulation

const ISO = {
  tileW: 56,
  tileH: 28,
  toScreen(x, y) {
    return { sx: (x - y) * (this.tileW / 2), sy: (x + y) * (this.tileH / 2) };
  },
};

function shade(hex, pct) {
  const h = hex.replace("#", "");
  const r = parseInt(h.slice(0, 2), 16);
  const g = parseInt(h.slice(2, 4), 16);
  const b = parseInt(h.slice(4, 6), 16);
  const f = pct < 0 ? 0 : 255;
  const t = Math.abs(pct);
  const nr = Math.round((f - r) * t + r);
  const ng = Math.round((f - g) * t + g);
  const nb = Math.round((f - b) * t + b);
  return "#" + [nr, ng, nb].map(n => n.toString(16).padStart(2, "0")).join("");
}

// ── Primitives ─────────────────────────────────────────────────────────────
function FloorTile({ x, y, fill = "#ece5d3", stroke = "#d4ccb6" }) {
  const { sx, sy } = ISO.toScreen(x, y);
  const w = ISO.tileW / 2, h = ISO.tileH / 2;
  return (
    <polygon
      points={`${sx},${sy - h} ${sx + w},${sy} ${sx},${sy + h} ${sx - w},${sy}`}
      fill={fill} stroke={stroke} strokeWidth="0.5"
    />
  );
}

function IsoBox({ x, y, w = 1, d = 1, h = 14, top = "#cfc6ad", left = "#b8ad8e", right = "#9d9173", stroke = "#5a5238" }) {
  const c00 = ISO.toScreen(x - 0.5, y - 0.5);
  const c10 = ISO.toScreen(x + w - 0.5, y - 0.5);
  const c11 = ISO.toScreen(x + w - 0.5, y + d - 0.5);
  const c01 = ISO.toScreen(x - 0.5, y + d - 0.5);
  const top00 = { x: c00.sx, y: c00.sy - h };
  const top10 = { x: c10.sx, y: c10.sy - h };
  const top11 = { x: c11.sx, y: c11.sy - h };
  const top01 = { x: c01.sx, y: c01.sy - h };
  return (
    <g>
      <polygon points={`${c00.sx},${c00.sy} ${c01.sx},${c01.sy} ${top01.x},${top01.y} ${top00.x},${top00.y}`}
        fill={left} stroke={stroke} strokeWidth="0.5" />
      <polygon points={`${c01.sx},${c01.sy} ${c11.sx},${c11.sy} ${top11.x},${top11.y} ${top01.x},${top01.y}`}
        fill={right} stroke={stroke} strokeWidth="0.5" />
      <polygon points={`${top00.x},${top00.y} ${top10.x},${top10.y} ${top11.x},${top11.y} ${top01.x},${top01.y}`}
        fill={top} stroke={stroke} strokeWidth="0.5" />
    </g>
  );
}

function Chair({ x, y, color = "#a89878" }) {
  return (<IsoBox x={x} y={y} w={0.5} d={0.5} h={6}
    top={color} left={shade(color, -0.18)} right={shade(color, -0.32)} />);
}

function RoundTable({ x, y, color = "#8a6e54" }) {
  const { sx, sy } = ISO.toScreen(x, y);
  const lift = 12;
  return (
    <g>
      <rect x={sx - 1.5} y={sy - lift} width="3" height={lift} fill="#5a4632" />
      <ellipse cx={sx} cy={sy + 2} rx={ISO.tileW / 2.6} ry={ISO.tileH / 2.6} fill="#000" opacity="0.18" />
      <ellipse cx={sx} cy={sy - lift} rx={ISO.tileW / 2.6} ry={ISO.tileH / 2.6}
        fill={color} stroke={shade(color, -0.3)} strokeWidth="0.6" />
      <ellipse cx={sx - 4} cy={sy - lift - 2} rx={ISO.tileW / 4} ry={ISO.tileH / 4.5}
        fill={shade(color, 0.08)} opacity="0.6" />
    </g>
  );
}

// Person now supports an action label that floats above their head
function Person({ x, y, shirt = "#5a8047", role = "", action = "", walking = false, t = 0 }) {
  const { sx, sy } = ISO.toScreen(x, y);
  // tiny walk bob
  const bob = walking ? Math.sin(t * 8 + (x + y) * 5) * 1.0 : 0;
  const legSwing = walking ? Math.sin(t * 8 + (x + y) * 5) * 1.4 : 0;
  return (
    <g transform={`translate(0, ${bob.toFixed(2)})`}>
      <ellipse cx={sx} cy={sy + 1} rx="9" ry="3" fill="#000" opacity="0.18" />
      <rect x={sx - 4 - legSwing} y={sy - 12} width="3" height="12" fill="#3a3024" />
      <rect x={sx + 1 + legSwing} y={sy - 12} width="3" height="12" fill="#3a3024" />
      <path d={`M ${sx - 6} ${sy - 22} L ${sx + 6} ${sy - 22} L ${sx + 5} ${sy - 12} L ${sx - 5} ${sy - 12} Z`}
        fill={shirt} stroke={shade(shirt, -0.3)} strokeWidth="0.4" />
      <circle cx={sx} cy={sy - 26} r="4" fill="#d4a98c" stroke="#7a5436" strokeWidth="0.4" />
      {role === "barista" && (
        <rect x={sx - 5} y={sy - 31} width="10" height="3" fill="#fbf9f4" stroke="#5a5238" strokeWidth="0.3" />
      )}
      {action && (
        <g transform={`translate(${sx + 8}, ${sy - 30})`}>
          <rect x="0" y="-9" width={action.length * 4.6 + 8} height="12" rx="2"
            fill="rgba(255,253,247,0.92)" stroke="#5a5238" strokeWidth="0.4" />
          <text x="4" y="0" fontFamily="JetBrains Mono, monospace" fontSize="7"
            fill="#3a3024">{action}</text>
        </g>
      )}
    </g>
  );
}

function Plant({ x, y }) {
  const { sx, sy } = ISO.toScreen(x, y);
  return (
    <g>
      <rect x={sx - 5} y={sy - 5} width="10" height="6" fill="#7a5a3a" stroke="#3a2818" strokeWidth="0.4" />
      <circle cx={sx} cy={sy - 13} r="9" fill="#4a6e3a" />
      <circle cx={sx - 5} cy={sy - 16} r="6" fill="#5a8048" />
      <circle cx={sx + 4} cy={sy - 17} r="5" fill="#6b9656" />
    </g>
  );
}

function Counter({ x, y, w, d, style = "default", showFixtures = true }) {
  const palette = {
    default: { top: "#5a4836", left: "#46382a", right: "#33291e" },
    brooklyn: { top: "#3a2c1e", left: "#28201a", right: "#1a1410" },
    tokyo: { top: "#1f2528", left: "#171c1f", right: "#0f1416" },
  }[style] || { top: "#5a4836", left: "#46382a", right: "#33291e" };
  return (
    <g>
      <IsoBox x={x} y={y} w={w} d={d} h={18} {...palette} />
      {showFixtures && (
        <>
          <IsoBox x={x + 0.3} y={y + 0.2} w={0.6} d={0.6} h={26}
            top="#c8c4bb" left="#a09c93" right="#7a766d" />
          <IsoBox x={x + w - 0.9} y={y + 0.2} w={0.5} d={0.5} h={22}
            top="#3a3328" left="#2a251c" right="#1c1812" />
        </>
      )}
    </g>
  );
}

// Cosy lounge couch — long upholstered bench against the back wall, modelled
// after the brown leather couch behind the couple's table in the AI-cafe
// video. Built as a low base IsoBox plus three "cushion" IsoBoxes on top so
// it reads as a piece of seating, not a generic counter.
function Couch({ x, y, w = 2.6, d = 0.85 }) {
  const base = { top: "#7a4d36", left: "#5e3a26", right: "#46291a" };
  const cushion = { top: "#a36d50", left: "#8a563b", right: "#6e3f29" };
  const seatW = (w - 0.2) / 3;
  return (
    <g>
      <IsoBox x={x} y={y} w={w} d={d} h={6} {...base} />
      {[0, 1, 2].map((i) => (
        <IsoBox key={i} x={x + 0.1 + i * seatW} y={y + 0.05} w={seatW - 0.1} d={d - 0.1} h={11}
          {...cushion} />
      ))}
    </g>
  );
}

// Tall bookshelf against the back wall (the wood-and-books column behind
// the couch in the video). Renders as a slim deep IsoBox with a set of
// horizontal shelf strokes drawn on the front face.
function Bookshelf({ x, y, w = 1.4, d = 0.7 }) {
  const c00 = ISO.toScreen(x - 0.5, y - 0.5);
  const top = "#5a4030";
  const left = "#3e2c20";
  const right = "#2a1d14";
  const shelfH = 30;
  const lines = [];
  for (let i = 1; i <= 4; i++) {
    const y0 = c00.sy - shelfH * (i / 5);
    lines.push(
      <line key={i} x1={c00.sx} y1={y0} x2={c00.sx + (w * ISO.tileW) / 2} y2={y0 + (w * ISO.tileH) / 2}
        stroke="#8a6448" strokeWidth="0.6" opacity="0.7" />
    );
  }
  return (
    <g>
      <IsoBox x={x} y={y} w={w} d={d} h={shelfH} top={top} left={left} right={right} />
      {lines}
    </g>
  );
}

// Floor mat / area rug — drawn as a flat darker quadrilateral on top of
// the tile grid. Two of these run down the central walkway in the AI-cafe
// video; mirroring them in the iso scene grounds the layout visually.
function FloorMat({ x, y, w = 2, d = 1.5, color = "#5a3a28" }) {
  const c00 = ISO.toScreen(x - 0.5, y - 0.5);
  const c10 = ISO.toScreen(x + w - 0.5, y - 0.5);
  const c11 = ISO.toScreen(x + w - 0.5, y + d - 0.5);
  const c01 = ISO.toScreen(x - 0.5, y + d - 0.5);
  return (
    <polygon points={`${c00.sx},${c00.sy} ${c10.sx},${c10.sy} ${c11.sx},${c11.sy} ${c01.sx},${c01.sy}`}
      fill={color} stroke={shade(color, -0.25)} strokeWidth="0.4" opacity="0.85" />
  );
}

// ── Procedural layout ─────────────────────────────────────────────────────
// `EXPLICIT_BASELINE_LAYOUT` mirrors the AI-cafe video frame at
// `demo_data/sessions/ai_cafe_a/frame.jpg`. The reference image shows a
// long, narrow cafe with the counter running along the LEFT wall from
// the front (where the barista works at the espresso machine) all the way
// to the back, a brick alcove in the back-middle holding a brown leather
// couch + bookshelf + a few potted plants, and five 2-top tables spread
// across the right side of the floor (one near the couch, three along
// the right window wall, one in the central floor). Two dark floor mats
// run down the central walkway between the counter and the dining area.
//
// In iso tile coordinates, x grows left-to-right and y grows back-to-
// front, so the "left wall counter" maps to a low-x, varying-y strip and
// the "back wall alcove" sits at low-y. The layout also carries explicit
// `simPoints` so the procedural simulation (`useCafeSim`) puts the
// barista at her actual workstation and queues customers in the right
// place, instead of the default top-edge counter geometry that the
// procedural grid layouts assume.
const EXPLICIT_BASELINE_LAYOUT = {
  floorW: 14,
  floorH: 7,
  counterW: 2,
  // Single long counter along the LEFT WALL (not an L — the video shows
  // one continuous bar). `showFixtures` puts the espresso machine + cash
  // register on this segment.
  counterSegments: [
    { x: 0, y: 0, w: 2, d: 5.5, showFixtures: true },
  ],
  // Five 2-top tables. Index 0 is the "couple table" near the couch (the
  // natural target for service-lane-style moves). Positions chosen to
  // match the actual furniture footprint in the video.
  tablePositions: [
    { x: 5.5, y: 2.0 },     // T0: couple table near couch
    { x: 8.5, y: 2.4 },     // T1: middle-back table
    { x: 11.5, y: 2.0 },    // T2: back-right window table (newspaper guy)
    { x: 8.0, y: 4.5 },     // T3: middle-floor table
    { x: 11.5, y: 4.4 },    // T4: middle-right window
    { x: 12.0, y: 6.0 },    // T5: front-right window (woman with laptop)
  ],
  // 2 chairs per table — wood chairs in the video sit across from each
  // other on the long axis of the table, not around it.
  chairOffsets: [{ dx: -0.6, dy: 0 }, { dx: 0.6, dy: 0 }],
  // Back-wall alcove (couch + bookshelf + plants) and the central
  // walkway mats. Renderer sorts by sortY so order in this array doesn't
  // matter.
  extras: [
    { type: "couch", x: 7.0, y: 0.4, w: 2.6, d: 0.9 },
    { type: "bookshelf", x: 5.4, y: 0.0, w: 1.3, d: 0.7 },
    { type: "plant", x: 4.4, y: 0.3 },
    { type: "plant", x: 10.0, y: 0.3 },
    { type: "plant", x: 12.8, y: 0.4 },
    { type: "plant", x: 13.6, y: 5.5 },
    { type: "mat", x: 4.5, y: 3.6, w: 3.0, d: 1.4, color: "#5e3e2a" },
    { type: "mat", x: 4.5, y: 5.4, w: 3.0, d: 1.4, color: "#5e3e2a" },
  ],
  // Sim hints — where the barista lives, where customers queue, where
  // they walk to to order/wait/exit. With the counter on the LEFT wall,
  // these all live in the low-x band rather than the procedural default
  // (which assumes a top-edge counter at low y).
  simPoints: {
    // Barista stands inside the counter footprint; customers approach
    // from the right (interior of cafe).
    baristaHome: { x: 1.0, y: 3.5 },
    // Customer order point — in front of the counter, at espresso area.
    orderPoint: { x: 2.4, y: 4.0 },
    counterFront: { x: 2.2, y: 4.0 },
    // Queue grows downward (toward entrance) from the order point.
    queueFront: { x: 2.6, y: 5.0 },
    queueDx: 0.0,
    queueDy: 0.55,
    // Where customers wait for their drink (just to the right of order).
    waitPoint: { x: 3.5, y: 4.5 },
    // Customers enter from the bottom-right (door + windows in video)
    // and exit the same way.
    entryPoint: { x: 14.5, y: 7.5 },
    exitPoint: { x: 14.5, y: 7.5 },
    // Barista-make-drink station (stays inside counter, slightly back).
    makeDrinkPoint: { x: 0.7, y: 3.0 },
    // Barista-serve point at the front of the counter.
    servePoint: { x: 1.7, y: 4.0 },
  },
};


function generateLayout({ seats, baristas, style = "default", chairsPerTable = 3, name = "" }) {
  const shirtColors = ["#a86b4a", "#4a6a96", "#9a4a6a", "#c8a050", "#5a7a4a", "#a04050",
                       "#3d6f8a", "#8a4d3d", "#6e9050", "#a0805a", "#7a4a6a", "#506a96"];

  // The "baseline" scenario (and the agent's "recommended" derivative —
  // which is literally baseline + one table shifted) use an explicit
  // hand-tuned layout that matches the cafe in the looping CCTV pane next
  // to it (see frame.jpg in demo_data/sessions/ai_cafe_a/). All other
  // scenarios use the procedural grid below — they're "what-if" twins,
  // not 1:1 reproductions of any specific cafe, so the grid stays the
  // right tool for them.
  if (name === "baseline" || name === "recommended") {
    return {
      ...EXPLICIT_BASELINE_LAYOUT,
      baristas,
      style,
      shirtColors,
    };
  }

  const tables = Math.max(1, Math.ceil(seats / chairsPerTable));
  const cols = Math.max(2, Math.ceil(Math.sqrt(tables * 1.6)));
  const rows = Math.ceil(tables / cols);
  const xStep = 2.6, yStep = 2.6;
  const floorW = Math.max(8, cols * xStep + 3);
  const floorH = Math.max(6, rows * yStep + 2);
  const counterW = Math.min(floorW - 2, Math.max(3, Math.ceil(baristas * 1.4) + 2));

  const tablePositions = [];
  for (let i = 0; i < tables; i++) {
    const r = Math.floor(i / cols);
    const c = i % cols;
    tablePositions.push({ x: 1 + c * xStep, y: 2.5 + r * yStep });
  }

  const chairOffsets = [
    { dx: -0.6, dy: 0 }, { dx: 0.6, dy: 0 }, { dx: 0, dy: -0.6 }, { dx: 0, dy: 0.6 },
  ].slice(0, chairsPerTable);

  return {
    floorW: Math.ceil(floorW),
    floorH: Math.ceil(floorH),
    counterW,
    baristas,
    style,
    tablePositions,
    chairOffsets,
    shirtColors,
    extras: [],
    counterSegments: null,
  };
}

const STYLES = {
  default:  { tileA: "#ece5d3", tileB: "#e3dac3", tileEdge: "#cec4a8", baristaShirt: "#5a8047" },
  brooklyn: { tileA: "#cdb89a", tileB: "#bea787", tileEdge: "#9c8762", baristaShirt: "#4a3a2a" },
  tokyo:    { tileA: "#e8eaea", tileB: "#dcdfe0", tileEdge: "#bcc0c1", baristaShirt: "#1a1a1a" },
};

// ── Simulation ─────────────────────────────────────────────────────────────
// Customer states: walk_in → queue → order → wait_drink → walk_to_seat → seated → leaving
// Baristas: idle → taking_order → making_drink → serve → idle (cycle through orders)

function simHash(seed, i) {
  // deterministic-ish jitter
  const x = Math.sin(seed * 9301 + i * 49297) * 233280;
  return x - Math.floor(x);
}

function useCafeSim({ layout, footfall, scenarioKey, running = true, externalTime = null, speed = 1 }) {
  const [tick, setTick] = React.useState(0);
  const stateRef = React.useRef(null);
  const lastTimeRef = React.useRef(performance.now());
  const lastExtRef = React.useRef(externalTime);

  // (Re)init on layout/scenario change
  React.useEffect(() => {
    const customers = [];
    const baristas = [];
    // The procedural grid layout doesn't carry simPoints, so we synthesise
    // them from `counterW` / `floorH` and pretend the counter sits along
    // the top edge (legacy behaviour). The hand-tuned baseline overrides
    // these via `layout.simPoints` so its left-wall counter actually
    // gets queued against.
    const sp = layout.simPoints || {};
    const counterFront = sp.counterFront || { x: 1.2, y: 0.3 };
    const orderPoint   = sp.orderPoint   || { x: 1.5, y: 0.4 };
    const queueFront   = sp.queueFront   || { x: 2.2, y: 0.6 };
    const queueDx      = sp.queueDx ?? 0.55;
    const queueDy      = sp.queueDy ?? 0.18;
    const waitPoint    = sp.waitPoint    || { x: 1.0, y: 1.0 };
    const exitPoint    = sp.exitPoint    || { x: -0.5, y: layout.floorH + 0.5 };
    const entryPoint   = sp.entryPoint   || { x: layout.floorW + 0.5, y: layout.floorH + 0.5 };
    const makeDrink    = sp.makeDrinkPoint || null;
    const servePoint   = sp.servePoint    || null;

    for (let i = 0; i < layout.baristas; i++) {
      let bx, by;
      if (sp.baristaHome) {
        // Custom layout: spread the (potentially multiple) baristas
        // along the counter's vertical extent, since the counter is on
        // a wall, not the top edge.
        bx = sp.baristaHome.x;
        by = sp.baristaHome.y + (i - (layout.baristas - 1) / 2) * 1.0;
      } else {
        bx = 1.5 + (i / Math.max(1, layout.baristas - 1)) * (layout.counterW - 1.5);
        by = -1.2;
      }
      baristas.push({
        id: i, home: { x: bx, y: by },
        x: bx, y: by,
        target: { x: bx, y: by },
        state: "idle", action: "", busyUntil: 0,
      });
    }

    // pre-seed some customers already seated for non-empty starting state
    const seedCount = Math.min(layout.tablePositions.length,
      Math.floor(layout.tablePositions.length * (scenarioKey.includes("tokyo") ? 0.8 : scenarioKey.includes("brooklyn") ? 0.5 : 0.35)));
    for (let i = 0; i < seedCount; i++) {
      const t = layout.tablePositions[i];
      customers.push({
        id: -i - 1,
        x: t.x + 0.3, y: t.y + 0.3,
        target: { x: t.x + 0.3, y: t.y + 0.3 },
        state: "seated",
        action: simHash(i, 7) > 0.7 ? "sipping ☕" : "",
        seatedTable: i,
        shirt: layout.shirtColors[i % layout.shirtColors.length],
        spawned: 0,
        leaveAt: 8 + simHash(i, 11) * 30,
      });
    }

    stateRef.current = {
      customers, baristas,
      counterFront, orderPoint, exitPoint, entryPoint,
      queueFront, queueDx, queueDy, waitPoint, makeDrink, servePoint,
      time: 0, nextSpawn: 0,
      orderQueue: [],   // customer IDs waiting at counter
      drinkQueue: [],   // {custId, doneAt}
      tableUsed: new Array(layout.tablePositions.length).fill(false),
      nextId: 1,
      seed: Math.floor(Math.random() * 1000),
    };
    // mark seeded tables used
    for (let i = 0; i < seedCount; i++) stateRef.current.tableUsed[i] = true;

    setTick(t => t + 1);
  }, [layout.floorW, layout.floorH, layout.baristas, layout.tablePositions.length, scenarioKey]);

  // External-time mode: advance sim deterministically based on simTime delta
  React.useEffect(() => {
    if (externalTime == null) return;
    const S = stateRef.current;
    if (!S) return;
    const prev = lastExtRef.current ?? externalTime;
    let delta = externalTime - prev;
    lastExtRef.current = externalTime;
    if (delta < 0) {
      // scrubbed backward — re-init
      const customers = []; const baristas = [];
      for (let i = 0; i < layout.baristas; i++) {
        const bx = 1.5 + (i / Math.max(1, layout.baristas - 1)) * (layout.counterW - 1.5);
        baristas.push({ id: i, home: { x: bx, y: -1.2 }, x: bx, y: -1.2,
          target: { x: bx, y: -1.2 }, state: "idle", action: "", busyUntil: 0 });
      }
      stateRef.current = { ...S, customers, baristas, time: externalTime,
        nextSpawn: externalTime, orderQueue: [], drinkQueue: [],
        tableUsed: new Array(layout.tablePositions.length).fill(false), nextId: 1 };
      setTick(t => t + 1);
      return;
    }
    if (delta > 5) delta = 5; // cap big jumps
    // step in small chunks for stability
    const slices = Math.max(1, Math.ceil(delta / 0.05));
    for (let i = 0; i < slices; i++) step(delta / slices);
    setTick(t => (t + 1) % 1000000);
  }, [externalTime]);

  // RAF loop (only used when no external time control)
  React.useEffect(() => {
    if (externalTime != null) return;
    if (!running) return;
    let raf;
    const loop = (now) => {
      const dt = Math.min(0.05, (now - lastTimeRef.current) / 1000) * speed;
      lastTimeRef.current = now;
      step(dt);
      setTick(t => (t + 1) % 1000000);
      raf = requestAnimationFrame(loop);
    };
    lastTimeRef.current = performance.now();
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, [running, footfall, scenarioKey, speed, externalTime]);

  function step(dt) {
    const S = stateRef.current;
    if (!S) return;
    S.time += dt;

    // ── spawn customers based on footfall (lambda per hour, sim is sped up)
    const speedMult = 8;
    const spawnInterval = Math.max(0.6, 3600 / Math.max(1, footfall) / speedMult);
    if (S.time > S.nextSpawn && S.customers.filter(c => c.state !== "done").length < 18) {
      S.nextSpawn = S.time + spawnInterval * (0.7 + simHash(S.seed, S.nextId) * 0.6);
      S.customers.push({
        id: S.nextId++,
        x: S.entryPoint.x, y: S.entryPoint.y,
        target: { ...S.entryPoint },
        state: "walk_in",
        action: "",
        seatedTable: -1,
        shirt: layout.shirtColors[(S.nextId * 3) % layout.shirtColors.length],
        spawned: S.time,
        leaveAt: 0,
      });
    }

    // ── walk all entities toward their target
    const moveSpeed = 2.2;
    const moveTo = (e, target, speed = moveSpeed) => {
      const dx = target.x - e.x, dy = target.y - e.y;
      const d = Math.hypot(dx, dy);
      if (d < 0.05) { e.x = target.x; e.y = target.y; return true; }
      const v = Math.min(d, speed * dt);
      e.x += (dx / d) * v; e.y += (dy / d) * v;
      return false;
    };

    // ── customer state machine
    const queueFront = { x: 2.2, y: 0.6 };
    S.customers.forEach((c) => {
      switch (c.state) {
        case "walk_in": {
          // walk toward back of queue
          const slot = S.orderQueue.length;
          const target = { x: queueFront.x + slot * 0.55, y: queueFront.y + slot * 0.18 };
          c.target = target;
          c.action = "";
          if (moveTo(c, target)) {
            c.state = "queue";
            S.orderQueue.push(c.id);
          }
          break;
        }
        case "queue": {
          // shuffle forward as queue advances
          const idx = S.orderQueue.indexOf(c.id);
          if (idx === 0) {
            c.action = "ordering";
            // wait for a free barista
            const free = S.baristas.find(b => b.state === "idle");
            if (free) {
              free.state = "taking_order";
              free.target = { x: free.home.x, y: 0.1 };
              free.action = "taking order";
              free.busyUntil = S.time + 1.6;
              free.assignedCust = c.id;
              c.state = "ordering";
              S.orderQueue.shift();
            }
          } else {
            const target = { x: queueFront.x + idx * 0.55, y: queueFront.y + idx * 0.18 };
            c.target = target;
            c.action = idx === 1 ? "next" : "";
            moveTo(c, target);
          }
          break;
        }
        case "ordering": {
          c.target = S.orderPoint;
          moveTo(c, S.orderPoint);
          c.action = "ordering";
          // wait for barista to finish taking order
          const b = S.baristas.find(x => x.assignedCust === c.id);
          if (!b || b.state === "making_drink" || b.state === "serve") {
            c.state = "wait_drink";
            c.action = "waiting";
            c.target = { x: 1.0, y: 1.0 };
          }
          break;
        }
        case "wait_drink": {
          c.target = { x: 1.0, y: 1.0 };
          moveTo(c, c.target);
          // when barista delivers to drink_queue with this customer's id, we proceed
          if (c.gotDrink) {
            // pick a free table
            const tIdx = S.tableUsed.findIndex(u => !u);
            if (tIdx >= 0) {
              S.tableUsed[tIdx] = true;
              c.seatedTable = tIdx;
              const t = layout.tablePositions[tIdx];
              c.target = { x: t.x + 0.3, y: t.y + 0.3 };
              c.state = "walk_to_seat";
              c.action = "☕ → seat";
            } else {
              // no seat — leave
              c.state = "leaving";
              c.action = "to-go";
              c.target = S.exitPoint;
            }
          } else {
            c.action = "waiting";
          }
          break;
        }
        case "walk_to_seat": {
          if (moveTo(c, c.target)) {
            c.state = "seated";
            c.seatedAt = S.time;
            c.leaveAt = S.time + 14 + simHash(S.seed, c.id) * 18;
            c.action = "sipping ☕";
          }
          break;
        }
        case "seated": {
          if (S.time > c.leaveAt) {
            c.state = "leaving";
            c.action = "leaving";
            if (c.seatedTable >= 0) S.tableUsed[c.seatedTable] = false;
            c.seatedTable = -1;
            c.target = S.exitPoint;
          } else if (S.time - c.seatedAt > 4 && simHash(S.seed, c.id + Math.floor(S.time)) > 0.97) {
            c.action = simHash(S.seed, c.id) > 0.5 ? "chatting" : "sipping ☕";
          }
          break;
        }
        case "leaving": {
          if (moveTo(c, c.target)) {
            c.state = "done";
          }
          break;
        }
      }
    });

    // ── barista state machine
    S.baristas.forEach((b) => {
      switch (b.state) {
        case "idle": {
          b.action = "";
          moveTo(b, b.home, 1.2);
          break;
        }
        case "taking_order": {
          moveTo(b, b.target);
          b.action = "taking order";
          if (S.time >= b.busyUntil) {
            b.state = "making_drink";
            b.target = { x: b.home.x + 0.4, y: -1.4 };
            b.action = "making ☕";
            b.busyUntil = S.time + 2.6 + simHash(S.seed, b.id) * 1.4;
          }
          break;
        }
        case "making_drink": {
          moveTo(b, b.target);
          b.action = "making ☕";
          if (S.time >= b.busyUntil) {
            b.state = "serve";
            b.target = { x: b.home.x, y: -0.1 };
            b.action = "serving";
            b.busyUntil = S.time + 0.8;
          }
          break;
        }
        case "serve": {
          moveTo(b, b.target);
          b.action = "serving";
          if (S.time >= b.busyUntil) {
            // mark customer's drink ready
            const cust = S.customers.find(c => c.id === b.assignedCust);
            if (cust) cust.gotDrink = true;
            b.assignedCust = null;
            b.state = "idle";
            b.action = "";
          }
          break;
        }
      }
    });

    // ── compact done customers occasionally
    if (S.customers.filter(c => c.state === "done").length > 30) {
      S.customers = S.customers.filter(c => c.state !== "done");
    }
  }

  return { state: stateRef.current, tick };
}

// ── Recommendation helpers ────────────────────────────────────────────────
// The OptimizationAgent emits LayoutChange.simulation with from_position /
// to_position in *camera-frame pixels* (see object_inventory.json for the
// canonical coordinate system). The procedural iso scene works in *tile
// units* and doesn't share IDs with the fixture (no `table_center_1` here).
// To bridge: hash target_id -> deterministic table index, and convert the
// pixel delta to a clamped tile delta so the visible shift is meaningful
// without flying off-canvas if the agent emits an extreme move.
function _recHashStr(s) {
  let h = 0;
  for (let i = 0; i < s.length; i++) h = ((h << 5) - h + s.charCodeAt(i)) | 0;
  return Math.abs(h);
}

function _recClamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)); }

const REC_PX_PER_TILE = 80;
const REC_MAX_TILES = 2.0;

function recInfoFromLayout(layout, recommendation) {
  if (!recommendation || !layout || !layout.tablePositions || !layout.tablePositions.length) {
    return null;
  }
  const idx = _recHashStr(recommendation.targetId || "") % layout.tablePositions.length;
  const fromX = (recommendation.fromPosition && recommendation.fromPosition[0]) || 0;
  const fromY = (recommendation.fromPosition && recommendation.fromPosition[1]) || 0;
  const toX = (recommendation.toPosition && recommendation.toPosition[0]) || 0;
  const toY = (recommendation.toPosition && recommendation.toPosition[1]) || 0;
  const dxTile = _recClamp((toX - fromX) / REC_PX_PER_TILE, -REC_MAX_TILES, REC_MAX_TILES);
  const dyTile = _recClamp((toY - fromY) / REC_PX_PER_TILE, -REC_MAX_TILES, REC_MAX_TILES);
  return { idx, dxTile, dyTile, target: layout.tablePositions[idx] };
}

// Smooth scalar tween: animates the current value toward `target` over
// `durationMs` whenever target changes. When `key` changes (e.g. a fresh
// recommendation fingerprint), jump instantly without animating so a stale
// in-flight tween from the previous recommendation can't bleed into the new
// one. Uses cubic ease-out — feels like a confident snap into place rather
// than a sluggish drift.
function useScalarTween(target, durationMs = 700, key = "") {
  const [v, setV] = React.useState(target);
  const vRef = React.useRef(target);
  const targetRef = React.useRef(target);
  const fromRef = React.useRef(target);
  const keyRef = React.useRef(key);

  React.useEffect(() => { vRef.current = v; }, [v]);

  React.useEffect(() => {
    if (key !== keyRef.current) {
      keyRef.current = key;
      targetRef.current = target;
      fromRef.current = target;
      vRef.current = target;
      setV(target);
      return;
    }
    if (target === targetRef.current) return;
    fromRef.current = vRef.current;
    targetRef.current = target;
    const start = performance.now();
    let raf;
    const ease = (t) => 1 - Math.pow(1 - t, 3);
    const loop = (now) => {
      const t = Math.min(1, (now - start) / durationMs);
      const next = fromRef.current + (target - fromRef.current) * ease(t);
      setV(next);
      if (t < 1) raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => { if (raf) cancelAnimationFrame(raf); };
  }, [target, key, durationMs]);

  return v;
}

// Pulsing ring at the original table + dashed ghost at the proposed
// destination + direction arrow with "AI · proposed shift" label. Rendered
// only while status is "pending" (no decision yet); disappears once the
// user clicks accept (animation takes over) or reject (table stays put).
function RecOverlay({ recInfo }) {
  const a = ISO.toScreen(recInfo.target.x, recInfo.target.y);
  const b = ISO.toScreen(recInfo.target.x + recInfo.dxTile, recInfo.target.y + recInfo.dyTile);
  const rxA = ISO.tileW * 0.7, ryA = ISO.tileH * 0.7;
  const rxB = ISO.tileW * 0.65, ryB = ISO.tileH * 0.65;
  return (
    <g style={{ pointerEvents: "none" }}>
      <ellipse cx={a.sx} cy={a.sy} rx={rxA} ry={ryA}
        fill="none" stroke="#f4a73e" strokeWidth="2">
        <animate attributeName="rx" values={`${rxA};${rxA * 1.25};${rxA}`}
          dur="1.6s" repeatCount="indefinite" />
        <animate attributeName="ry" values={`${ryA};${ryA * 1.25};${ryA}`}
          dur="1.6s" repeatCount="indefinite" />
        <animate attributeName="opacity" values="0.95;0.45;0.95"
          dur="1.6s" repeatCount="indefinite" />
      </ellipse>
      <ellipse cx={b.sx} cy={b.sy} rx={rxB} ry={ryB}
        fill="rgba(244,167,62,0.18)" stroke="#f4a73e" strokeWidth="1.5"
        strokeDasharray="4 3" />
      <line x1={a.sx} y1={a.sy} x2={b.sx} y2={b.sy}
        stroke="#f4a73e" strokeWidth="2.2" strokeLinecap="round"
        markerEnd="url(#rec-arrow-head)" opacity="0.9" />
      <text x={(a.sx + b.sx) / 2} y={Math.min(a.sy, b.sy) - 14}
        fill="#7a4a18" fontSize="10" fontWeight="600" textAnchor="middle">
        AI · proposed shift
      </text>
    </g>
  );
}

// ── Renderer ──────────────────────────────────────────────────────────────
function CafeLayout({ layout, sim, recInfo, recTween = 0 }) {
  const s = STYLES[layout.style] || STYLES.default;
  const floor = [];
  for (let y = -1; y <= layout.floorH; y++) {
    for (let x = -1; x <= layout.floorW; x++) {
      const alt = (x + y) % 2 === 0;
      floor.push(<FloorTile key={`f${x}_${y}`} x={x} y={y}
        fill={alt ? s.tileA : s.tileB} stroke={s.tileEdge} />);
    }
  }

  // Floor mats render *under* every other entity but *over* the floor tile
  // grid, so they're added separately from the sortY-stacked `objects`
  // list. Only baseline carries mats today (extras list).
  const matEls = (layout.extras || [])
    .filter((e) => e.type === "mat")
    .map((e, i) => (<FloorMat key={`mat${i}`} x={e.x} y={e.y} w={e.w} d={e.d} color={e.color} />));

  const objects = [];

  // Counter — multi-segment when the layout supplies `counterSegments`
  // (baseline = L-shape espresso bar + register column), otherwise the
  // single-segment top-edge counter the procedural layout produces.
  if (layout.counterSegments && layout.counterSegments.length) {
    layout.counterSegments.forEach((seg, i) => {
      objects.push({ key: `counter${i}`, sortY: seg.x + seg.y - 2,
        el: <Counter x={seg.x} y={seg.y} w={seg.w} d={seg.d}
              style={layout.style} showFixtures={seg.showFixtures !== false} /> });
    });
  } else {
    objects.push({ key: "counter", sortY: -2,
      el: <Counter x={1} y={-1} w={layout.counterW} d={1} style={layout.style} /> });
  }

  // Background extras (couch, bookshelf, plants) — opt-in via the layout's
  // `extras` array. Procedural scenarios fall back to the legacy
  // bottom-corner plants so the empty back wall doesn't read as bare.
  const extras = layout.extras || [];
  if (extras.length) {
    extras.forEach((e, i) => {
      if (e.type === "couch") {
        objects.push({ key: `couch${i}`, sortY: e.x + e.y,
          el: <Couch x={e.x} y={e.y} w={e.w} d={e.d} /> });
      } else if (e.type === "bookshelf") {
        objects.push({ key: `bs${i}`, sortY: e.x + e.y - 0.1,
          el: <Bookshelf x={e.x} y={e.y} w={e.w} d={e.d} /> });
      } else if (e.type === "plant") {
        objects.push({ key: `p${i}`, sortY: e.x + e.y, el: <Plant x={e.x} y={e.y} /> });
      }
      // mats are handled above (they render under everything else)
    });
  } else {
    objects.push({ key: "p1", sortY: layout.floorH, el: <Plant x={-1} y={layout.floorH - 1} /> });
    objects.push({ key: "p2", sortY: layout.floorH, el: <Plant x={layout.floorW - 1} y={layout.floorH - 1} /> });
  }

  // tables + chairs — when a recommendation is being applied, the target
  // table (and the chairs orbiting it) translate together by recTween *
  // (dxTile, dyTile). Other tables stay put. recTween is 0 while pending,
  // animates to 1 on accept; this layer doesn't care which.
  const tableOffset = (i) => {
    if (!recInfo || i !== recInfo.idx) return { dx: 0, dy: 0 };
    return { dx: recInfo.dxTile * recTween, dy: recInfo.dyTile * recTween };
  };
  layout.tablePositions.forEach((t, i) => {
    const off = tableOffset(i);
    const tx = t.x + off.dx, ty = t.y + off.dy;
    objects.push({ key: `t${i}`, sortY: tx + ty, el: <RoundTable x={tx} y={ty} /> });
    layout.chairOffsets.forEach((co, j) => {
      const cx = tx + co.dx, cy = ty + co.dy;
      objects.push({ key: `c${i}_${j}`, sortY: cx + cy - 0.01, el: <Chair x={cx} y={cy} /> });
    });
  });

  // baristas
  if (sim.state) {
    sim.state.baristas.forEach((b, i) => {
      const walking = Math.hypot(b.target.x - b.x, b.target.y - b.y) > 0.05;
      objects.push({ key: `b${i}`, sortY: b.y - 1.5,
        el: <Person x={b.x} y={b.y} shirt={s.baristaShirt} role="barista"
              action={b.action} walking={walking} t={sim.state.time} /> });
    });

    // customers — seated customers at the target table travel with it so
    // they don't end up floating where the table used to be. Walking
    // customers head for the original sim target (the procedural sim
    // doesn't know about the visual offset); for a 700ms apply animation
    // this is invisible enough.
    sim.state.customers.forEach((c) => {
      if (c.state === "done") return;
      const walking = c.state === "walk_in" || c.state === "walk_to_seat" || c.state === "leaving"
        || c.state === "queue" || c.state === "ordering";
      let cx = c.x, cy = c.y;
      if (recInfo && c.state === "seated" && c.seatedTable === recInfo.idx) {
        cx += recInfo.dxTile * recTween;
        cy += recInfo.dyTile * recTween;
      }
      objects.push({ key: `cu${c.id}`, sortY: cx + cy + (c.state === "seated" ? 0.4 : 0),
        el: <Person x={cx} y={cy} shirt={c.shirt}
              action={c.action} walking={walking} t={sim.state.time} /> });
    });
  }

  objects.sort((a, b) => a.sortY - b.sortY);
  return (
    <g>
      {floor}
      {matEls}
      {objects.map(o => <g key={o.key}>{o.el}</g>)}
    </g>
  );
}

function CafeScene({ seats = 18, baristas = 2, style = "default", scenarioName = "baseline",
                    footfall = 42, running = true, simTime = null, speed = 1,
                    recommendation = null }) {
  const layout = React.useMemo(() => generateLayout({
    seats, baristas, style, name: scenarioName,
    chairsPerTable: scenarioName === "tokyo" ? 2 : 3,
  }), [seats, baristas, style, scenarioName]);

  const scenarioKey = `${scenarioName}|${seats}|${baristas}|${style}`;
  const sim = useCafeSim({ layout, footfall, scenarioKey, running,
    externalTime: simTime, speed });

  // Recommendation overlay + apply animation. recInfo is derived from the
  // (target_id, from_position, to_position) triple emitted by the agent;
  // recTween is the eased 0→1 scalar that drives the visible shift when
  // the user clicks accept. The fingerprint is fed in as the tween "key"
  // so a fresh recommendation can't inherit the previous tween's state.
  const recKey = recommendation ? recommendation.fingerprint || "" : "";
  const recInfo = React.useMemo(
    () => recInfoFromLayout(layout, recommendation),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [layout, recKey,
     recommendation && recommendation.targetId,
     recommendation && recommendation.fromPosition && recommendation.fromPosition.join(","),
     recommendation && recommendation.toPosition && recommendation.toPosition.join(",")]
  );
  const recTween = useScalarTween(
    recommendation && recommendation.status === "accept" ? 1 : 0,
    700,
    recKey
  );
  const showOverlay = !!recInfo && recommendation && recommendation.status === "pending";

  const halfW = (layout.floorW + 2) * (ISO.tileW / 2);
  const minX = -halfW;
  const w = halfW * 2;
  const minY = -60;
  const h = (layout.floorW + layout.floorH + 2) * (ISO.tileH / 2) + 80;
  const vb = `${minX} ${minY} ${w} ${h}`;

  return (
    <svg width="100%" height="100%" viewBox={vb} preserveAspectRatio="xMidYMid meet"
      style={{ display: "block", background: "transparent" }}>
      <defs>
        <radialGradient id="iso-vignette" cx="50%" cy="55%" r="65%">
          <stop offset="0%" stopColor="rgba(0,0,0,0)" />
          <stop offset="100%" stopColor="rgba(70,55,30,0.15)" />
        </radialGradient>
        <marker id="rec-arrow-head" viewBox="0 0 8 8" refX="6" refY="4"
          markerWidth="6" markerHeight="6" orient="auto-start-reverse">
          <path d="M0,0 L8,4 L0,8 Z" fill="#f4a73e" />
        </marker>
      </defs>
      <CafeLayout layout={layout} sim={sim} recInfo={recInfo} recTween={recTween} />
      {showOverlay && <RecOverlay recInfo={recInfo} />}
      <rect x={minX} y={minY} width={w} height={h} fill="url(#iso-vignette)" pointerEvents="none" />
    </svg>
  );
}

Object.assign(window, { CafeScene, generateLayout, useScalarTween });
