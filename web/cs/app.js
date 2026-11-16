/* VitaLens · user app: sign-in, onboarding and every screen. Hash routes: #/home, #/trends, #/labs, ... */
(function () {
  const $ = id => document.getElementById(id);
  const esc = s => VL.fmt.esc(s);
  const n = (v, d) => VL.fmt.num(v, d);
  const I = VL.insights, K = VL.K, C = VL.charts, S = VL.store;
  const today = () => new Date().toISOString().slice(0, 10);

  const NAV = [
    ["home", "🏠", "Home"], ["trends", "📈", "My trends"], ["labs", "🧪", "Lab results"], ["meds", "💊", "Medicines"],
    ["checkin", "📝", "Daily check-in"], ["assistant", "🤖", "AI assistant"], ["report", "📄", "Doctor report"], ["settings", "⚙️", "Settings"]
  ];
  const VERDICT = { better: ["better", "▲ Better"], worse: ["worse", "▼ Needs care"], same: ["same", "● Steady"], neutral: ["neutral", "● Changed"] };
  const verdictPill = (v, s) => { const [c, t] = VERDICT[v] || VERDICT.same; return `<span class="pill ${c}">${s && s.direction !== "stable" && v !== "same" ? (s.direction === "up" ? "↑ " : "↓ ") + t.slice(2) : t}</span>`; };

  /* ---------- mini markdown for AI text: **bold**, _italic_, bullets, numbered lists ---------- */
  function md(text) {
    const inline = s => esc(s).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>").replace(/(^|\s)_(.+?)_(?=\s|$|[.,!?])/g, "$1<em>$2</em>");
    return `<div class="md">` + String(text).split(/\n{2,}/).map(block => block.split("\n").map(l => {
      if (/^\s{2,}[–-]\s/.test(l)) return `<div class="li sub">${inline(l.replace(/^\s*[–-]\s/, ""))}</div>`;
      if (/^\s*[•*-]\s/.test(l)) return `<div class="li">${inline(l.replace(/^\s*[•*-]\s/, ""))}</div>`;
      const m = l.match(/^\s*(\d+)\.\s(.*)/); if (m) return `<div class="li num" data-n="${m[1]}.">${inline(m[2])}</div>`;
      return l.trim() ? `<p>${inline(l)}</p>` : "";
    }).join("")).join("") + `</div>`;
  }

  function toast(msg) {
    const t = document.createElement("div"); t.className = "toast"; t.setAttribute("role", "status"); t.textContent = msg;
    document.body.appendChild(t); setTimeout(() => t.remove(), 2600);
  }

  /* ---------- theme ---------- */
  function applyTheme() {
    const t = S.get("theme", "auto");
    const dark = t === "dark" || (t === "auto" && window.matchMedia && matchMedia("(prefers-color-scheme: dark)").matches);
    document.documentElement.setAttribute("data-theme", dark ? "dark" : "light");
  }

  /* =================================================================== sign in */
  function renderLogin(err) {
    const feat = VL.data.index ? VL.data.index.summary.featured : [];
    const demos = feat.map(f => VL.data.findRow(f.id)).filter(Boolean);
    document.title = "VitaLens · Sign in";
    $("app").innerHTML = `<div class="login">
      <section class="hero">
        <div class="logo"><span class="mark">♥</span><span>Vita<b>Lens</b></span></div>
        <h1>Your health data,<br>explained in plain words.</h1>
        <p style="max-width:52ch;opacity:.92">VitaLens turns a year of your wearable, home and lab data into simple answers: what got better, what to watch, and what to ask your doctor.</p>
        <div class="feat">
          <div><i>📈</i><span><b>Your own trends</b><br><span style="opacity:.85">Every change is compared with your own starting point, not with other people.</span></span></div>
          <div><i>🤖</i><span><b>AI health assistant</b><br><span style="opacity:.85">Ask questions about your results. Safety checks stop it from diagnosing or making up numbers.</span></span></div>
          <div><i>📝</i><span><b>Daily check-ins and reminders</b><br><span style="opacity:.85">Log how you feel, tick off your medicines and get a quick reflection.</span></span></div>
          <div><i>📄</i><span><b>Ready for your next visit</b><br><span style="opacity:.85">A one-page report with your questions for the doctor.</span></span></div>
        </div>
      </section>
      <section class="form"><div class="card stack">
        <h2>Sign in</h2>
        <p class="muted small">Enter your VitaLens Health ID (for example PC0001).</p>
        <form id="lf" class="stack" autocomplete="off">
          <div><label class="lbl" for="hid">Health ID</label><input class="input mono" id="hid" placeholder="PC0001" required aria-describedby="lerr"></div>
          <p id="lerr" class="small" style="color:var(--bad)">${err ? esc(err) : ""}</p>
          <button class="btn primary" style="width:100%">Continue</button>
        </form>
        <div><p class="small" style="font-weight:700;margin-bottom:8px">Or try a demo account</p>
          <div class="demo">${demos.map(r => `<button type="button" data-demo="${r.id}"><b class="mono">${r.id}</b><br><span class="tiny muted">${r.sex === "F" ? "Woman" : "Man"}, ${r.age}</span></button>`).join("")}</div></div>
        <p class="tiny muted">This prototype uses synthetic (made-up) data from PranaChain. No real patients. Anything you enter stays in this browser.</p>
      </div></section></div>`;
    $("lf").onsubmit = e => { e.preventDefault(); signIn($("hid").value); };
    document.querySelectorAll("[data-demo]").forEach(b => (b.onclick = () => signIn(b.dataset.demo)));
    $("hid").focus();
  }

  async function signIn(id) {
    const row = VL.data.findRow(id);
    if (!row) return renderLogin(`We couldn't find "${id}". Health IDs look like PC0001 (PC0201–PC0300 are not in this dataset).`);
    $("app").innerHTML = `<div class="loading">Loading your health data…</div>`;
    const p = await VL.data.getPatient(row.id);
    VL.state.uid = row.id; VL.state.p = p;
    S.set("session", row.id);
    if (!S.u("profile")) renderOnboarding(); else { if (!location.hash || location.hash === "#/") location.hash = "#/home"; renderShell(); }
  }
  function signOut() { S.del("session"); VL.state.uid = null; VL.state.p = null; location.hash = ""; renderLogin(); }

  /* =================================================================== onboarding */
  function renderOnboarding() {
    const p = VL.state.p, picked = new Set();
    const sug = I.findings(p).watch.map(w => w.key);
    if (sug.includes("sbp")) picked.add("bp"); if (sug.includes("HbA1c") || sug.includes("Fasting glucose")) picked.add("sugar");
    if (p.trends.sleep && p.trends.sleep.recent < 7) picked.add("sleep"); if (p.trends.steps && p.trends.steps.recent < 8000) picked.add("move");
    if (p.adherence.some(a => a.mean < 80)) picked.add("meds");
    $("app").innerHTML = `<div class="login"><section class="hero"><div class="logo"><span class="mark">♥</span><span>Vita<b>Lens</b></span></div>
      <h1>Welcome! Let's set up your space.</h1><p style="opacity:.9;max-width:50ch">Two quick questions so VitaLens can talk to you by name and focus on what matters to you. You can change these later in Settings.</p></section>
      <section class="form"><form class="card stack" id="of">
        <div><label class="lbl" for="nm">What should we call you?</label><input class="input" id="nm" maxlength="30" placeholder="Your first name" required></div>
        <div><span class="lbl">What are your health goals?</span><p class="tiny muted" style="margin-bottom:8px">We pre-selected some based on your data.</p>
          <div class="chips" id="gl">${Object.entries(K.GOALS).map(([k, g]) => `<button type="button" class="chip" data-g="${k}" aria-pressed="${picked.has(k)}">${g.icon} ${g.label}</button>`).join("")}</div></div>
        <button class="btn primary">Start</button></form></section></div>`;
    document.querySelectorAll("[data-g]").forEach(b => (b.onclick = () => { const on = b.getAttribute("aria-pressed") !== "true"; b.setAttribute("aria-pressed", on); on ? picked.add(b.dataset.g) : picked.delete(b.dataset.g); }));
    $("of").onsubmit = e => { e.preventDefault(); S.uset("profile", { name: $("nm").value.trim(), goals: [...picked], created: today() }); location.hash = "#/home"; renderShell(); };
    $("nm").focus();
  }

  /* =================================================================== shell + router */
  const profile = () => S.u("profile", { name: "", goals: [] });
  const ctx = () => ({ name: profile().name, goals: profile().goals, checkins: S.u("checkins", []), history: S.u("chat", []) });

  function renderShell() {
    const pr = profile();
    $("app").innerHTML = `<div class="shell">
      <nav class="side" aria-label="Main"><div class="logo"><span class="mark">♥</span><span>Vita<b>Lens</b></span></div>
        <div class="nav" id="nav">${NAV.map(([k, ic, t]) => `<a href="#/${k}" data-k="${k}"><span class="ic" aria-hidden="true">${ic}</span><span>${t}</span></a>`).join("")}</div>
        <div class="me"><span class="avatar">${esc((pr.name || "?")[0].toUpperCase())}</span><span style="flex:1;min-width:0"><b>${esc(pr.name)}</b><br><span class="tiny muted mono">${VL.state.uid}</span></span>
          <button class="btn sm ghost" id="so" title="Sign out">↩</button></div></nav>
      <main id="main" tabindex="-1"></main></div>`;
    $("so").onclick = signOut;
    route();
  }

  function route() {
    if (!VL.state.p) return;
    const [k, arg] = (location.hash.replace(/^#\//, "") || "home").split("/");
    const page = PAGES[k] ? k : "home";
    document.querySelectorAll("#nav a").forEach(a => a.setAttribute("aria-current", a.dataset.k === page ? "page" : "false"));
    document.title = `VitaLens · ${NAV.find(x => x[0] === page)[2]}`;
    const main = $("main");
    const cs = getComputedStyle(main), inner = main.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight);
    C.width = Math.min(1000, (page === "meds" || page === "checkin") && window.innerWidth > 980 ? (inner - 16) / 2 - 42 : inner - 42);
    main.innerHTML = PAGES[page](arg) + `<footer class="foot">VitaLens prototype v1.0 · COMP 8967 Group 1 · Synthetic data from PranaChain · VitaLens explains your data. It does not diagnose. In an emergency call 911.</footer>`;
    (AFTER[page] || (() => {}))(arg);
    window.scrollTo(0, 0);
  }

  /* =================================================================== home */
  function hello() { const h = new Date().getHours(); return h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening"; }
  const TILE_KEYS = ["steps", "sleep", "sbp", "rhr", "stress", "weight"];

  function medsChecklist(compact) {
    const p = VL.state.p, meds = I.activeMeds(p);
    if (!meds.length) return `<p class="muted small">You have no current medicines in your record.</p>`;
    const taken = S.u("taken:" + today(), []);
    return `<div class="list">${meds.map(m => { const id = m.medication + "|" + m.start, done = taken.includes(id);
      return `<label class="check ${done ? "done" : ""}"><input type="checkbox" data-med="${esc(id)}" ${done ? "checked" : ""}><span style="flex:1"><b>${esc(m.medication)}</b><span class="small muted">${esc(m.dose)} · ${esc(m.frequency)}</span></span>${done ? `<span class="pill better">Taken</span>` : ""}</label>`; }).join("")}</div>
      ${compact ? "" : `<p class="tiny muted" style="margin-top:8px">Ticks are saved in this browser for today (${VL.fmt.date(today())}).</p>`}`;
  }
  function bindMeds() {
    document.querySelectorAll("[data-med]").forEach(cb => (cb.onchange = () => {
      const key = "taken:" + today(); let t = S.u(key, []);
      t = cb.checked ? [...new Set(t.concat(cb.dataset.med))] : t.filter(x => x !== cb.dataset.med);
      S.uset(key, t); cb.closest(".check").classList.toggle("done", cb.checked);
      const total = I.activeMeds(VL.state.p).length; if (cb.checked && t.length === total) toast("All medicines taken today. Great job! 🎉");
    }));
  }
  function medStreak() {
    const total = I.activeMeds(VL.state.p).length; if (!total) return 0;
    let s = 0; const d = new Date();
    for (let i = 0; i < 365; i++) { const k = d.toISOString().slice(0, 10); if (S.u("taken:" + k, []).length >= total) s++; else if (i > 0) break; d.setDate(d.getDate() - 1); }
    return s;
  }

  function goalCards() {
    const g = I.goals(VL.state.p, profile().goals);
    if (!g.length) return `<p class="muted small">No goals yet. <a href="#/settings">Pick goals in Settings</a>.</p>`;
    return `<div class="list">${g.map(x => `<div class="item"><span class="em">${x.icon}</span><span style="flex:1;min-width:0"><span class="row"><b>${esc(x.label)}</b><span class="small mono">${n(x.now, 1)} → ${n(x.target, 1)} ${esc(x.unit)}</span></span>
      <div class="meter" role="progressbar" aria-valuenow="${x.pct}" aria-valuemin="0" aria-valuemax="100" aria-label="${esc(x.label)} progress"><span style="width:${x.pct}%;${x.done ? "background:var(--good)" : ""}"></span></div>
      <span class="tiny muted">${x.done ? "✓ Target reached. " : ""}${esc(x.text)}</span></span></div>`).join("")}</div>`;
  }

  function home() {
    const p = VL.state.p, pr = profile(), sc = I.score(p), F = I.findings(p);
    const aiSum = S.u("aisummary");
    const cfg = VL.ai.settings();
    const tiles = TILE_KEYS.map(k => { const s = I.signal(p, k); if (!s) return "";
      const val = k === "sbp" ? `${n(p.trends.sbp.monthly[11], 0)}/${n(p.trends.dbp.monthly[11], 0)}` : n(s.latest, s.dec);
      return `<a class="tile" href="#/trends/${k}"><span class="small muted">${s.icon} ${esc(k === "sbp" ? "Blood pressure" : s.name)}</span>
        <div class="v">${val} <small>${esc(s.unit)}</small></div>${verdictPill(s.verdict, s)}${C.spark(s.monthly)}</a>`; }).join("");
    return `<div class="page-head"><div><p class="muted small">${hello()}${pr.name ? "," : ""}</p><h1>${esc(pr.name || "Welcome back")} 👋</h1>
        <p class="muted small" style="margin-top:4px">Your data covers September 2025 to August 2026. Latest month: August 2026.</p></div>
        <a class="btn primary" href="#/checkin">📝 Today's check-in</a></div>
      <div class="grid g-hero">
        <section class="card scorecard"><h2>Wellness score</h2>${C.ring(sc.total, "Wellness score")}<span class="pill ${sc.total >= 65 ? "better" : sc.total >= 50 ? "warn" : "worse"}">${sc.word}</span>
          <div class="parts">${sc.parts.map(x => `<div class="part"><div class="row"><span>${esc(x.label)}</span><span class="mono">${x.v}</span></div><div class="meter"><span style="width:${x.v}%"></span></div><span class="tiny muted">${esc(x.why)}</span></div>`).join("")}</div>
          <p class="tiny muted">A simple summary of your own data. Not a medical score.</p></section>
        <section class="card ai-card"><div class="row"><h2>🤖 Your AI summary</h2><span class="pill ai">${aiSum ? esc(aiSum.label) : "Built-in AI"}</span></div>
          <div id="aisum" style="margin-top:10px">${md(aiSum ? aiSum.text : I.summary(p, pr.name))}</div>
          <div class="row noprint" style="margin-top:14px;justify-content:flex-start">
            <a class="btn sm primary" href="#/assistant">Ask a question</a>
            ${cfg.provider !== "offline" && cfg.key ? `<button class="btn sm" id="rw">✨ Rewrite with ${esc(VL.ai.PROVIDERS[cfg.provider].label.split(" (")[0])}</button>` : `<a class="btn sm ghost" href="#/settings">Connect Claude / Gemini</a>`}
            ${aiSum ? `<button class="btn sm ghost" id="rs">Use built-in summary</button>` : ""}</div></section>
      </div>
      <h2 class="sec" style="margin:24px 0 12px">This month at a glance</h2><div class="tiles">${tiles}</div>
      <div class="grid g2 sec" style="margin-top:20px">
        <section class="card"><h2>✅ What's going well</h2><div class="list" style="margin-top:12px">${F.wins.slice(0, 5).map(w => `<a class="item" style="text-decoration:none;color:inherit" href="#/${w.tab}${w.key && w.tab === "trends" ? "/" + w.key : ""}"><span class="em">${w.icon}</span><span><b>${esc(w.title)}</b><span class="small muted">${esc(w.text)}</span></span></a>`).join("") || `<p class="muted small">Nothing clearly improved yet. Small steps count. Check your goals below.</p>`}</div></section>
        <section class="card"><h2>👀 Keep an eye on</h2><div class="list" style="margin-top:12px">${F.watch.slice(0, 5).map(w => `<a class="item" style="text-decoration:none;color:inherit" href="#/${w.tab}${w.key && w.tab === "trends" ? "/" + w.key : ""}"><span class="em">${w.icon}</span><span><b>${esc(w.title)}</b><span class="small muted">${esc(w.text)}</span></span></a>`).join("") || `<p class="muted small">Nothing needs attention right now. 🎉</p>`}</div></section>
      </div>
      <div class="grid g2 sec" style="margin-top:16px">
        <section class="card"><div class="row"><h2>💊 Today's medicines</h2>${medStreak() ? `<span class="pill better">🔥 ${medStreak()}-day streak</span>` : ""}</div><div style="margin-top:12px">${medsChecklist(true)}</div></section>
        <section class="card"><div class="row"><h2>🎯 My goals</h2><a class="small" href="#/settings">Edit</a></div><div style="margin-top:12px">${goalCards()}</div></section>
      </div>`;
  }
  const AFTER = {};
  AFTER.home = () => {
    bindMeds();
    if ($("rs")) $("rs").onclick = () => { S.del(`${VL.state.uid}:aisummary`); route(); };
    if ($("rw")) $("rw").onclick = async () => {
      $("rw").disabled = true; $("rw").textContent = "Writing…";
      const r = await VL.ai.rewriteSummary(VL.state.p, ctx());
      if (r) { const un = (r.checks && r.checks.unknownNumbers) || []; S.uset("aisummary", { text: r.text + (un.length ? `\n\n⚠ These numbers were not found in your data, please double-check: ${un.join(", ")}.` : "") + "\n\n_Written by AI from your data. Not a diagnosis._", label: VL.ai.PROVIDERS[r.source].label.split(" (")[0] }); route(); }
      else { toast("Couldn't reach the AI model. Check your key in Settings."); $("rw").disabled = false; $("rw").textContent = "Try again"; }
    };
  };

  /* =================================================================== trends */
  function trends(sel) {
    const p = VL.state.p;
    const keys = I.SIG_ORDER.concat(["rr"]).filter(k => I.signal(p, k));
    sel = keys.includes(sel) ? sel : keys[0];
    const s = I.signal(p, sel), info = K.SIGNALS[sel];
    const target = sel === "steps" ? 8000 : sel === "active" ? 30 : sel === "sbp" ? 130 : sel === "dbp" ? 80 : sel === "sleep" ? 7 : null;
    const sym = {}; p.symptoms.forEach(x => (sym[x[1]] = (sym[x[1]] || 0) + 1));
    let h = `<div class="page-head"><div><h1>My trends</h1><p class="muted small" style="margin-top:4px">Each month compared with your own start (average of Sep–Nov 2025).</p></div></div>
      <div class="chips" role="group" aria-label="Choose a measure">${keys.map(k => `<a class="chip" style="text-decoration:none" href="#/trends/${k}" aria-pressed="${k === sel}">${K.SIGNALS[k].icon} ${esc(K.SIGNALS[k].short)}</a>`).join("")}</div>
      <section class="card sec" style="margin-top:16px"><div class="row"><div><h2>${s.icon} ${esc(s.name)}</h2><p class="muted small">${esc(s.what)}</p></div>${verdictPill(s.verdict, s)}</div>
        <div style="margin-top:12px">${C.line({ values: s.monthly, baseline: s.base, target, unit: s.unit, dec: s.dec, title: s.name })}</div>
        <div class="legend"><span><i class="l"></i>Monthly average</span><span><i></i>Your start</span>${target != null ? `<span><i class="t"></i>Healthy target</span>` : ""}</div>
        <div class="grid g3" style="margin-top:16px">
          <div class="item"><span><span class="small muted">Your start</span><b class="mono" style="font-size:20px">${n(s.base, s.dec)} <span class="small muted">${esc(s.unit)}</span></b></span></div>
          <div class="item"><span><span class="small muted">Last 3 months</span><b class="mono" style="font-size:20px">${n(s.recent, s.dec)} <span class="small muted">${esc(s.unit)}</span></b></span></div>
          <div class="item"><span><span class="small muted">Change</span><b class="mono" style="font-size:20px">${s.change > 0 ? "+" : ""}${n(s.change, s.dec + 1)} <span class="small muted">${esc(s.unit)}</span></b></span></div></div>
        <p style="margin-top:14px">${esc(s.text)}</p><div class="notice info" style="margin-top:12px">💡 <span>${esc(s.tip)}</span></div></section>`;
    if (sel === "sbp" || sel === "dbp") h += `<section class="card sec" style="margin-top:16px"><h2>Days with blood pressure at or above 130/80</h2><p class="muted small">Share of days each month. Lower is better.</p>
      <div style="margin-top:10px">${C.line({ values: p.bp_target.monthly, baseline: p.bp_target.baseline, unit: "% of days", dec: 0, title: "Days above 130/80" })}</div></section>`;
    h += `<div class="grid g2 sec" style="margin-top:16px"><section class="card"><h2>🔗 Patterns in your data</h2><p class="muted small">We tested 8 possible links using your 365 days. Only clear ones are shown. A link is not proof of cause.</p>
      <div class="list" style="margin-top:12px">${p.relationships.map(r => `<div class="item"><span class="em">🔗</span><span><b>${esc(r.xl)} ↔ ${esc(r.yl)}</b><span class="small muted">${r.r < 0 ? "When the first goes up, the second tends to go down" : "These tend to rise together"} (strength ${Math.abs(r.r)}, from ${r.n} days).</span></span></div>`).join("") || `<p class="small muted">No clear links for you this year. That's common.</p>`}</div></section>
      <section class="card"><h2>🤒 Symptoms you reported</h2><div class="tbl" style="margin-top:10px">${Object.keys(sym).length ? `<table class="t"><thead><tr><th>Symptom</th><th>Times this year</th></tr></thead><tbody>${Object.entries(sym).sort((a, b) => b[1] - a[1]).map(([k, v]) => `<tr><td>${esc(k)}</td><td class="mono">${v}</td></tr>`).join("")}</tbody></table>` : `<p class="small muted">None reported.</p>`}</div></section></div>`;
    if (p.cycles) h += `<section class="card sec" style="margin-top:16px"><h2>🌸 Menstrual cycle</h2><p class="muted small">A typical cycle is 21–35 days. Average ${p.cycles.mean} days (±${p.cycles.sd}); ${p.cycles.long} of ${p.cycles.n} longer than 35 days.</p>
      <div style="margin-top:10px">${C.line({ values: p.cycles.cycles.map(c => c[1]), labels: p.cycles.cycles.map(c => c[0] ? VL.fmt.MON[+c[0].slice(5, 7) - 1] : ""), target: 35, unit: "days", dec: 0, title: "Cycle length" })}</div></section>`;
    return h;
  }

  /* =================================================================== labs */
  function labs() {
    const p = VL.state.p;
    const list = Object.keys(p.labs).map(k => I.lab(p, k)).filter(Boolean)
      .sort((a, b) => (a.inRange - b.inRange) || ((b.verdict === "worse") - (a.verdict === "worse")) || a.name.localeCompare(b.name));
    const out = list.filter(x => !x.inRange).length;
    return `<div class="page-head"><div><h1>Lab results</h1><p class="muted small" style="margin-top:4px">${list.length} tests · ${list.length - out} in range · ${out} outside range. Tap a test to see every result.</p></div>
      <a class="btn sm" href="#/assistant">🤖 Ask AI to explain</a></div>
      <div class="list">${list.map(L => `<details class="lab"><summary>
        <span><b>${esc(L.name)}</b><br><span class="small muted">${esc(L.what)}</span></span>
        <span class="rcol"><span class="mono" style="font-weight:700">${n(L.last, L.dec)} ${esc(L.unit)}</span>${C.rangeBar(L.last, L.lo, L.hi)}<span class="tiny muted">Normal: ${esc(L.ref)}</span></span>
        <span style="display:flex;flex-direction:column;gap:6px;align-items:flex-end"><span class="pill ${L.inRange ? "in" : "out"}">${L.inRange ? "✓ In range" : "! Outside range"}</span>${L.points.length > 1 ? verdictPill(L.verdict) : ""}</span></summary>
        <div class="body"><p>${esc(L.text)}</p><div style="margin-top:10px">${C.lab(L.points, L.lo, L.hi, L.unit)}</div>
          <div class="legend"><span><i class="b"></i>Normal range</span><span>● green = in range, red = outside</span></div>
          <div class="row" style="margin-top:10px;justify-content:flex-start"><button class="btn sm" data-ask="Explain my ${esc(L.name)}">🤖 Explain this</button></div></div></details>`).join("")}</div>`;
  }
  AFTER.labs = () => document.querySelectorAll("[data-ask]").forEach(b => (b.onclick = () => { S.set("pendingAsk", b.dataset.ask); location.hash = "#/assistant"; }));

  /* =================================================================== medicines */
  function meds() {
    const p = VL.state.p;
    const cards = p.meds.map(m => { const st = I.medStory(p, m);
      return `<section class="card"><div class="row"><div><h2>💊 ${esc(m.medication)}</h2><p class="muted small">${esc(m.dose)} · ${esc(m.frequency)} · since ${VL.fmt.date(m.start)}${m.end ? " · ended " + VL.fmt.date(m.end) : ""}</p></div>
        <span class="pill ${!m.end ? "better" : "same"}">${!m.end ? "Current" : esc(m.status)}</span></div>
        <p style="margin-top:10px">${esc(K.MEDS[m.medication] || m.indication || "")}</p>
        ${m.tolerance ? `<p class="small muted" style="margin-top:4px">How you tolerated it: ${esc(m.tolerance)}</p>` : ""}
        ${st.lines.length ? `<h3 style="margin-top:14px">What changed after you started</h3><div class="md">${st.lines.map(l => `<div class="li">${esc(l)}</div>`).join("")}</div>` : ""}
        ${st.adherence ? `<h3 style="margin-top:14px">Doses taken each month <span class="pill ${st.adherence.mean >= 80 ? "better" : "warn"}">${st.adherence.mean}% overall</span></h3><div style="margin-top:6px">${C.bars(st.adherence.monthly)}</div><p class="tiny muted">Dotted line = 80%. Months below it are shown in amber.</p>` : ""}
        <button class="btn sm" style="margin-top:12px" data-ask="Is my ${esc(m.medication)} working?">🤖 Ask about this medicine</button></section>`; }).join("");
    return `<div class="page-head"><div><h1>Medicines</h1><p class="muted small" style="margin-top:4px">Never stop or change a medicine without talking to your doctor.</p></div></div>
      <section class="card"><div class="row"><h2>Today's checklist</h2>${medStreak() ? `<span class="pill better">🔥 ${medStreak()}-day streak</span>` : ""}</div><div style="margin-top:12px">${medsChecklist()}</div></section>
      <div class="grid g2 sec" style="margin-top:16px">${cards || `<p class="muted">No medicines in your record.</p>`}</div>`;
  }
  AFTER.meds = () => { bindMeds(); AFTER.labs(); };

  /* =================================================================== check-in */
  const MOODS = ["😞", "🙁", "😐", "🙂", "😄"];
  function checkin() {
    const list = S.u("checkins", []), c = list.find(x => x.date === today()) || {};
    return `<div class="page-head"><div><h1>Daily check-in</h1><p class="muted small" style="margin-top:4px">Takes 30 seconds. The AI compares it with your usual numbers.</p></div></div>
      <div class="grid g2"><form class="card stack" id="cf">
        <div><span class="lbl">How do you feel today?</span><div class="moods" id="mood">${MOODS.map((m, i) => `<button type="button" data-m="${i + 1}" aria-pressed="${c.mood === i + 1}" aria-label="Mood ${i + 1} of 5">${m}</button>`).join("")}</div></div>
        <div class="fields">
          <div><label class="lbl" for="c-sleep">Sleep last night (h)</label><input class="input" id="c-sleep" type="number" step="0.5" min="0" max="16" value="${c.sleep ?? ""}"></div>
          <div><label class="lbl" for="c-stress">Stress (1–10)</label><input class="input" id="c-stress" type="number" min="1" max="10" value="${c.stress ?? ""}"></div>
          <div><label class="lbl" for="c-steps">Steps today</label><input class="input" id="c-steps" type="number" min="0" max="100000" value="${c.steps ?? ""}"></div>
          <div><label class="lbl" for="c-sbp">BP top (optional)</label><input class="input" id="c-sbp" type="number" min="60" max="260" value="${c.sbp ?? ""}"></div>
          <div><label class="lbl" for="c-dbp">BP bottom (optional)</label><input class="input" id="c-dbp" type="number" min="30" max="160" value="${c.dbp ?? ""}"></div></div>
        <div><span class="lbl">Any symptoms?</span><div class="chips" id="sym">${K.SYMPTOMS.map(s => `<button type="button" class="chip" data-s="${esc(s)}" aria-pressed="${(c.symptoms || []).includes(s)}">${esc(s)}</button>`).join("")}</div></div>
        <div><label class="lbl" for="c-note">Notes (optional)</label><textarea class="input" id="c-note" maxlength="400" placeholder="Anything else you want to remember">${esc(c.note || "")}</textarea></div>
        <button class="btn primary">Save check-in</button></form>
        <div class="stack"><section class="card ai-card" id="refl"><h2>🤖 AI reflection</h2><div style="margin-top:8px">${c.date ? md(I.reflect(VL.state.p, c)) : `<p class="muted">Save today's check-in to get a short reflection.</p>`}</div></section>
          <section class="card"><h2>Your check-ins</h2>${list.length ? `<p class="small muted">${list.length} check-in${list.length > 1 ? "s" : ""} saved in this browser.</p>
            ${list.length >= 2 ? `<div style="margin-top:8px">${C.line({ values: list.slice(-14).map(x => x.mood), labels: list.slice(-14).map(x => x.date.slice(5)), unit: "of 5 mood", dec: 0, title: "Mood" })}</div>` : ""}
            <div class="tbl"><table class="t"><thead><tr><th>Date</th><th>Mood</th><th>Sleep</th><th>Stress</th><th>Symptoms</th></tr></thead><tbody>${list.slice().reverse().slice(0, 10).map(x => `<tr><td>${VL.fmt.date(x.date)}</td><td>${MOODS[(x.mood || 3) - 1]}</td><td>${x.sleep ?? "–"}</td><td>${x.stress ?? "–"}</td><td>${esc((x.symptoms || []).join(", ") || "–")}</td></tr>`).join("")}</tbody></table></div>` : `<p class="small muted">No check-ins yet.</p>`}</section></div></div>`;
  }
  AFTER.checkin = () => {
    let mood = null;
    document.querySelectorAll("[data-m]").forEach(b => { if (b.getAttribute("aria-pressed") === "true") mood = +b.dataset.m;
      b.onclick = () => { mood = +b.dataset.m; document.querySelectorAll("[data-m]").forEach(x => x.setAttribute("aria-pressed", x === b)); }; });
    document.querySelectorAll("[data-s]").forEach(b => (b.onclick = () => b.setAttribute("aria-pressed", b.getAttribute("aria-pressed") !== "true")));
    $("cf").onsubmit = e => {
      e.preventDefault();
      const num = id => { const v = $(id).value; return v === "" ? null : +v; };
      const c = { date: today(), mood: mood || 3, sleep: num("c-sleep"), stress: num("c-stress"), steps: num("c-steps"), sbp: num("c-sbp"), dbp: num("c-dbp"),
        symptoms: [...document.querySelectorAll("[data-s][aria-pressed='true']")].map(b => b.dataset.s), note: $("c-note").value.trim() };
      const list = S.u("checkins", []).filter(x => x.date !== c.date).concat([c]).sort((a, b) => a.date.localeCompare(b.date));
      S.uset("checkins", list); toast("Check-in saved ✓"); route();
    };
  };

  /* =================================================================== AI assistant */
  const SUGGEST = ["How am I doing?", "Explain my blood pressure", "What is my HbA1c?", "Is my medicine working?", "How can I sleep better?", "What should I ask my doctor?", "What patterns are in my data?", "What's my wellness score?"];
  function assistant() {
    const cfg = VL.ai.settings();
    const live = cfg.provider !== "offline" && cfg.key;
    return `<div class="page-head" style="margin-bottom:12px"><div><h1>AI health assistant</h1><p class="muted small" style="margin-top:4px">Answers come only from your own data, with safety checks. It explains; it does not diagnose.</p></div>
      <div class="row"><span class="pill ai">${esc(live ? VL.ai.PROVIDERS[cfg.provider].label : "Built-in AI (offline)")}</span><button class="btn sm ghost" id="clr">Clear chat</button></div></div>
      <section class="card chat"><div class="msgs" id="msgs" aria-live="polite"></div>
        <div class="chips noprint" id="sugg" style="padding:6px 0 10px">${SUGGEST.map(s => `<button type="button" class="chip" data-q="${esc(s)}">${esc(s)}</button>`).join("")}</div>
        <form class="composer" id="cmp"><label class="sr" for="q">Your question</label><input class="input" id="q" placeholder="Ask about your sleep, labs, medicines…" autocomplete="off" maxlength="500"><button class="btn primary">Send</button></form></section>`;
  }
  function msgHtml(m) {
    if (m.role === "user") return `<div class="msg user">${esc(m.text)}</div>`;
    const c = m.checks || {}, badges = [];
    if (m.source === "safety") badges.push(`<span class="pill worse">🛡️ Safety message</span>`);
    else if (m.source === "offline") badges.push(`<span class="pill ai">Built-in AI</span>`, `<span class="pill better">✓ Numbers from your data</span>`);
    else {
      badges.push(`<span class="pill ai">${esc(VL.ai.PROVIDERS[m.source].label.split(" (")[0])} · ${esc(m.model || "")}</span>`);
      badges.push(c.unknownNumbers && c.unknownNumbers.length ? `<span class="pill warn" title="These numbers were not found in your data">⚠ Check: ${esc(c.unknownNumbers.slice(0, 4).join(", "))}</span>` : `<span class="pill better">✓ ${c.numbersChecked || 0} numbers match your data</span>`);
      if (c.diagnosisRemoved) badges.push(`<span class="pill warn">🛡️ Diagnosis wording removed</span>`);
    }
    return `<div class="msg bot">${md(m.text)}<div class="meta">${badges.join("")}</div></div>`;
  }
  AFTER.assistant = () => {
    const box = $("msgs"), pr = profile();
    const draw = () => {
      const hist = S.u("chat", []);
      box.innerHTML = (hist.length ? "" : msgHtml({ role: "bot", source: "offline", text: `Hi${pr.name ? " " + pr.name : ""}! 👋 I'm your VitaLens assistant. I've read your data from the last 12 months. Ask me anything about your trends, lab results or medicines, or tap a suggestion below.` })) + hist.map(msgHtml).join("");
      box.scrollTop = box.scrollHeight;
    };
    const send = async q => {
      q = q.trim(); if (!q) return;
      const hist = S.u("chat", []); hist.push({ role: "user", text: q }); S.uset("chat", hist); draw();
      box.insertAdjacentHTML("beforeend", `<div class="msg bot" id="typing"><span class="typing"><i></i><i></i><i></i></span></div>`); box.scrollTop = box.scrollHeight;
      const c = ctx(); c.history = hist.slice(0, -1);
      const [r] = await Promise.all([VL.ai.ask(VL.state.p, q, c), new Promise(res => setTimeout(res, 450))]);
      const h2 = S.u("chat", []); h2.push({ role: "bot", text: r.text, source: r.source, model: r.model, checks: r.checks }); S.uset("chat", h2.slice(-40)); draw();
    };
    draw();
    $("cmp").onsubmit = e => { e.preventDefault(); const q = $("q").value; $("q").value = ""; send(q); };
    document.querySelectorAll("[data-q]").forEach(b => (b.onclick = () => send(b.dataset.q)));
    $("clr").onclick = () => { S.uset("chat", []); draw(); };
    const pending = S.get("pendingAsk"); if (pending) { S.del("pendingAsk"); send(pending); }
    $("q").focus();
  };

  /* =================================================================== doctor report */
  function report() {
    const p = VL.state.p, pr = profile(), F = I.findings(p), sc = I.score(p);
    const outLabs = Object.keys(p.labs).map(k => I.lab(p, k)).filter(L => L && !L.inRange);
    const checks = S.u("checkins", []);
    const myQ = S.u("myQuestions", []);
    const qs = I.doctorQuestions(p).concat(myQ);
    return `<div class="page-head noprint"><div><h1>Doctor report</h1><p class="muted small" style="margin-top:4px">A one-page summary to bring to your next appointment. Print it or save it as PDF.</p></div>
      <div class="row"><button class="btn" id="cp">📋 Copy as text</button><button class="btn primary" id="pr">🖨️ Print / Save PDF</button></div></div>
      <section class="card stack" id="rep">
        <div class="row"><div><h2>Health summary: ${esc(pr.name || VL.state.uid)}</h2><p class="small muted">Health ID ${VL.state.uid} · ${p.age} · ${esc(p.sex)} · Data Sep 2025 – Aug 2026 · Prepared ${VL.fmt.date(today())}</p></div><span class="pill ai">Wellness score ${sc.total}/100</span></div>
        <div class="grid g2">
          <div><h3>Current medicines</h3><div class="md">${I.activeMeds(p).map(m => { const a = p.adherence.find(x => x.medication === m.medication); return `<div class="li">${esc(m.medication)} ${esc(m.dose)}, ${esc(m.frequency.toLowerCase())}${a ? ` (about ${a.mean}% of doses taken)` : ""}</div>`; }).join("") || "<p class='muted small'>None</p>"}</div></div>
          <div><h3>Lab results outside the normal range</h3><div class="md">${outLabs.map(L => `<div class="li">${esc(L.name)}: ${n(L.last, L.dec)} ${esc(L.unit)} (normal ${esc(L.ref)})</div>`).join("") || "<p class='muted small'>None</p>"}</div></div>
          <div><h3>What improved</h3><div class="md">${F.wins.slice(0, 5).map(w => `<div class="li">${esc(w.text)}</div>`).join("") || "<p class='muted small'>No clear changes</p>"}</div></div>
          <div><h3>What I'd like to discuss</h3><div class="md">${F.watch.slice(0, 5).map(w => `<div class="li">${esc(w.text.split(". ").slice(0, 2).join(". "))}</div>`).join("") || "<p class='muted small'>Nothing flagged</p>"}</div></div></div>
        ${checks.length ? `<div><h3>My recent check-ins</h3><p class="small">${checks.length} check-ins. Average mood ${n(checks.reduce((s, c) => s + (c.mood || 3), 0) / checks.length, 1)}/5.${(() => { const sy = {}; checks.forEach(c => (c.symptoms || []).forEach(x => (sy[x] = (sy[x] || 0) + 1))); const e = Object.entries(sy); return e.length ? " Symptoms logged: " + e.map(([k, v]) => `${k} ×${v}`).join(", ") + "." : ""; })()}</p></div>` : ""}
        <div><h3>My questions for the doctor</h3><ol class="small" style="margin:6px 0 0;padding-left:20px">${qs.map(q => `<li style="margin-top:4px">${esc(q)}</li>`).join("")}</ol>
          <form class="row noprint" id="aq" style="margin-top:10px;justify-content:flex-start"><label class="sr" for="aqi">Add your own question</label><input class="input" id="aqi" style="flex:1;min-width:200px" placeholder="Add your own question"><button class="btn sm">Add</button></form></div>
        <p class="tiny muted">Generated by VitaLens from the user's own data. Describes changes only; it is not a diagnosis.</p></section>`;
  }
  AFTER.report = () => {
    $("pr").onclick = () => window.print();
    $("cp").onclick = async () => { try { await navigator.clipboard.writeText($("rep").innerText); toast("Report copied ✓"); } catch (e) { toast("Copy not allowed here. Use Print instead."); } };
    $("aq").onsubmit = e => { e.preventDefault(); const v = $("aqi").value.trim(); if (!v) return; S.uset("myQuestions", S.u("myQuestions", []).concat(v)); route(); };
  };

  /* =================================================================== settings */
  function settings() {
    const pr = profile(), cfg = VL.ai.settings(), th = S.get("theme", "auto");
    return `<div class="page-head"><div><h1>Settings</h1></div></div>
      <div class="grid g2">
        <form class="card stack" id="pf"><h2>👤 Profile</h2>
          <div><label class="lbl" for="s-name">Name</label><input class="input" id="s-name" value="${esc(pr.name)}" maxlength="30"></div>
          <div><span class="lbl">Goals</span><div class="chips">${Object.entries(K.GOALS).map(([k, g]) => `<button type="button" class="chip" data-g="${k}" aria-pressed="${pr.goals.includes(k)}">${g.icon} ${g.label}</button>`).join("")}</div></div>
          <div><span class="lbl">Theme</span><div class="chips">${["auto", "light", "dark"].map(t => `<button type="button" class="chip" data-th="${t}" aria-pressed="${th === t}">${t === "auto" ? "🌗 Auto" : t === "light" ? "☀️ Light" : "🌙 Dark"}</button>`).join("")}</div></div>
          <button class="btn primary">Save profile</button></form>
        <form class="card stack" id="af"><h2>🤖 AI model</h2>
          <p class="small muted">The built-in AI works offline with no key. For more natural answers, connect a large language model with your own API key. The key is stored only in this browser and sent only to the provider you choose. Don't save a key on a shared computer.</p>
          <div><label class="lbl" for="s-prov">Provider</label><select class="input" id="s-prov">${Object.entries(VL.ai.PROVIDERS).map(([k, v]) => `<option value="${k}" ${cfg.provider === k ? "selected" : ""}>${esc(v.label)}</option>`).join("")}</select></div>
          <div id="keyrow" ${cfg.provider === "offline" ? "hidden" : ""} class="stack">
            <div><label class="lbl" for="s-key">API key</label><input class="input mono" id="s-key" type="password" value="${esc(cfg.key)}" autocomplete="off" placeholder="Paste your key"><p class="tiny muted" id="keyhelp" style="margin-top:4px">${esc((VL.ai.PROVIDERS[cfg.provider] || {}).keyHelp || "")}</p></div>
            <div><label class="lbl" for="s-model">Model</label><input class="input mono" id="s-model" value="${esc(cfg.model || (VL.ai.PROVIDERS[cfg.provider] || {}).model || "")}"></div></div>
          <div class="row" style="justify-content:flex-start"><button class="btn primary">Save AI settings</button><button type="button" class="btn" id="test">Test connection</button></div>
          <p class="small" id="testout" aria-live="polite"></p>
          <div class="notice info">🛡️ <span>Every AI answer is checked: emergency words get a 911 message first, diagnosis wording is removed, and numbers are compared with your data.</span></div></form>
      </div>
      <section class="card sec stack" style="margin-top:16px"><h2>🔒 My data</h2>
        <p class="small muted">Your health record comes from the VitaLens pipeline. Check-ins, ticks, chat and settings stay in this browser only.</p>
        <div class="row" style="justify-content:flex-start"><button class="btn" id="exp">⬇️ Download my entries (JSON)</button><button class="btn" id="del">🗑️ Delete my entries</button><button class="btn ghost" id="out">↩ Sign out</button></div></section>`;
  }
  AFTER.settings = () => {
    let theme = S.get("theme", "auto");
    document.querySelectorAll("[data-g]").forEach(b => (b.onclick = () => b.setAttribute("aria-pressed", b.getAttribute("aria-pressed") !== "true")));
    document.querySelectorAll("[data-th]").forEach(b => (b.onclick = () => { theme = b.dataset.th; document.querySelectorAll("[data-th]").forEach(x => x.setAttribute("aria-pressed", x === b)); S.set("theme", theme); applyTheme(); }));
    $("pf").onsubmit = e => { e.preventDefault(); const pr = profile(); pr.name = $("s-name").value.trim(); pr.goals = [...document.querySelectorAll("[data-g][aria-pressed='true']")].map(b => b.dataset.g); S.uset("profile", pr); renderShell(); toast("Profile saved ✓"); };
    $("s-prov").onchange = () => { const v = $("s-prov").value; $("keyrow").hidden = v === "offline"; $("s-model").value = (VL.ai.PROVIDERS[v] || {}).model || ""; $("keyhelp").textContent = (VL.ai.PROVIDERS[v] || {}).keyHelp || ""; };
    const save = () => S.set("ai", { provider: $("s-prov").value, key: $("s-key").value.trim(), model: $("s-model").value.trim() });
    $("af").onsubmit = e => { e.preventDefault(); save(); S.del(`${VL.state.uid}:aisummary`); toast("AI settings saved ✓"); };
    $("test").onclick = async () => {
      save(); $("testout").textContent = "Testing…";
      const r = await VL.ai.ask(VL.state.p, "In one sentence, what is my average sleep recently?", ctx());
      $("testout").innerHTML = r.source === "offline" && VL.ai.settings().provider !== "offline" ? `<span style="color:var(--bad)">✗ Could not connect. ${esc(r.text.split("connection failed:")[1] || "").slice(0, 160)}</span>` : `<span style="color:var(--good)">✓ Working (${esc(r.source)}):</span> ${esc(r.text.slice(0, 200))}`;
    };
    $("exp").onclick = () => {
      const data = {}; const pre = `vl:${VL.state.uid}:`;
      if (S.ok) Object.keys(localStorage).filter(k => k.startsWith(pre)).forEach(k => (data[k.slice(pre.length)] = JSON.parse(localStorage.getItem(k))));
      const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }));
      a.download = `vitalens-${VL.state.uid}-entries.json`; a.click();
    };
    $("del").onclick = () => { if (confirm("Delete your check-ins, chat, goals and ticks from this browser?")) { S.clearUser(VL.state.uid); signOut(); } };
    $("out").onclick = signOut;
  };

  const PAGES = { home, trends, labs, meds, checkin, assistant, report, settings };

  /* =================================================================== start */
  async function start() {
    applyTheme();
    if (window.matchMedia) matchMedia("(prefers-color-scheme: dark)").addEventListener("change", applyTheme);
    C.installTooltip();
    try { await VL.data.loadIndex(); }
    catch (e) {
      $("app").innerHTML = `<div class="loading" style="max-width:560px;margin:auto;text-align:left"><h2>VitaLens couldn't load its data</h2><p style="margin-top:8px">The app reads the <span class="mono">data</span> folder with the browser, so it must be opened through a small local server, not by double-clicking the file.</p>
        <p style="margin-top:8px">In the project folder run <b class="mono">python start.py</b> (or <span class="mono">cd web</span> then <span class="mono">python -m http.server 8000</span>) and open <span class="mono">http://localhost:8000</span>.</p></div>`;
      return;
    }
    window.addEventListener("hashchange", () => (VL.state.p ? route() : null));
    let rw = window.innerWidth, rt;
    window.addEventListener("resize", () => { clearTimeout(rt); rt = setTimeout(() => { if (VL.state.p && Math.abs(window.innerWidth - rw) > 80 && !location.hash.includes("assistant") && !location.hash.includes("checkin") && !location.hash.includes("settings")) { rw = window.innerWidth; route(); } }, 250); });
    const sess = S.get("session");
    if (sess && VL.data.findRow(sess)) signIn(sess); else renderLogin();
  }
  start();
})();
