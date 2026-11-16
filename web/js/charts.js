/* VitaLens · small hand-made SVG charts (no library needed). Every mark has a hover/tap tooltip via data-tip. */
window.VL = window.VL || {};

VL.fmt = {
  MON: ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
  months12: ["Sep 25", "Oct", "Nov", "Dec", "Jan 26", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug 26"],
  monthsLong: ["September 2025", "October 2025", "November 2025", "December 2025", "January 2026", "February 2026",
               "March 2026", "April 2026", "May 2026", "June 2026", "July 2026", "August 2026"],
  num(v, d = 1) {
    if (v == null || isNaN(v)) return "–";
    if (Math.abs(v) >= 1000) return Math.round(v).toLocaleString("en-US");
    return (+v).toFixed(d).replace(/\.0+$/, "");
  },
  date(s) { if (!s) return ""; const [y, m, d] = s.split("-").map(Number); return `${d} ${this.MON[m - 1]} ${y}`; },
  esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])); }
};

VL.charts = (() => {
  const esc = s => VL.fmt.esc(s);
  const cw = () => Math.round(Math.max(300, Math.min(1000, (api.width || 640))));
  const nice = (lo, hi) => { if (lo === hi) { lo -= 1; hi += 1; } const pad = (hi - lo) * 0.12; return [lo - pad, hi + pad]; };

  /* Monthly line with the user's own starting level shown as a dashed reference line. */
  function line({ values, labels = VL.fmt.months12, baseline = null, target = null, unit = "", dec = 1, title = "" }) {
    const W = cw(), H = W < 500 ? 200 : 240, ml = 44, mr = 14, mt = 14, mb = 28, pw = W - ml - mr, ph = H - mt - mb;
    const vals = values.map(v => (v == null ? null : +v));
    const finite = vals.filter(v => v != null).concat(baseline != null ? [baseline] : []).concat(target != null ? [target] : []);
    if (!finite.length) return `<p class="muted small">No readings in this period.</p>`;
    const [lo, hi] = nice(Math.min(...finite), Math.max(...finite));
    const x = i => ml + (vals.length === 1 ? pw / 2 : (i * pw) / (vals.length - 1));
    const y = v => mt + ph - ((v - lo) / (hi - lo)) * ph;
    let s = `<svg class="chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(title)} by month">`;
    for (let k = 0; k <= 3; k++) {
      const v = lo + ((hi - lo) * k) / 3, yy = y(v);
      s += `<line x1="${ml}" x2="${W - mr}" y1="${yy}" y2="${yy}" class="grid"/><text x="${ml - 6}" y="${yy + 4}" class="axis" text-anchor="end">${VL.fmt.num(v, Math.abs(hi - lo) < 5 ? 1 : 0)}</text>`;
    }
    const every = W < 500 ? 3 : labels.length > 12 ? 2 : W > 700 ? 1 : 2;
    labels.forEach((l, i) => { if (i % every === 0) s += `<text x="${x(i)}" y="${H - 8}" class="axis" text-anchor="middle">${esc(l)}</text>`; });
    if (target != null) s += `<line x1="${ml}" x2="${W - mr}" y1="${y(target)}" y2="${y(target)}" class="target"/><text x="${ml + 6}" y="${y(target) - 6}" class="axis">target ${VL.fmt.num(target, dec)}</text>`;
    if (baseline != null) s += `<line x1="${ml}" x2="${W - mr}" y1="${y(baseline)}" y2="${y(baseline)}" class="base"/><text x="${W - mr - 16}" y="${y(baseline) + (target != null && Math.abs(y(target) - y(baseline)) < 18 ? 16 : -6)}" class="axis" text-anchor="end">your start ${VL.fmt.num(baseline, dec)}</text>`;
    let d = "", pen = false;
    vals.forEach((v, i) => { if (v == null) { pen = false; return; } d += (pen ? "L" : "M") + x(i).toFixed(1) + "," + y(v).toFixed(1); pen = true; });
    s += `<path d="${d}" class="ln"/>`;
    vals.forEach((v, i) => {
      if (v == null) return;
      s += `<circle cx="${x(i)}" cy="${y(v)}" r="${i === vals.length - 1 ? 5 : 3.5}" class="pt${i === vals.length - 1 ? " last" : ""}"/>`;
      s += `<rect x="${x(i) - pw / vals.length / 2}" y="${mt}" width="${pw / vals.length}" height="${ph}" class="hit" data-tip="${esc(VL.fmt.monthsLong[i] || labels[i])}: ${VL.fmt.num(v, dec)} ${esc(unit)}"/>`;
    });
    return s + `</svg>`;
  }

  /* Lab results over time with the normal range shaded. */
  function lab(points, lo, hi, unit) {
    const W = cw(), H = W < 500 ? 190 : 220, ml = 44, mr = 14, mt = 12, mb = 26, pw = W - ml - mr, ph = H - mt - mb;
    const t0 = Date.UTC(2025, 8, 1), t1 = Date.UTC(2026, 8, 1);
    const ts = s => { const [a, b, c] = s.split("-").map(Number); return Date.UTC(a, b - 1, c); };
    const vs = points.map(p => p[1]).concat([lo, hi].filter(v => v != null));
    const [a, b] = nice(Math.min(...vs), Math.max(...vs));
    const x = t => ml + ((Math.min(Math.max(t, t0), t1) - t0) / (t1 - t0)) * pw;
    const y = v => mt + ph - ((v - a) / (b - a)) * ph;
    let s = `<svg class="chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="Results over time">`;
    const top = hi != null ? y(Math.min(hi, b)) : mt, bot = lo != null ? y(Math.max(lo, a)) : mt + ph;
    s += `<rect x="${ml}" y="${top}" width="${pw}" height="${Math.max(0, bot - top)}" class="band"/>`;
    s += `<text x="${W - mr - 4}" y="${top + 13}" class="axis" text-anchor="end">normal range</text>`;
    for (let k = 0; k <= 3; k++) { const v = a + ((b - a) * k) / 3; s += `<text x="${ml - 6}" y="${y(v) + 4}" class="axis" text-anchor="end">${VL.fmt.num(v, b - a < 5 ? 1 : 0)}</text>`; }
    ["Sep 25", "Dec", "Mar 26", "Jun", "Sep 26"].forEach((l, i) => s += `<text x="${ml + (i * pw) / 4}" y="${H - 7}" class="axis" text-anchor="middle">${l}</text>`);
    s += `<path d="${points.map((p, i) => (i ? "L" : "M") + x(ts(p[0])).toFixed(1) + "," + y(p[1]).toFixed(1)).join("")}" class="ln"/>`;
    points.forEach((p, i) => {
      const out = (lo != null && p[1] < lo) || (hi != null && p[1] > hi);
      s += `<circle cx="${x(ts(p[0]))}" cy="${y(p[1])}" r="5" class="pt ${out ? "out" : "in"}" data-tip="${VL.fmt.date(p[0])}: ${p[1]} ${esc(unit)}${out ? " (outside range)" : " (in range)"}"/>`;
    });
    return s + `</svg>`;
  }

  /* Where the latest value sits against the normal range. */
  function rangeBar(v, lo, hi) {
    if (v == null || (lo == null && hi == null)) return "";
    const L = lo != null ? lo : hi * 0.5, H = hi != null ? hi : lo * 1.6;
    const span = H - L, a = L - span * 0.5, b = H + span * 0.5;
    const pos = v2 => Math.min(100, Math.max(0, ((v2 - a) / (b - a)) * 100));
    const out = (lo != null && v < lo) || (hi != null && v > hi);
    return `<div class="rbar" aria-hidden="true"><span class="rin" style="left:${pos(L)}%;width:${pos(H) - pos(L)}%"></span><span class="rdot ${out ? "out" : "in"}" style="left:${pos(v)}%"></span></div>`;
  }

  /* Score ring 0-100. */
  function ring(score, label) {
    const r = 52, c = 2 * Math.PI * r, off = c * (1 - score / 100);
    const cls = score >= 75 ? "good" : score >= 55 ? "fair" : "low";
    return `<svg class="ring ${cls}" viewBox="0 0 128 128" role="img" aria-label="${esc(label)} ${score} of 100">
      <circle cx="64" cy="64" r="${r}" class="track"/><circle cx="64" cy="64" r="${r}" class="val" stroke-dasharray="${c.toFixed(1)}" stroke-dashoffset="${off.toFixed(1)}" transform="rotate(-90 64 64)"/>
      <text x="64" y="64" text-anchor="middle" class="rnum">${score}</text><text x="64" y="84" text-anchor="middle" class="rlab">of 100</text></svg>`;
  }

  /* Monthly % bars (medicine adherence). */
  function bars(values, labels = VL.fmt.months12, unit = "%") {
    const W = cw(), H = 150, ml = 30, mr = 8, mt = 10, mb = 24, pw = W - ml - mr, ph = H - mt - mb, bw = pw / values.length;
    let s = `<svg class="chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="Monthly values">`;
    [0, 50, 100].forEach(v => { const yy = mt + ph - (v / 100) * ph; s += `<line x1="${ml}" x2="${W - mr}" y1="${yy}" y2="${yy}" class="grid"/><text x="${ml - 5}" y="${yy + 4}" class="axis" text-anchor="end">${v}</text>`; });
    const y80 = mt + ph - 0.8 * ph; s += `<line x1="${ml}" x2="${W - mr}" y1="${y80}" y2="${y80}" class="target"/>`;
    values.forEach((v, i) => {
      const xx = ml + i * bw + 3;
      if (i % (W < 500 ? 3 : 2) === 0) s += `<text x="${xx + (bw - 6) / 2}" y="${H - 7}" class="axis" text-anchor="middle">${esc(labels[i])}</text>`;
      if (v == null) return;
      const hh = (v / 100) * ph;
      s += `<rect x="${xx}" y="${mt + ph - hh}" width="${bw - 6}" height="${hh}" rx="4" class="bar ${v < 80 ? "low" : ""}" data-tip="${esc(VL.fmt.monthsLong[i])}: ${Math.round(v)}${unit} of doses taken"/>`;
    });
    return s + `</svg>`;
  }

  /* Tiny trend line for cards. */
  function spark(values) {
    const v = values.filter(x => x != null);
    if (v.length < 2) return "";
    const lo = Math.min(...v), hi = Math.max(...v), W = 96, H = 30;
    const pts = values.map((x, i) => (x == null ? null : [(i * W) / (values.length - 1), H - 3 - ((x - lo) / ((hi - lo) || 1)) * (H - 6)])).filter(Boolean);
    return `<svg class="spark" viewBox="0 0 ${W} ${H}" aria-hidden="true"><path d="${pts.map((p, i) => (i ? "L" : "M") + p[0].toFixed(1) + "," + p[1].toFixed(1)).join("")}"/></svg>`;
  }

  /* One shared tooltip for every [data-tip] element. */
  function installTooltip() {
    const tip = document.createElement("div");
    tip.className = "tooltip"; tip.hidden = true; document.body.appendChild(tip);
    const show = (e) => {
      const t = e.target.closest && e.target.closest("[data-tip]");
      if (!t) { tip.hidden = true; return; }
      tip.textContent = t.getAttribute("data-tip"); tip.hidden = false;
      const x = Math.min(window.innerWidth - tip.offsetWidth - 8, e.clientX + 12);
      tip.style.left = Math.max(8, x) + "px"; tip.style.top = (e.clientY - tip.offsetHeight - 10) + "px";
    };
    document.addEventListener("pointermove", show);
    document.addEventListener("pointerdown", show);
    document.addEventListener("scroll", () => (tip.hidden = true), true);
  }

  const api = { line, lab, rangeBar, ring, bars, spark, installTooltip, width: 640 };
  return api;
})();
