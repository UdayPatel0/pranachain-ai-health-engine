"""New patients (not in PranaChain's dataset): their own results, read from uploaded lab reports or typed in,
and the same three-scenario judgment as the dataset (metabolic, cardiovascular, PCOS).

The record built here has exactly the shape of a dataset record, so every screen, the AI, the safety checks,
sharing and the doctor view work for new patients without changes.

Scenario rules (first result vs latest result for each test, "meaningful" changes only):
  Metabolic      applies with prediabetes/diabetes, family history of diabetes, HbA1c >= 5.7 % or fasting glucose >= 100.
  Cardiovascular applies with high blood pressure/cholesterol, family history of heart disease, LDL >= 130,
                 total cholesterol >= 200, or blood pressure >= 130/80.
  PCOS           applies to women with a PCOS diagnosis or an average cycle longer than 35 days.
  Status: worse > better -> worsening; better > worse -> improving (or "improving, still above target");
          equal and both > 0 -> mixed; no change but above target -> needs review; no change -> stable;
          fewer than two results for every test -> "not enough results yet".
"""
from __future__ import annotations

import io
import json
import re
from datetime import date, datetime

# reference ranges: the same as PranaChain's dataset
REF = {
    "HbA1c": ("%", "4.0–5.6", 4.0, 5.6), "Fasting glucose": ("mg/dL", "70–99", 70.0, 99.0),
    "LDL cholesterol": ("mg/dL", "<100", None, 100.0), "HDL cholesterol": ("mg/dL", ">40", 40.0, None),
    "Total cholesterol": ("mg/dL", "<200", None, 200.0), "Triglycerides": ("mg/dL", "<150", None, 150.0),
    "ALT": ("U/L", "7–56", 7.0, 56.0), "AST": ("U/L", "10–40", 10.0, 40.0), "Creatinine": ("mg/dL", "0.7–1.3", 0.7, 1.3),
    "eGFR": ("mL/min/1.73m²", ">60", 60.0, None), "Hemoglobin": ("g/dL", "12.0–17.5", 12.0, 17.5),
    "TSH": ("mIU/L", "0.4–4.0", 0.4, 4.0), "Free T4": ("ng/dL", "0.8–1.8", 0.8, 1.8),
    "Vitamin D": ("ng/mL", "30–100", 30.0, 100.0), "Vitamin B12": ("pg/mL", "200–900", 200.0, 900.0),
    "Ferritin": ("ng/mL", "15–400", 15.0, 400.0),
    "Blood pressure (top)": ("mmHg", "<130", None, 130.0), "Blood pressure (bottom)": ("mmHg", "<80", None, 80.0),
}
HIGHER_IS_BETTER = {"HDL cholesterol", "eGFR", "Vitamin D", "Vitamin B12", "Hemoglobin"}
MIN_CHANGE = {"HbA1c": 0.2, "Fasting glucose": 5, "LDL cholesterol": 10, "HDL cholesterol": 3, "Total cholesterol": 10,
              "Triglycerides": 15, "ALT": 5, "AST": 5, "Creatinine": 0.1, "eGFR": 5, "Hemoglobin": 0.5, "TSH": 0.5,
              "Free T4": 0.2, "Vitamin D": 3, "Vitamin B12": 50, "Ferritin": 20,
              "Blood pressure (top)": 5, "Blood pressure (bottom)": 3}
PLAIN = {"HbA1c": "average blood sugar over the last 2 to 3 months", "Fasting glucose": "blood sugar after not eating overnight",
         "LDL cholesterol": "the 'bad' cholesterol", "HDL cholesterol": "the 'good' cholesterol",
         "Triglycerides": "a type of fat in the blood", "Total cholesterol": "all the cholesterol in the blood",
         "Blood pressure (top)": "pressure when the heart beats", "Blood pressure (bottom)": "pressure between beats"}
TARGETS = {"HbA1c": "below 5.7 %", "Fasting glucose": "70 to 99 mg/dL", "LDL cholesterol": "below 100 mg/dL",
           "Blood pressure": "below 130/80 mmHg", "Typical cycle length": "21 to 35 days"}
CONDITIONS = {"prediabetes": "Prediabetes", "diabetes": "Type 2 diabetes", "hypertension": "High blood pressure",
              "high_cholesterol": "High cholesterol", "pcos": "PCOS", "hypothyroidism": "Hypothyroidism"}
FAMILY = {"diabetes": "Family history of diabetes", "heart": "Family history of heart disease"}
TESTS = list(REF)
MED_KIND = {"metabolic": ["metformin", "insulin", "glipizide", "gliclazide", "sitagliptin", "semaglutide", "ozempic",
                          "empagliflozin", "dapagliflozin", "jardiance", "januvia", "pioglitazone"],
            "cardio": ["statin", "atorvastatin", "rosuvastatin", "simvastatin", "pravastatin", "lipitor", "crestor", "ezetimibe",
                       "amlodipine", "lisinopril", "ramipril", "perindopril", "losartan", "valsartan", "candesartan", "telmisartan",
                       "hydrochlorothiazide", "indapamide", "metoprolol", "bisoprolol", "atenolol"]}


def _r(v: float, d: int = 2) -> float:
    return float(f"{v:.{d}f}")


# ---------------- reading values from a lab report ----------------
_PATTERNS = [
    ("HbA1c", r"\b(?:ha?emoglobin\s*a1c(?:\s*\(\s*hba1c\s*\))?|hb\s*a1c|a1c|glyc(?:osyl)?ated\s+ha?emoglobin)"),
    ("Fasting glucose", r"\b(?:fasting\s+(?:plasma\s+|blood\s+)?(?:glucose|sugar)|glucose[,\s]*\(?fasting\)?|fbs|fbg|fpg)\b"),
    ("LDL cholesterol", r"\bldl\b"), ("HDL cholesterol", r"\bhdl\b"),
    ("Total cholesterol", r"\b(?:total\s+cholesterol|cholesterol[,\s]*total)\b"),
    ("Triglycerides", r"\btriglycerides?\b"), ("ALT", r"\b(?:alt|sgpt|alanine\s+aminotransferase)\b"),
    ("AST", r"\b(?:ast|sgot|aspartate\s+aminotransferase)\b"), ("eGFR", r"\begfr\b"), ("Creatinine", r"\bcreatinine\b"),
    ("Hemoglobin", r"\bha?emoglobin\b(?!\s*a1c)"), ("TSH", r"\btsh\b"), ("Free T4", r"\b(?:free\s+t4|ft4)\b"),
    ("Vitamin D", r"\b(?:vitamin\s+d|25[\s-]*oh)"), ("Vitamin B12", r"\b(?:vitamin\s+b12|b12)\b"), ("Ferritin", r"\bferritin\b"),
]
_NUM = re.compile(r"(?<![\w.])(\d{1,4}(?:[.,]\d+)?)(?![\d.])")
_DATE_PATTERNS = [
    (re.compile(r"\b(20\d\d)[-/.](\d{1,2})[-/.](\d{1,2})\b"), "ymd"),
    (re.compile(r"\b(\d{1,2})[-/.](\d{1,2})[-/.](20\d\d)\b"), "dmy"),
    (re.compile(r"\b(\d{1,2})\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?,?\s+(20\d\d)\b", re.I), "dMy"),
    (re.compile(r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+(\d{1,2}),?\s+(20\d\d)\b", re.I), "Mdy"),
]
_MON = {m: i for i, m in enumerate("jan feb mar apr may jun jul aug sep oct nov dec".split(), 1)}


def _find_date(text: str) -> str | None:
    low = text.lower()
    hint = re.search(r"(collect|sample|report(ed)?|test|drawn|date)", low)
    order = [low[hint.start():]] if hint else []
    order.append(low)
    for chunk in order:
        for rx, kind in _DATE_PATTERNS:
            m = rx.search(chunk)
            if not m:
                continue
            try:
                g = m.groups()
                if kind == "ymd":
                    d = date(int(g[0]), int(g[1]), int(g[2]))
                elif kind == "dmy":  # day/month/year (Canada, India, UK); if the day is > 12 it can only be that
                    a, b = int(g[0]), int(g[1])
                    d = date(int(g[2]), b, a) if a > 12 or b <= 12 else date(int(g[2]), a, b)
                elif kind == "dMy":
                    d = date(int(g[2]), _MON[g[1][:3].lower()], int(g[0]))
                else:
                    d = date(int(g[2]), _MON[g[0][:3].lower()], int(g[1]))
                if d <= date.today():
                    return d.isoformat()
            except ValueError:
                continue
    return None


def _convert(test: str, v: float, line: str) -> float | None:
    """Convert common SI units to the units VitaLens uses, and drop impossible values."""
    low = line.lower()
    if test == "Fasting glucose" and ("mmol" in low or v < 30):
        v = v * 18.0
    elif test in ("LDL cholesterol", "HDL cholesterol", "Total cholesterol") and ("mmol" in low or v < 15):
        v = v * 38.67
    elif test == "Triglycerides" and ("mmol" in low or v < 15):
        v = v * 88.57
    elif test == "HbA1c" and ("mmol/mol" in low or v > 20):
        v = v / 10.929 + 2.15
    elif test == "Hemoglobin" and ("g/l" in low.replace("g/dl", "") or v > 30):
        v = v / 10
    ok = {"HbA1c": (3, 20), "Fasting glucose": (30, 600), "LDL cholesterol": (10, 400), "HDL cholesterol": (5, 150),
          "Total cholesterol": (50, 600), "Triglycerides": (10, 2000), "Hemoglobin": (3, 25), "TSH": (0.01, 100)}
    lo, hi = ok.get(test, (0, 100000))
    return _r(v, 2) if lo <= v <= hi else None


def extract_text(data: bytes, mime: str) -> str:
    if mime != "application/pdf":
        return ""
    try:
        from pypdf import PdfReader
        return "\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(data)).pages[:10])
    except Exception:
        return ""


def find_values(text: str) -> dict:
    """Find lab values in report text. Returns {'date': ..., 'values': [{'test','value','unit','line'}]}.
    The patient always confirms or corrects these before they are saved."""
    found: dict[str, dict] = {}
    for raw in text.splitlines():
        line = " ".join(raw.split())
        low = line.lower()
        hb_a1c_line = bool(re.search(_PATTERNS[0][1], low))
        for test, pat in _PATTERNS:
            if test in found or (test == "Hemoglobin" and hb_a1c_line):
                continue
            m = re.search(pat, low)
            if not m:
                continue
            rest = line[m.end():]
            if test == "Vitamin D":
                rest = re.sub(r"^\s*[,(]?\s*25[\s-]*(?:oh|hydroxy)\)?", "", rest, flags=re.I)
            nm = _NUM.search(rest)
            if not nm:
                continue
            v = _convert(test, float(nm.group(1).replace(",", ".")), line)
            if v is not None:
                found[test] = {"test": test, "value": v, "unit": REF[test][0], "line": line[:140]}
    return {"date": _find_date(text), "values": list(found.values())}


# ---------------- building the record ----------------
def _cycles(starts: list[str]) -> dict | None:
    ds = sorted({s for s in starts})
    if len(ds) < 2:
        return None
    dd = [datetime.fromisoformat(d) for d in ds]
    lens = [(b - a).days for a, b in zip(dd, dd[1:]) if 0 < (b - a).days < 200]
    if not lens:
        return None
    mean = sum(lens) / len(lens)
    sd = (sum((x - mean) ** 2 for x in lens) / len(lens)) ** 0.5
    return {"n": len(lens), "mean": _r(mean, 1), "sd": _r(sd, 1), "long": sum(1 for x in lens if x > 35),
            "short": sum(1 for x in lens if x < 21), "max": max(lens),
            "cycles": [[d, l, None, ""] for d, l in zip(ds, lens)]}


def _labs(results: list[dict]) -> dict:
    labs = {}
    for test in TESTS:
        pts = sorted((r["date"], float(r["value"])) for r in results if r["test"] == test)
        if not pts:
            continue
        unit, ref, lo, hi = REF[test]
        first, last = pts[0][1], pts[-1][1]
        ch = last - first
        out = lambda v: (lo is not None and v < lo) or (hi is not None and v > hi)
        if len(pts) < 2 or abs(ch) < MIN_CHANGE.get(test, 0):
            direction = "stable" if len(pts) >= 2 else None
        else:
            up_good = test in HIGHER_IS_BETTER
            direction = "better" if (ch > 0) == up_good else "worse"
            if hi is not None and lo is not None and not out(first) and not out(last):
                direction = "stable"  # moved, but stayed inside the normal range
        labs[test] = {"unit": unit, "ref": ref, "lo": lo, "hi": hi, "points": [list(p) for p in pts],
                      "first": _r(first), "last": _r(last), "change": _r(ch), "direction": direction,
                      "last_outside": out(last), "first_outside": out(first)}
    return labs


def _judge(name_id: str, labs: dict, tests: list[str], context: list[dict], targets: dict, extra=None) -> dict | None:
    if not context:
        return None
    ev = list(extra or [])
    for t in tests:
        L = labs.get(t)
        if not L:
            continue
        if L["direction"] in ("worse", "better", "stable"):
            ev.append({"kind": "lab", "name": t, "dir": L["direction"] if L["direction"] != "stable" else "steady",
                       "from": L["first"], "to": L["last"], "unit": L["unit"]})
        elif L["last_outside"]:
            ev.append({"kind": "lab", "name": t, "dir": "flag", "from": L["first"], "to": L["last"], "unit": L["unit"],
                       "note": "Only one result so far. Add another later to see the trend."})
    above = [t for t, test in targets.items() if labs.get(t) and test(labs[t]["last"])]
    worse = sum(1 for e in ev if e["dir"] == "worse")
    better = sum(1 for e in ev if e["dir"] == "better")
    enough = any(len(labs[t]["points"]) >= 2 for t in tests if t in labs) or any(e["kind"] == "cycle" for e in ev)
    if not enough:
        status = "not_enough"
    elif worse > better:
        status = "worsening"
    elif better > worse:
        status = "improving_above_target" if above else "improving"
    elif worse and better:
        status = "mixed"
    else:
        status = "needs_review" if above or any(e["dir"] == "flag" for e in ev) else "stable"
    return {"id": name_id, "context": context, "evidence": ev, "worse": worse, "better": better,
            "above_target": above, "status": status}


def _responses(meds: list[dict], labs: dict) -> list[dict]:
    out = []
    for m in meds:
        if not m.get("start"):
            continue
        items = []
        for t, L in labs.items():
            before = [v for d, v in L["points"] if d < m["start"]]
            after = [v for d, v in L["points"] if d >= m["start"]]
            if before and after:
                ch = after[-1] - before[-1]
                items.append({"kind": "lab", "name": t, "unit": L["unit"], "before": _r(before[-1]), "after": _r(after[-1]),
                              "change": _r(ch), "meaningful": abs(ch) >= MIN_CHANGE.get(t, 0)})
        if items:
            out.append({"medication": m["medication"], "dose": m.get("dose"), "start": m["start"], "status": "Active",
                        "indication": m.get("indication", ""), "tolerance": "", "items": items})
    return out


STATUS_TEXT = {"worsening": "Worsening", "improving": "Improving", "improving_above_target": "Improving, still above target",
               "mixed": "Mixed", "needs_review": "Needs review", "stable": "Stable",
               "not_enough": "Not enough results yet to see a trend"}
SC_NAMES = {"metabolic": "Metabolic health (type 2 diabetes risk)", "cardio": "Cardiovascular (heart and blood vessel risk)",
            "pcos": "PCOS (women's health)"}


def build(pid: str, profile: dict, results: list[dict]) -> dict:
    labs_all = [r for r in results if r["test"] in REF]
    labs = _labs(labs_all)
    cyc = _cycles([r["date"] for r in results if r["test"] == "Period start"])
    cond, fam = set(profile.get("conditions", [])), set(profile.get("family", []))
    created = profile.get("created", date.today().isoformat())
    history = [{"date": created, "type": "Clinical finding", "finding": CONDITIONS[c], "status": "Reported by patient",
                "notes": "From sign-up"} for c in cond if c in CONDITIONS]
    meds = [{"medication": m["name"], "dose": m.get("dose", ""), "frequency": m.get("frequency", ""), "start": m.get("start"),
             "end": None, "status": "Active", "indication": m.get("for", ""), "tolerance": "", "rationale": ""}
            for m in profile.get("meds", []) if m.get("name")]

    def first(t):
        return labs[t]["points"][0] if t in labs else None

    # ---- metabolic
    ctx = [{"kind": "history", "text": CONDITIONS[c], "date": None} for c in ("prediabetes", "diabetes") if c in cond]
    if "diabetes" in fam:
        ctx.append({"kind": "family", "text": FAMILY["diabetes"], "date": None})
    for t, thr, unit in (("HbA1c", 5.7, "%"), ("Fasting glucose", 100, "mg/dL")):
        hit = next((p for p in (labs.get(t) or {}).get("points", []) if p[1] >= thr), None)
        if hit:
            ctx.append({"kind": "lab", "text": f"{t} {hit[1]:g} {unit} ({thr:g} {unit} or higher)", "date": hit[0]})
    metabolic = _judge("metabolic", labs, ["HbA1c", "Fasting glucose", "Triglycerides", "HDL cholesterol"], ctx,
                       {"HbA1c": lambda v: v >= 5.7, "Fasting glucose": lambda v: v >= 100})
    # ---- cardiovascular
    ctx = [{"kind": "history", "text": CONDITIONS[c], "date": None} for c in ("hypertension", "high_cholesterol") if c in cond]
    if "heart" in fam:
        ctx.append({"kind": "family", "text": FAMILY["heart"], "date": None})
    for t, thr in (("LDL cholesterol", 130), ("Total cholesterol", 200), ("Blood pressure (top)", 130), ("Blood pressure (bottom)", 80)):
        f = first(t)
        if f and f[1] >= thr:
            ctx.append({"kind": "lab", "text": f"First {t.lower()} {f[1]:g} {REF[t][0]} ({thr} or higher)", "date": f[0]})
    cardio = _judge("cardio", labs, ["LDL cholesterol", "Total cholesterol", "Triglycerides", "HDL cholesterol",
                                     "Blood pressure (top)", "Blood pressure (bottom)"], ctx,
                    {"LDL cholesterol": lambda v: v >= 100, "Blood pressure (top)": lambda v: v >= 130,
                     "Blood pressure (bottom)": lambda v: v >= 80})
    # ---- PCOS
    pcos = None
    if profile.get("sex") == "Female":
        ctx = [{"kind": "history", "text": "PCOS", "date": None}] if "pcos" in cond else []
        extra = []
        if cyc:
            if cyc["mean"] > 35 or cyc["long"] >= max(2, cyc["n"] // 2):
                ctx.append({"kind": "cycle", "text": f"Average cycle {cyc['mean']:g} days; {cyc['long']} cycles longer than 35 days", "date": None})
            extra.append({"kind": "cycle", "name": "Cycle length", "dir": "flag" if cyc["mean"] > 35 or cyc["long"] else "steady",
                          "to": cyc["mean"], "sd": cyc["sd"], "long": cyc["long"], "n": cyc["n"], "unit": "days (typical 21–35)"})
        pcos = _judge("pcos", labs, ["HbA1c", "Fasting glucose"], ctx, {"HbA1c": lambda v: v >= 5.7}, extra)
        if pcos:
            for e in pcos["evidence"]:
                if e["kind"] == "lab":
                    e["note"] = "Metabolic markers are relevant in PCOS because insulin resistance is common."
    scen = {"metabolic": metabolic, "cardio": cardio, "pcos": pcos}
    resp = _responses(meds, labs)
    for r in resp:  # show each medicine's before/after inside the check it treats
        names = {i["name"] for i in r["items"]}
        low = r["medication"].lower()
        kinds = [k for k, words in MED_KIND.items() if any(w in low for w in words)]
        for k, tests in (("metabolic", {"HbA1c", "Fasting glucose"}), ("cardio", {"LDL cholesterol", "Total cholesterol", "Blood pressure (top)", "Blood pressure (bottom)"})):
            if scen[k] and k in kinds and names & tests:
                scen[k]["evidence"].append({"kind": "response", "name": r["medication"], "start": r["start"],
                                            "items": [i for i in r["items"] if i["name"] in tests | {"Triglycerides", "HDL cholesterol"}]})

    dates = sorted(r["date"] for r in results)
    period = f"{_month(dates[0])} to {_month(dates[-1])}" if dates else "No results yet"
    evidence = {
        "person": {"age": profile.get("age"), "sex": profile.get("sex")},
        "period": f"{period}. 'First' = the person's first result for each test; 'latest' = their most recent result.",
        "scenarios": [{"name": SC_NAMES[k], "status": STATUS_TEXT[v["status"]],
                       "why_this_scenario": [c["text"] + (f" ({c['date']})" if c.get("date") else "") for c in v["context"]],
                       "evidence": [{"measure": e["name"], "usual_or_first": e.get("from"), "recent_or_last": e.get("to"),
                                     "unit": e.get("unit"), "change": _r(e["to"] - e["from"]) if e.get("from") is not None and e.get("to") is not None else None,
                                     "direction": e["dir"]} for e in v["evidence"] if e["kind"] == "lab"]
                                   + [{"measure": "Cycle length", "average_days": e["to"], "cycles_longer_than_35_days": e["long"],
                                       "cycles_counted": e["n"]} for e in v["evidence"] if e["kind"] == "cycle"],
                       "still_above_target": v["above_target"]} for k, v in scen.items() if v],
        "medicines": [{"name": r["medication"], "started": r["start"],
                       "changes_after_start": [{"measure": i["name"], "before": i["before"], "after": i["after"], "unit": i["unit"],
                                                "meaningful_change": i["meaningful"]} for i in r["items"]]} for r in resp],
        "other_changes": [{"measure": t, "usual": L["first"], "recent": L["last"], "unit": L["unit"], "direction": L["direction"]}
                          for t, L in labs.items() if L["direction"] in ("worse", "better")
                          and not any(t == e.get("name") for v in scen.values() if v for e in v["evidence"])],
        "targets": TARGETS, "plain_words": {k: v for k, v in PLAIN.items() if k in labs},
    }
    rule = _rule_text(scen, labs)
    return {
        "id": pid, "age": profile.get("age"), "sex": profile.get("sex"), "height": profile.get("height"),
        "blood_group": profile.get("blood_group") or "Not given", "allergies": profile.get("allergies") or "Not given",
        "family": "; ".join(FAMILY[f] for f in fam if f in FAMILY) or "None reported",
        "history": history, "meds": meds, "responses": resp, "adherence": [], "labs": labs, "trends": {}, "bp_target": None,
        "cycles": cyc, "symptoms": [], "relationships": [], "habits": {}, "scenarios": scen, "issues": [],
        "completeness": 1.0, "ai": {"evidence": evidence, "rule_text": rule},
        "is_new": True, "period_label": period, "results_count": len(results),
    }


def _month(d: str) -> str:
    return datetime.fromisoformat(d).strftime("%B %Y")


def _rule_text(scen: dict, labs: dict) -> str:
    if not labs and not any(scen.values()):
        return "Add your first results (upload a lab report or type them in) and VitaLens will show what they mean for you."
    parts = []
    for k, v in scen.items():
        if not v:
            continue
        s = f"{SC_NAMES[k]}: {STATUS_TEXT[v['status']].lower()}."
        ch = [f"{e['name']} went from {e['from']:g} to {e['to']:g} {e['unit']}" for e in v["evidence"]
              if e["kind"] == "lab" and e["dir"] in ("worse", "better")]
        if ch:
            s += " " + "; ".join(ch) + "."
        if v["above_target"]:
            s += " Still above target: " + ", ".join(v["above_target"]) + "."
        parts.append(s)
    if not parts:
        parts.append("None of the three main checks apply to you based on what you've shared so far.")
    return " ".join(parts) + " This is not a diagnosis. Please talk to your doctor about these results."


def profile_from_json(s: str) -> dict:
    return json.loads(s) if s else {}
