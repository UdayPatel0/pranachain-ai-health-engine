// Data rules for the patient overview, ported 1:1 from web/index.html so both views agree.
// Owner: Nancy · built with AI assistance (Claude), reviewed by the team

export const STATUS = {
  worsening: "Worsening", mixed: "Mixed changes", needs_review: "Above target · review",
  improving_above_target: "Improving, still above target", improving: "Improving", stable: "Stable", none: "Not in scenario",
};
export const SCN = {
  metabolic: { n: "01", t: "Metabolic health", s: "Type 2 diabetes risk" },
  cardio: { n: "02", t: "Cardiovascular", s: "Hypertension risk" },
  pcos: { n: "03", t: "PCOS", s: "Women's health" },
};

const GLY = ["Borderline glycemic markers", "Prediabetes", "Type 2 diabetes"];
// Which data belongs to which body system (same as SYS in web/index.html, without the 3D settings)
export const SYS = {
  heart: { name: "Heart", sig: [["rhr", "up"], ["hrv", "down"]], labs: [], meds: [], hist: [], sym: ["Dizziness"] },
  vessels: { name: "Blood vessels & blood", sig: [["sbp", "up"], ["dbp", "up"]], bp: true, labs: ["LDL cholesterol", "Total cholesterol", "Triglycerides", "HDL cholesterol", "eGFR", "Urine albumin/creatinine", "Creatinine", "Potassium", "Sodium", "Hemoglobin", "Ferritin", "WBC", "Platelets"], meds: ["Amlodipine", "Atorvastatin", "Ferrous sulfate"], hist: ["Hypertension", "Hyperlipidemia", "Iron deficiency"], sym: [] },
  metabolic: { name: "Pancreas & liver", sig: [], labs: ["HbA1c", "Fasting glucose", "Triglycerides", "ALT", "AST"], meds: ["Metformin", "Metformin XR"], hist: GLY, sym: ["Increased thirst", "Frequent urination"] },
  digestion: { name: "Stomach", sig: [], labs: [], meds: ["Pantoprazole"], hist: ["GERD"], sym: ["Heartburn", "Acid reflux", "Bloating"] },
  thyroid: { name: "Thyroid", sig: [], labs: ["TSH", "Free T4"], meds: ["Levothyroxine"], hist: ["Hypothyroidism"], sym: ["Fatigue"] },
  lungs: { name: "Lungs", sig: [["spo2", "down"], ["rr", "up"]], labs: [], meds: ["Budesonide/formoterol"], hist: ["Asthma"], sym: ["Wheezing", "Shortness of breath", "Nasal congestion"] },
  sleep: { name: "Brain · sleep & stress", sig: [["sleep", "down"], ["stress", "up"]], labs: [], meds: ["Sumatriptan"], hist: ["Migraine"], sym: ["Poor sleep", "Headache", "Migraine headache", "Light sensitivity"] },
  hormones: { name: "Ovaries & uterus", sig: [], labs: [], meds: [], hist: ["PCOS"], sym: ["Menstrual cramps", "Irregular cycle"], cycles: true },
  activity: { name: "Muscles · activity", sig: [["steps", "down"], ["active", "down"], ["sedentary", "up"]], labs: [], meds: [], hist: [], sym: ["Muscle ache", "Muscle soreness"] },
  body: { name: "Body & nutrition", sig: [["weight", "up"]], labs: ["Vitamin D", "Vitamin B12"], meds: ["Cholecalciferol", "Vitamin D3"], hist: ["Vitamin D insufficiency"], sym: [] },
};
export const ORDER = ["heart", "vessels", "metabolic", "digestion", "thyroid", "lungs", "sleep", "hormones", "activity", "body"];

export function labDir(p, t) { const L = p.labs[t]; if (!L) return null; return L.direction === "worse" ? "worse" : L.last_outside ? "flag" : "ok"; }

/** worse / flag / ok / nodata per body system (same rules as computeStatus in web/index.html) */
export function systemStatus(p) {
  const out = {};
  for (const k of ORDER) {
    const s = SYS[k]; let worse = 0, flag = 0, has = 0;
    s.sig.forEach(([key, bad]) => { const t = p.trends[key]; if (!t || t.baseline == null) return; has++; if (t.direction === bad) worse++; });
    if (s.bp && p.bp_target) { has++; if (p.bp_target.recent - p.bp_target.baseline >= 10) worse++; else if (p.bp_target.recent >= 50) flag++; }
    s.labs.forEach((t) => { const d = labDir(p, t); if (!d) return; has++; if (d === "worse") worse++; else if (d === "flag") flag++; });
    if (s.cycles && p.cycles) { has++; if (p.cycles.mean > 35 || p.cycles.long >= 2) flag++; }
    if (s.hist.some((h) => p.history.some((x) => x.finding === h))) { flag++; has++; }
    if (s.meds.some((m) => p.meds.some((x) => x.medication === m))) has++;
    if (s.sym.some((m) => p.symptoms.some((x) => x[1] === m))) has++;
    out[k] = !has ? "nodata" : worse ? "worse" : flag ? "flag" : "ok";
  }
  if (p.sex !== "Female") out.hormones = "nodata";
  return out;
}

export function systemSummary(p, k, status) {
  const s = SYS[k];
  const bad = [...s.sig.filter(([key, b]) => p.trends[key] && p.trends[key].direction === b).map(([key]) => p.trends[key].label), ...s.labs.filter((t) => labDir(p, t) === "worse")];
  const fl = s.labs.filter((t) => labDir(p, t) === "flag");
  return status === "nodata" ? "No data for this patient" : bad.length ? "Worse: " + bad.join(", ") : fl.length ? "Outside reference: " + fl.join(", ") : "Within usual range";
}

const MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
export const fmtD = (s) => { if (!s) return ""; const [y, m, d] = s.split("-").map(Number); return `${d} ${MON[m - 1]} ${y}`; };
export const num = (v, d = 1) => (v == null ? "–" : Math.abs(v) >= 1000 ? Math.round(v).toLocaleString("en-US") : (+v).toFixed(d));
