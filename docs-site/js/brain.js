// brain.js — the interactive "Memory Brain", rendered as clean neural ink.
// Crisp vector SVG (no hand-drawn/rough styling): a smooth brain outline, soft
// elliptical region shapes placed anatomically, labels lifted into the margins
// with thin leader lines (so nothing overlaps), and a neuron network whose
// synapses pulse with an electric accent on interaction, plus a slow ambient
// idle shimmer. Honors prefers-reduced-motion (then static).
//
// Pure native SVG — no external library — so it always renders.

const SVG_NS = "http://www.w3.org/2000/svg";
const W = 760;
const H = 560;

// Neural-ink palette: ink linework + a single electric accent. Status is shown
// by ink weight / opacity rather than hue, keeping it calm and Apple-clean.
const PALETTE = {
  ink: "#1d1d1f",
  line: "#86868b",
  accent: "#0a84ff",        // electric neural blue
  accentSoft: "#5ac8fa",
  covered: "#0a84ff",       // fully energized
  partial: "#7f9fbf",       // dimmer
  planned: "#c4c7cc",       // ghost
};

const STATUS_ALPHA = { covered: 1, partial: 0.7, planned: 0.4 };

const reduceMotion =
  window.matchMedia &&
  window.matchMedia("(prefers-reduced-motion: reduce)").matches;

// --- Region geometry (lateral view, frontal lobe facing left) -----------
// Each region is a soft ellipse (cx, cy, rx, ry) placed anatomically inside
// the cerebrum hull, plus the memory systems it hosts and a margin label
// (labelAt / labelAnchor) connected back to the region by a thin leader line.
const REGIONS = [
  {
    id: "prefrontal",
    label: "prefrontal cortex",
    systems: ["working", "prospective"],
    cx: 224, cy: 200, rx: 48, ry: 44,
    labelAt: [38, 150], labelAnchor: "start",
  },
  {
    id: "neocortex",
    label: "neocortex",
    systems: ["semantic", "priming"],
    cx: 392, cy: 170, rx: 94, ry: 46,
    labelAt: [392, 78], labelAnchor: "middle",
  },
  {
    id: "sensory",
    label: "sensory cortices",
    systems: ["sensory"],
    cx: 534, cy: 200, rx: 48, ry: 42,
    labelAt: [726, 150], labelAnchor: "end",
  },
  {
    id: "basal",
    label: "basal ganglia",
    systems: ["procedural"],
    cx: 374, cy: 240, rx: 40, ry: 26,
    labelAt: [726, 234], labelAnchor: "end",
  },
  {
    id: "hippocampus",
    label: "hippocampus",
    systems: ["episodic", "temporal"],
    cx: 372, cy: 292, rx: 54, ry: 26,
    labelAt: [300, 396], labelAnchor: "middle",
  },
  {
    id: "amygdala",
    label: "amygdala",
    systems: ["affective", "conditioning"],
    cx: 288, cy: 292, rx: 30, ry: 24,
    labelAt: [38, 322], labelAnchor: "start",
  },
  {
    id: "cerebellum",
    label: "cerebellum",
    systems: ["procedural"],
    cx: 554, cy: 318, rx: 58, ry: 40,
    labelAt: [726, 332], labelAnchor: "end",
  },
];

// Annotated nodes (not anatomical regions): consolidation & forgetting.
const ANNOT_NODES = [
  { id: "consolidation", at: [150, 432], leadTo: [372, 318], label: "consolidation" },
  { id: "forgetting", at: [566, 432], leadTo: [470, 296], label: "forgetting" },
];

// Brain outer hull (the iconic side-profile cortex) for the inked outline.
const HULL = [
  [160, 250], [152, 190], [180, 150], [235, 122], [320, 107],
  [420, 105], [510, 120], [565, 150], [592, 195], [590, 248],
  [560, 292], [495, 315], [420, 325], [345, 326], [285, 318],
  [238, 300], [198, 278],
];

// --- helpers ------------------------------------------------------------
function el(tag, attrs = {}) {
  const n = document.createElementNS(SVG_NS, tag);
  for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, String(v));
  return n;
}

function aggregateStatus(systemIds, systemsById) {
  let best = "planned";
  for (const id of systemIds) {
    const s = systemsById.get(id)?.status;
    if (s === "covered") return "covered";
    if (s === "partial") best = "partial";
  }
  return best;
}

// Catmull-Rom → cubic Bézier: turns a point loop into a smooth closed path.
function smoothClosedPath(pts) {
  const n = pts.length;
  if (n < 3) return "";
  let d = `M ${pts[0][0].toFixed(1)} ${pts[0][1].toFixed(1)} `;
  for (let i = 0; i < n; i++) {
    const p0 = pts[(i - 1 + n) % n];
    const p1 = pts[i];
    const p2 = pts[(i + 1) % n];
    const p3 = pts[(i + 2) % n];
    const c1x = p1[0] + (p2[0] - p0[0]) / 6;
    const c1y = p1[1] + (p2[1] - p0[1]) / 6;
    const c2x = p2[0] - (p3[0] - p1[0]) / 6;
    const c2y = p2[1] - (p3[1] - p1[1]) / 6;
    d += `C ${c1x.toFixed(1)} ${c1y.toFixed(1)} ${c2x.toFixed(1)} ${c2y.toFixed(1)} ${p2[0].toFixed(1)} ${p2[1].toFixed(1)} `;
  }
  return d + "Z";
}

// A crisp neuron: soma dot + a few clean dendrite lines.
function makeNeuron(cx, cy, color, scale = 1) {
  const g = el("g", { class: "neuron" });
  const r = 4 * scale;
  const dend = 5;
  for (let i = 0; i < dend; i++) {
    const a = (i / dend) * Math.PI * 2 + 0.4;
    const len = (12 + (i % 2) * 6) * scale;
    g.appendChild(el("line", {
      x1: cx.toFixed(1), y1: cy.toFixed(1),
      x2: (cx + Math.cos(a) * len).toFixed(1), y2: (cy + Math.sin(a) * len).toFixed(1),
      stroke: color, "stroke-width": 0.9 * scale, "stroke-linecap": "round", opacity: 0.55,
    }));
  }
  g.appendChild(el("circle", { cx, cy, r, fill: color }));
  g.appendChild(el("circle", { cx, cy, r: r + 1.4, fill: "none", stroke: color, "stroke-width": 0.8, opacity: 0.4 }));
  return g;
}

// --- main render --------------------------------------------------------
export function renderBrain(host, data, onSelect) {
  const systemsById = new Map(data.systems.map((s) => [s.id, s]));
  host.innerHTML = "";

  const svg = el("svg", {
    viewBox: `0 0 ${W} ${H}`,
    role: "group",
    "aria-label": "Interactive brain diagram. Tab through regions to inspect memory systems.",
  });
  host.appendChild(svg);

  // soft glow filter for energized neurons / pulses
  const defs = el("defs");
  defs.innerHTML =
    `<filter id="nGlow" x="-80%" y="-80%" width="260%" height="260%">` +
    `<feGaussianBlur stdDeviation="3" result="b"/>` +
    `<feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>`;
  svg.appendChild(defs);

  // layers
  const lHull = el("g", { class: "hull-layer" });
  const lNet = el("g", { class: "net-layer" });
  const lRegions = el("g", { class: "regions-layer" });
  const lAnnot = el("g", { class: "annot-layer" });
  svg.append(lHull, lNet, lRegions, lAnnot);

  // ---- brain hull (clean ink outline + faint fill) ----
  lHull.appendChild(el("path", {
    d: smoothClosedPath(HULL),
    fill: "rgba(10,132,255,0.04)",
    stroke: PALETTE.ink, "stroke-width": 2, "stroke-linejoin": "round",
  }));
  // a couple of smooth gyri folds
  lHull.appendChild(el("path", {
    d: "M 200 196 C 280 166 360 192 440 170 C 498 152 545 186 575 176",
    fill: "none", stroke: PALETTE.line, "stroke-width": 1, opacity: 0.55,
  }));
  lHull.appendChild(el("path", {
    d: "M 196 256 C 280 240 360 256 440 240 C 496 229 545 252 560 256",
    fill: "none", stroke: PALETTE.line, "stroke-width": 1, opacity: 0.55,
  }));
  // brain stem (between cerebrum and cerebellum, curving down)
  lHull.appendChild(el("path", {
    d: "M 458 318 C 456 350 466 382 480 404",
    fill: "none", stroke: PALETTE.ink, "stroke-width": 1.8, "stroke-linecap": "round",
  }));

  // ---- neuron network ----
  const neuronPts = [];
  REGIONS.forEach((reg) => {
    const status = aggregateStatus(reg.systems, systemsById);
    neuronPts.push({ x: reg.cx, y: reg.cy, status, color: PALETTE[status], regionId: reg.id });
  });
  const filler = [[300, 150], [455, 148], [330, 208], [462, 212], [262, 250], [474, 286]];
  filler.forEach(([x, y]) => {
    neuronPts.push({ x, y, status: "covered", color: PALETTE.covered, regionId: null, scale: 0.6 });
  });

  // synaptic connections (smooth curves)
  const connections = [];
  for (let i = 0; i < neuronPts.length; i++) {
    for (let j = i + 1; j < neuronPts.length; j++) {
      const a = neuronPts[i], b = neuronPts[j];
      const d = Math.hypot(a.x - b.x, a.y - b.y);
      if (d < 150 && (i * 7 + j * 13) % 9 < 5) {
        const status =
          a.status === "planned" || b.status === "planned" ? "planned"
          : a.status === "partial" || b.status === "partial" ? "partial"
          : "covered";
        const mx = (a.x + b.x) / 2 + ((i + j) % 5 - 2) * 6;
        const my = (a.y + b.y) / 2 + ((i * 3 + j) % 5 - 2) * 6;
        const path = el("path", {
          d: `M ${a.x.toFixed(1)} ${a.y.toFixed(1)} Q ${mx.toFixed(1)} ${my.toFixed(1)} ${b.x.toFixed(1)} ${b.y.toFixed(1)}`,
          fill: "none",
          stroke: PALETTE.line,
          "stroke-width": status === "covered" ? 1.1 : 0.9,
          "stroke-linecap": "round",
          opacity: status === "planned" ? 0.25 : status === "partial" ? 0.4 : 0.5,
          class: "synapse",
        });
        lNet.appendChild(path);
        connections.push({ path, a: i, b: j, status });
      }
    }
  }

  // neurons
  const neuronEls = neuronPts.map((p) => {
    const g = makeNeuron(p.x, p.y, p.color, p.scale || 1);
    g.dataset.region = p.regionId || "";
    g.dataset.status = p.status;
    g.style.opacity = String(STATUS_ALPHA[p.status]);
    lNet.appendChild(g);
    return g;
  });

  // ---- interactive regions ----
  const regionEls = new Map();
  REGIONS.forEach((reg) => {
    const status = aggregateStatus(reg.systems, systemsById);
    const color = PALETTE[status];
    const g = el("g", {
      class: "region",
      tabindex: "0",
      role: "button",
      "aria-label": `${reg.label}, ${status}. Activate to read details.`,
    });
    g.dataset.region = reg.id;

    // Leader line from the margin label to the region centre — drawn first so
    // the ellipse covers its inner end (reads as touching the region edge).
    g.appendChild(el("line", {
      class: "region__leader",
      x1: reg.labelAt[0], y1: reg.labelAt[1] - 4, x2: reg.cx, y2: reg.cy,
      stroke: PALETTE.line, "stroke-width": 0.9, opacity: 0.45,
    }));

    const shape = el("ellipse", {
      cx: reg.cx, cy: reg.cy, rx: reg.rx, ry: reg.ry,
      fill: status === "planned" ? "none" : color,
      "fill-opacity": status === "covered" ? 0.14 : 0.08,
      stroke: color,
      "stroke-width": status === "planned" ? 1.1 : 1.6,
      "stroke-opacity": STATUS_ALPHA[status],
    });
    if (status === "planned") shape.setAttribute("stroke-dasharray", "4 5");
    g.appendChild(shape);

    // transparent hit area (a touch larger than the shape)
    g.appendChild(el("ellipse", {
      class: "region__hit", cx: reg.cx, cy: reg.cy, rx: reg.rx + 4, ry: reg.ry + 4, fill: "transparent",
    }));

    // margin label
    const label = el("text", {
      class: "region__label", x: reg.labelAt[0], y: reg.labelAt[1], "text-anchor": reg.labelAnchor || "middle",
    });
    label.textContent = reg.label;
    g.appendChild(label);

    regionEls.set(reg.id, { g, status, systems: reg.systems, shape });
    lRegions.appendChild(g);

    const select = () => { onSelect(reg.systems[0], reg.id); fireRegion(reg.id); };
    g.addEventListener("mouseenter", () => { highlight(reg.id); onSelect(reg.systems[0], reg.id, true); });
    g.addEventListener("mouseleave", () => highlight(null));
    g.addEventListener("focus", () => { highlight(reg.id); onSelect(reg.systems[0], reg.id, true); });
    g.addEventListener("click", select);
    g.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); select(); }
    });
  });

  // ---- annotation nodes (consolidation / forgetting) ----
  ANNOT_NODES.forEach((n) => {
    const sys = systemsById.get(n.id);
    const status = sys?.status || "partial";
    lAnnot.appendChild(el("line", {
      x1: n.at[0], y1: n.at[1], x2: n.leadTo[0], y2: n.leadTo[1],
      stroke: PALETTE.line, "stroke-width": 0.9, "stroke-dasharray": "2 4", opacity: 0.7,
    }));
    lAnnot.appendChild(el("circle", { cx: n.leadTo[0], cy: n.leadTo[1], r: 2.5, fill: PALETTE.accent, opacity: STATUS_ALPHA[status] }));
    const t = el("text", {
      class: "region__label", x: n.at[0], y: n.at[1], "text-anchor": "middle", fill: PALETTE.line,
    });
    t.textContent = n.label;
    t.style.cursor = "pointer";
    t.setAttribute("tabindex", "0");
    t.setAttribute("role", "button");
    t.setAttribute("aria-label", `${n.label}, ${status}. Activate to read details.`);
    const pick = () => onSelect(n.id, null);
    t.addEventListener("click", pick);
    t.addEventListener("mouseenter", () => onSelect(n.id, null, true));
    t.addEventListener("focus", () => onSelect(n.id, null, true));
    t.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); pick(); }
    });
    lAnnot.appendChild(t);
  });

  // ---- highlight / dim ----
  function highlight(activeId) {
    regionEls.forEach(({ g }, id) => {
      g.classList.toggle("is-active", id === activeId);
      g.classList.toggle("is-dim", activeId !== null && id !== activeId);
    });
  }

  // ---- firing animation ----
  function fireRegion(regionId) {
    if (reduceMotion) return;
    neuronEls.forEach((g) => { if (g.dataset.region === regionId) pulseNeuron(g); });
    connections.forEach((c) => {
      const an = neuronPts[c.a], bn = neuronPts[c.b];
      if (an.regionId === regionId || bn.regionId === regionId) pulseSynapse(c.path);
    });
  }

  function pulseNeuron(g) {
    g.setAttribute("filter", "url(#nGlow)");
    g.animate(
      [{ opacity: 1 }, { opacity: 0.6 }, { opacity: 1 }],
      { duration: 700, easing: "ease-in-out" }
    ).onfinish = () => g.removeAttribute("filter");
  }

  function pulseSynapse(path) {
    const len = path.getTotalLength ? path.getTotalLength() : 100;
    path.style.strokeDasharray = `${len}`;
    const anim = path.animate(
      [
        { strokeDashoffset: len, stroke: PALETTE.accent, strokeWidth: 2.4, opacity: 1 },
        { strokeDashoffset: 0, stroke: PALETTE.accent, strokeWidth: 2.4, opacity: 1 },
      ],
      { duration: 600, easing: "cubic-bezier(0.4,0,0.2,1)" }
    );
    anim.onfinish = () => {
      path.style.strokeDasharray = "";
      path.style.strokeDashoffset = "";
      path.style.stroke = "";
      path.style.strokeWidth = "";
      path.style.opacity = "";
    };
  }

  // ---- idle ambient shimmer ----
  let idleTimer = null;
  if (!reduceMotion) {
    const tick = () => {
      const live = neuronEls.filter((g) => g.dataset.status !== "planned");
      if (live.length) {
        const g = live[Math.floor(Math.random() * live.length)];
        pulseNeuron(g);
        const reg = g.dataset.region;
        if (reg) {
          connections
            .filter((c) => neuronPts[c.a].regionId === reg || neuronPts[c.b].regionId === reg)
            .slice(0, 2)
            .forEach((c) => pulseSynapse(c.path));
        }
      }
      idleTimer = setTimeout(tick, 1400 + Math.random() * 1600);
    };
    idleTimer = setTimeout(tick, 1200);
  }

  // public API for app.js
  return {
    focusSystem(systemId) {
      let target = null;
      for (const [rid, info] of regionEls) {
        if (info.systems.includes(systemId)) { target = rid; break; }
      }
      highlight(target);
      if (target) fireRegion(target);
    },
    clearHighlight() { highlight(null); },
    destroy() { if (idleTimer) clearTimeout(idleTimer); },
  };
}
