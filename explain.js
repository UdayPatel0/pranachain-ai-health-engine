/* VitaLens · "Explain in plain words"
 * Owner: Nancy (Frontend & UX) · COMP 8967 Group 1 · built with AI assistance (Claude), reviewed by the team
 *
 * One shared module used by BOTH the HTML demo (web/index.html) and the React app (frontend/).
 * It does four things:
 *   1. buildEvidence(patient)        -> the small evidence summary the AI is allowed to talk about
 *   2. getExplanation(patient, opts) -> asks the AI endpoint (Rishi's FastAPI) and, if it is not
 *                                       running yet, falls back to a rule-based PREVIEW explanation
 *   3. safetyCheck(text, evidence)   -> numbers must match the evidence, no diagnosis / medicine-change
 *                                       words, disclaimer required (same rules as Rishi's backend checks)
 *   4. readability(text)             -> is it easy for patients to read? (grade level, sentence length,
 *                                       unexplained medical words)
 * The panel only shows the AI's words when the safety check passes.
 */

/* ---------- plain-language names ---------- */
// Medical words get a plain name first; the medical word is kept in brackets so patients can
// match it to their lab report. Anything in brackets is treated as "explained" by readability().
export const PLAIN = {
  // daily signals
  weight: "weight",
  steps: "daily steps",
  active: "active minutes each day",
  sedentary: "time spent sitting",
  sleep: "sleep each night",
  stress: "stress score",
  rhr: "heart rate at rest",
  hrv: "heart rhythm score (HRV)",
  sbp: "top blood pressure number",
  dbp: "bottom blood pressure number",
  spo2: "oxygen level (SpO2)",
  rr: "breathing rate",
  bpdays: "share of days with blood pressure of 130/80 or higher",
  // labs
  "HbA1c": "average blood sugar (HbA1c)",
  "Fasting glucose": "blood sugar before eating (fasting glucose)",
  "LDL cholesterol": "bad cholesterol (LDL)",
  "HDL cholesterol": "good cholesterol (HDL)",
  "Total cholesterol": "total cholesterol",
  "Triglycerides": "blood fat level (triglycerides)",
  "Triglyceride/HDL ratio": "blood fat balance (triglyceride to HDL ratio)",
  "eGFR": "kidney filter score (eGFR)",
  "Creatinine": "kidney waste level (creatinine)",
  "Urine albumin/creatinine": "protein in urine (albumin)",
  "ALT": "liver test (ALT)",
  "AST": "liver test (AST)",
  "TSH": "thyroid test (TSH)",
  "Free T4": "thyroid hormone (free T4)",
  "Vitamin D": "vitamin D",
  "Vitamin B12": "vitamin B12",
  "Hemoglobin": "iron in red blood cells (hemoglobin)",
  "Ferritin": "iron stores (ferritin)",
  "Potassium": "potassium",
  "Sodium": "salt level (sodium)",
};
const SIGNAL_BY_NAME = {
  "Weight": "weight", "Daily steps": "steps", "Active minutes": "active", "Sedentary time": "sedentary",
  "Sleep": "sleep", "Stress score": "stress", "Resting heart rate": "rhr", "Heart rate variability": "hrv",
  "Home blood pressure (top)": "sbp", "Home blood pressure (bottom)": "dbp", "Blood oxygen (SpO2)": "spo2",
  "Breathing rate": "rr", "Days with BP at or above 130/80": "bpdays",
};
const AREA = { metabolic: "Blood sugar and weight", cardio: "Heart and blood pressure", pcos: "Monthly cycle" };
const MONTHS = ["January","February","March","April","May","June","July","August","September","October","November","December"];

export const DISCLAIMER = "This is not a diagnosis. Please talk with your doctor or care team about these results.";

/* Numbers the explanation may use even if they are not a patient value: the comparison window
   (first / last 3 months, 12 months), the typical cycle range (21–35 days) and the 130/80 BP line. */
export const STRUCTURAL_NUMBERS = [3, 12, 21, 35, 130, 80];

/* ---------- 1. evidence summary ---------- */
const plainOf = (e) => {
  if (e.kind === "signal") return PLAIN[e.key || SIGNAL_BY_NAME[e.name]] || e.name.toLowerCase();
  return PLAIN[e.name] || e.name;
};
// round like a person would read it: steps and % of days as whole numbers, % labs with 1 decimal
function roundFor(e, v) {
  if (v == null) return null;
  const u = e.unit || "";
  if (Math.abs(v) >= 100 || u === "steps" || u.startsWith("% of days") || u === "min/day" || u === "ms" || u === "bpm") return Math.round(v);
  if (u === "%") return Math.round(v * 10) / 10;
  return Math.round(v * 10) / 10;
}

/** The evidence the AI is given, and the ONLY facts it may state. Same shape will be sent to the LLM. */
export function buildEvidence(p) {
  const areas = [];
  for (const [id, sc] of Object.entries(p.scenarios || {})) {
    if (!sc) continue;
    const items = [];
    for (const e of sc.evidence || []) {
      if (e.kind === "response") {
        const it = (e.items || []).find((i) => i.kind !== "symptom" && i.before != null && i.after != null);
        items.push({ kind: "response", medicine: e.name, start: e.start, measure: it ? (PLAIN[it.name] || PLAIN[SIGNAL_BY_NAME[it.name]] || it.name) : null,
          from: it ? roundFor(it, it.before) : null, to: it ? roundFor(it, it.after) : null, unit: it ? it.unit : null, meaningful: it ? !!it.meaningful : false });
      } else if (e.kind === "cycle") {
        items.push({ kind: "cycle", measure: "monthly cycle length", to: e.to, long: e.long, n: e.n, dir: e.dir });
      } else {
        items.push({ kind: e.kind, name: e.name, measure: plainOf(e), from: roundFor(e, e.from), to: roundFor(e, e.to), unit: e.unit, dir: e.dir || "stable" });
      }
    }
    areas.push({ id, area: AREA[id] || id, status: sc.status, above_target: (sc.above_target || []).map((n) => PLAIN[n] || n), items });
  }
  return { patient: p.id, window: "first 3 months (Sep–Nov 2025) vs last 3 months (Jun–Aug 2026)", areas };
}

/* ---------- 2a. rule-based preview (stand-in until the AI endpoint is live) ---------- */
const fmt = (v) => (v == null ? "" : Math.abs(v) >= 1000 ? Math.round(v).toLocaleString("en-US") : String(v));
const unitWord = (u) => ({ "%": "%", kg: " kg", steps: " steps", "min/day": " minutes", "h/night": " hours", "% of days": "%", "% (estimated)": "%", bpm: " beats a minute", "of 10": " out of 10" }[u] ?? "");
const monthYear = (iso) => { if (!iso) return ""; const [y, m] = iso.split("-").map(Number); return `${MONTHS[m - 1]} ${y}`; };
const cap = (s) => s.charAt(0).toUpperCase() + s.slice(1);

function sentenceFor(it) {
  const u = unitWord(it.unit);
  switch (it.kind) {
    case "signal":
    case "lab":
    case "marker": {
      if (it.from == null || it.to == null) return null;
      const move = it.to > it.from ? "went up" : it.to < it.from ? "went down" : "stayed the same";
      const tail = it.dir === "better" ? " This is a good sign." : "";
      return `Your ${it.measure} ${move} from ${fmt(it.from)}${u} to ${fmt(it.to)}${u}.${tail}`;
    }
    case "response":
      if (!it.measure) return `You started ${it.medicine} in ${monthYear(it.start)}.`;
      if (!it.meaningful) return `After you started ${it.medicine} in ${monthYear(it.start)}, your ${it.measure} stayed about the same.`;
      return `After you started ${it.medicine} in ${monthYear(it.start)}, your ${it.measure} went from ${fmt(it.from)} to ${fmt(it.to)}${unitWord(it.unit)}.`;
    case "symptom":
      return `You told us about feeling very thirsty or needing the bathroom often ${it.to} times this year.`;
    case "adherence":
      return `You took ${it.name.replace(/ taken$/, "")} about ${fmt(it.to)}% of the time.`;
    case "cycle":
      return `Your monthly cycle was ${it.to} days long on average. A usual cycle is 21 to 35 days. ${it.long} of your ${it.n} cycles were longer than 35 days.`;
    default:
      return null;
  }
}

const RANK = { worse: 0, flag: 1, better: 2, stable: 3 };
/** Short, plain sentences from the evidence. Max 4 points per area so it stays easy to read. */
export function previewExplanation(ev) {
  const sections = [];
  if (!ev.areas.length) {
    sections.push({ area: "Your year in numbers", sentences: ["We did not find any big changes in your health data."] });
  }
  for (const a of ev.areas) {
    const items = [...a.items].sort((x, y) => (RANK[x.dir] ?? 2) - (RANK[y.dir] ?? 2));
    const sentences = items.map(sentenceFor).filter(Boolean).slice(0, 4);
    // say "worth a closer look" once per area, not after every line (test feedback: it was repetitive)
    if (items.slice(0, 4).some((i) => i.dir === "worse")) sentences.push("The changes that went the wrong way are worth a closer look with your care team.");
    if (a.above_target.length) sentences.push(`Your ${a.above_target.slice(0, 2).join(" and ")} ${a.above_target.length > 1 ? "are" : "is"} still above the healthy range.`);
    if (!sentences.length) sentences.push("We did not find any big changes here.");
    sections.push({ area: a.area, sentences });
  }
  return { source: "preview", model: "VitaLens rule-based preview (AI not connected)", intro: "Here is what changed in your health data. We compared your last 3 months with your first 3 months.", sections, disclaimer: DISCLAIMER };
}

export const explanationText = (x) => [x.intro, ...x.sections.flatMap((s) => s.sentences), x.disclaimer].filter(Boolean).join(" ");

/* ---------- 2b. ask the AI, fall back to preview ---------- */
/** opts.api: base URL of the FastAPI service (e.g. http://localhost:8001). Empty -> preview only.
 *  Expected response (contract in docs/ai-explanation-panel.md):
 *  { intro, sections:[{area, sentences:[...]}], disclaimer, model, safety? }  or  { text, model } */
export async function getExplanation(p, opts = {}) {
  const ev = buildEvidence(p);
  let x = null, apiError = null;
  if (opts.api) {
    try {
      const ctrl = new AbortController(); const t = setTimeout(() => ctrl.abort(), opts.timeoutMs || 12000);
      const r = await fetch(`${opts.api.replace(/\/$/, "")}/patients/${encodeURIComponent(p.id)}/explanation`, { signal: ctrl.signal });
      clearTimeout(t);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const j = await r.json();
      x = j.sections ? { ...j, source: "ai" } : { source: "ai", model: j.model, intro: "", sections: [{ area: "", sentences: splitSentences(j.text || "") }], disclaimer: "", server_safety: j.safety };
    } catch (e) { apiError = String(e.message || e); }
  }
  if (!x) x = previewExplanation(ev);
  if (opts.demoUnsafe) x = injectUnsafe(x); // test hook: ?demo=unsafe shows the blocked state
  const text = explanationText(x);
  return { ...x, apiError, evidence: ev, text, safety: safetyCheck(text, ev), readability: readability(text) };
}
function injectUnsafe(x) {
  const y = JSON.parse(JSON.stringify(x));
  (y.sections[0] || (y.sections[0] = { area: "", sentences: [] })).sentences.push("Your blood sugar of 9.4 means you have diabetes, so you should increase your dose.");
  y.disclaimer = "";
  return y;
}

/* ---------- 3. safety check ---------- */
// Diagnosis words and medicine-change advice are never allowed in patient text.
export const BLOCKED = [
  "diagnos", "diabetes", "diabetic", "prediabet", "hypertension", "hypertensive", "pcos", "polycystic",
  "disease", "disorder", "syndrome", "cancer", "tumou?r", "insulin resistance", "obese", "obesity",
  "you have [a-z ]{0,20}(condition|illness)", "stop taking", "start taking", "increase your dose",
  "reduce your dose", "lower your dose", "change your dose", "skip (a |your )?dose",
];
const NUM_RE = /(?<![A-Za-z\d.])\d{1,3}(?:,\d{3})+(?:\.\d+)?(?![A-Za-z\d])|(?<![A-Za-z\d.])\d+(?:\.\d+)?(?![A-Za-z\d])/g;

function allowedNumbers(ev) {
  const set = new Set(STRUCTURAL_NUMBERS.map(String));
  const add = (v) => { if (typeof v !== "number" || !isFinite(v)) return; for (const d of [0, 1, 2]) set.add(String(+v.toFixed(d))); };
  const walk = (o) => {
    if (o == null) return;
    if (typeof o === "number") return add(o);
    if (typeof o === "string") { // dates and "130/80"-style strings
      const m = o.match(/^(\d{4})-(\d{2})(?:-(\d{2}))?$/); if (m) { add(+m[1]); add(+m[3] || 1); return; }
      (o.match(/\d+(?:\.\d+)?/g) || []).forEach((n) => add(+n)); return;
    }
    if (Array.isArray(o)) return o.forEach(walk);
    if (typeof o === "object") { Object.values(o).forEach(walk); if (typeof o.from === "number" && typeof o.to === "number") add(Math.abs(o.to - o.from)); }
  };
  walk(ev.areas);
  return set;
}
export function numbersIn(text) { return (text.match(NUM_RE) || []).map((s) => String(+s.replace(/,/g, ""))); }

export function safetyCheck(text, ev) {
  const allowed = allowedNumbers(ev);
  const nums = numbersIn(text);
  const unknown = [...new Set(nums.filter((n) => !allowed.has(n)))];
  // the required disclaimer itself says "not a diagnosis", so it is removed before the word check
  const lower = text.toLowerCase().replace(/(this is )?not a diagnosis/g, " ");
  const blocked = BLOCKED.filter((w) => new RegExp(`\\b${w}`, "i").test(lower)).map((w) => (lower.match(new RegExp(`\\b${w}[a-z]*`, "i")) || [w])[0]);
  const disclaimer = /not a diagnosis/i.test(text) && /(doctor|care team)/i.test(text);
  const checks = [
    { id: "numbers", label: "Numbers match the evidence", pass: unknown.length === 0, detail: unknown.length ? `Not in the evidence: ${unknown.join(", ")}` : `${nums.length} numbers checked` },
    { id: "words", label: "No diagnosis or medicine-change words", pass: blocked.length === 0, detail: blocked.length ? `Found: ${[...new Set(blocked)].join(", ")}` : "None found" },
    { id: "disclaimer", label: "Says it is not a diagnosis", pass: disclaimer, detail: disclaimer ? "Disclaimer present" : "Disclaimer missing" },
  ];
  return { pass: checks.every((c) => c.pass), checks };
}

/* ---------- 4. readability ---------- */
// Patient materials should be at about a grade 6–8 reading level (NIH / AMA guidance).
export const READ_TARGET = { grade: 8, ideal: 6, wordsPerSentence: 20 };
export const JARGON = {
  "hba1c": "average blood sugar", "glucose": "blood sugar", "glycemic": "blood sugar", "ldl": "bad cholesterol",
  "hdl": "good cholesterol", "triglyceride": "blood fat", "egfr": "kidney filter score", "creatinine": "kidney waste level",
  "albumin": "protein in urine", "alt": "liver test", "ast": "liver test", "tsh": "thyroid test", "hrv": "heart rhythm score",
  "variability": "how much it changes", "spo2": "oxygen level", "systolic": "top number", "diastolic": "bottom number",
  "mmhg": "(leave the unit out)", "mg/dl": "(leave the unit out)", "baseline": "your usual level", "metabolic": "blood sugar and weight",
  "cardiovascular": "heart and blood vessels", "adherence": "how often you took it", "reference range": "healthy range",
  "correlat": "move together", "statistic": "(leave it out)", "significant": "clear", "trajectory": "trend", "ferritin": "iron stores",
  "hemoglobin": "iron in red blood cells", "sedentary": "sitting", "elevated": "high", "abnormal": "outside the usual range",
  "ovulation": "releasing an egg", "menstrual": "monthly", "medication": "medicine",
};
export function splitSentences(text) { return (text.replace(/\s+/g, " ").match(/[^.!?]+[.!?]+|[^.!?]+$/g) || []).map((s) => s.trim()).filter(Boolean); }
export function syllables(word) {
  let w = word.toLowerCase().replace(/[^a-z]/g, "");
  if (!w) return 1; // numbers read as one unit
  if (w.length <= 3) return 1;
  w = w.replace(/(?:[^laeiouy]es|ed|[^laeiouy]e)$/, "").replace(/^y/, "");
  const m = w.match(/[aeiouy]{1,2}/g);
  return Math.max(1, m ? m.length : 1);
}
export function readability(text) {
  const sentences = splitSentences(text);
  const words = text.match(/[A-Za-z][A-Za-z'’-]*|\d[\d,.]*/g) || [];
  const syl = words.reduce((a, w) => a + syllables(w), 0);
  const nW = Math.max(1, words.length), nS = Math.max(1, sentences.length);
  const grade = Math.max(0, +(0.39 * (nW / nS) + 11.8 * (syl / nW) - 15.59).toFixed(1));
  const ease = Math.round(206.835 - 1.015 * (nW / nS) - 84.6 * (syl / nW));
  const longest = sentences.reduce((m, s) => Math.max(m, (s.match(/\S+/g) || []).length), 0);
  const outside = text.replace(/\([^)]*\)/g, " ").toLowerCase(); // words in brackets are explained
  // short abbreviations must match a whole word ("alt" must not match "although"); longer stems may take endings
  const jargon = Object.entries(JARGON).filter(([k]) => new RegExp(`(^|[^a-z])${k.replace("/", "\\/")}${k.length <= 5 ? "(?![a-z])" : ""}`).test(outside)).map(([term, plain]) => ({ term, plain }));
  const wps = +(nW / nS).toFixed(1);
  const pass = grade <= READ_TARGET.grade && wps <= READ_TARGET.wordsPerSentence && jargon.length === 0;
  const level = grade <= READ_TARGET.ideal ? "Very easy" : grade <= READ_TARGET.grade ? "Easy" : grade <= 10 ? "A bit hard" : "Hard";
  return { pass, level, grade, ease, wordsPerSentence: wps, longestSentence: longest, sentences: nS, words: nW, jargon };
}
