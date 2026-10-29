"""VitaLens analysis: personal baselines, lab trajectories, medication responses,
signal relationships and the three PranaChain validation scenarios.

Everything is computed per patient from that patient's own data. Nothing is
diagnosed: each result is a described change with its evidence.
"""
from __future__ import annotations

import math
import re
import sqlite3

import numpy as np
import pandas as pd

WINDOW_START = pd.Timestamp("2025-09-01")
MONTHS = pd.date_range(WINDOW_START, periods=12, freq="MS")

# daily signals: (table, column, label, unit, decimals, meaningful change, change is % of baseline?)
SIGNALS = {
    "sbp": ("vitals_daily", "systolic_bp", "Home blood pressure (top)", "mmHg", 0, 5, False),
    "dbp": ("vitals_daily", "diastolic_bp", "Home blood pressure (bottom)", "mmHg", 0, 3, False),
    "weight": ("vitals_daily", "weight_kg", "Weight", "kg", 1, 2, True),
    "spo2": ("vitals_daily", "spo2_pct", "Blood oxygen (SpO2)", "%", 1, 1, False),
    "rr": ("vitals_daily", "respiratory_rate", "Breathing rate", "breaths/min", 1, 1.5, False),
    "rhr": ("wearable_daily", "resting_hr", "Resting heart rate", "bpm", 0, 3, False),
    "hrv": ("wearable_daily", "hrv_ms", "Heart rate variability", "ms", 0, 4, False),
    "steps": ("wearable_daily", "steps", "Daily steps", "steps", 0, 15, True),
    "active": ("wearable_daily", "active_minutes", "Active minutes", "min/day", 0, 15, True),
    "sedentary": ("wearable_daily", "sedentary_hours", "Sedentary time", "h/day", 1, 1, False),
    "sleep": ("wearable_daily", "sleep_hours", "Sleep", "h/night", 1, .4, False),
    "stress": ("wearable_daily", "stress_score_1_10", "Stress score", "of 10", 1, .5, False),
}

# lab tests: meaningful change, and whether higher is the concerning direction
LABS = {
    "HbA1c": (.3, "up"), "Fasting glucose": (10, "up"), "LDL cholesterol": (15, "up"),
    "Total cholesterol": (20, "up"), "Triglycerides": (25, "up"), "HDL cholesterol": (5, "down"),
    "ALT": (10, "up"), "AST": (10, "up"), "Creatinine": (.2, "up"), "eGFR": (10, "down"),
    "Urine albumin/creatinine": (10, "up"), "TSH": (1.0, "up"), "Free T4": (.3, "down"),
    "Hemoglobin": (.8, "down"), "Ferritin": (15, "down"), "Vitamin D": (5, "down"),
    "Vitamin B12": (80, "down"), "Potassium": (.4, "up"), "Sodium": (3, "up"),
    "WBC": (2, "up"), "Platelets": (60, "up"),
}

# what each medicine is expected to influence (for event-response analysis)
MED_EFFECTS = {
    "Metformin": {"labs": ["HbA1c", "Fasting glucose"], "signals": ["weight"]},
    "Metformin XR": {"labs": ["HbA1c", "Fasting glucose"], "signals": ["weight"]},
    "Atorvastatin": {"labs": ["LDL cholesterol", "Total cholesterol", "Triglycerides"], "signals": []},
    "Amlodipine": {"labs": [], "signals": ["sbp", "dbp"]},
    "Levothyroxine": {"labs": ["TSH", "Free T4"], "signals": ["weight", "rhr"]},
    "Ferrous sulfate": {"labs": ["Hemoglobin", "Ferritin"], "signals": [], "symptoms": ["Fatigue", "Dizziness"]},
    "Cholecalciferol": {"labs": ["Vitamin D"], "signals": []},
    "Vitamin D3": {"labs": ["Vitamin D"], "signals": []},
    "Sumatriptan": {"labs": [], "signals": [], "symptoms": ["Migraine headache", "Headache", "Light sensitivity"]},
    "Pantoprazole": {"labs": [], "signals": [], "symptoms": ["Heartburn", "Acid reflux"]},
    "Budesonide/formoterol": {"labs": [], "signals": ["spo2"], "symptoms": ["Wheezing", "Shortness of breath"]},
}

GLYCEMIC = {"Borderline glycemic markers", "Prediabetes", "Type 2 diabetes"}


def parse_ref(ref: str):
    """'70–99' -> (70, 99); '>40' -> (40, None); '<5.7' -> (None, 5.7)."""
    if not isinstance(ref, str):
        return None, None
    s = ref.replace("–", "-").replace("—", "-").replace(" ", "")
    m = re.match(r"^([0-9.]+)-([0-9.]+)$", s)
    if m:
        return float(m.group(1)), float(m.group(2))
    m = re.match(r"^(>=|>|≥)([0-9.]+)$", s)
    if m:
        return float(m.group(2)), None
    m = re.match(r"^(<=|<|≤)([0-9.]+)$", s)
    if m:
        return None, float(m.group(2))
    return None, None


def pearson_p(r: float, n: int) -> float:
    """Two-sided p-value for a Pearson correlation (t distribution, normal approx for large n)."""
    if n < 4 or abs(r) >= 1:
        return 0.0 if abs(r) >= 1 else 1.0
    t = r * math.sqrt((n - 2) / (1 - r * r))
    from scipy import stats
    return float(2 * stats.t.sf(abs(t), n - 2))


def load_tables(db_path: str) -> dict[str, pd.DataFrame]:
    con = sqlite3.connect(db_path)
    T = {}
    for name in ["patients", "medical_history", "medications", "labs", "vitals_daily", "wearable_daily",
                 "habits_weekly", "symptoms", "encounters", "adherence", "cycles", "data_issues"]:
        T[name] = pd.read_sql(f"select * from {name}", con)
    con.close()
    for name, cols in {"medical_history": ["date"], "medications": ["start_date", "end_date"], "labs": ["date"],
                       "vitals_daily": ["date"], "wearable_daily": ["date"], "habits_weekly": ["week_start"],
                       "symptoms": ["date"], "encounters": ["date"], "adherence": ["month"], "cycles": ["start_date"]}.items():
        for c in cols:
            T[name][c] = pd.to_datetime(T[name][c], errors="coerce")
    return T


def daily_frame(T) -> pd.DataFrame:
    v = T["vitals_daily"][["patient_id", "date", "systolic_bp", "diastolic_bp", "weight_kg", "spo2_pct", "respiratory_rate"]]
    w = T["wearable_daily"][["patient_id", "date", "resting_hr", "hrv_ms", "steps", "active_minutes",
                             "sedentary_hours", "sleep_hours", "stress_score_1_10"]]
    d = v.merge(w, on=["patient_id", "date"], how="outer")
    d = d.rename(columns={SIGNALS[k][1]: k for k in SIGNALS})
    return d.sort_values(["patient_id", "date"]).reset_index(drop=True)


def _round(x, nd=1):
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return None
    return round(float(x), nd)


def trend_of(series_daily: pd.Series, dates: pd.Series, key: str) -> dict:
    tab, col, label, unit, dec, tol, pct = SIGNALS[key]
    s = pd.Series(series_daily.values, index=pd.DatetimeIndex(dates))
    monthly = s.resample("MS").mean().reindex(MONTHS)
    base = s[s.index < MONTHS[3]].mean()
    recent = s[s.index >= MONTHS[9]].mean()
    tol_abs = abs(base) * tol / 100 if pct else tol
    diff = recent - base if pd.notna(base) and pd.notna(recent) else np.nan
    sustained = False
    if pd.notna(diff) and abs(diff) >= tol_abs:
        last3 = monthly.iloc[9:]
        sustained = int(((last3 - base) * np.sign(diff) >= tol_abs * .6).sum()) >= 2
    completeness = float(s.notna().mean())
    return {"key": key, "label": label, "unit": unit, "dec": dec,
            "monthly": [_round(x, dec + 1) for x in monthly.values],
            "baseline": _round(base, dec + 1), "recent": _round(recent, dec + 1),
            "change": _round(diff, dec + 1), "tol": _round(tol_abs, dec + 1),
            "direction": ("up" if diff > 0 else "down") if (pd.notna(diff) and abs(diff) >= tol_abs and sustained) else "stable",
            "completeness": round(completeness, 3)}


def lab_summary(L: pd.DataFrame, sex: str) -> dict:
    out = {}
    for test, g in L.groupby("test_name"):
        g = g.sort_values("date")
        vals = g["result"].values
        lo, hi = parse_ref(g["reference_range"].dropna().iloc[0] if g["reference_range"].notna().any() else None)
        n = len(vals)
        first = float(np.mean(vals[:2])) if n >= 4 else float(vals[0])
        last = float(np.mean(vals[-2:])) if n >= 4 else float(vals[-1])
        tol, worse = LABS.get(test, (None, "up"))
        change = last - first
        if tol is None or n < 2 or abs(change) < tol:
            direction = "stable"
        else:
            direction = "worse" if ((change > 0) == (worse == "up")) else "better"
        outside = lambda x: (lo is not None and x < lo) or (hi is not None and x > hi)
        out[test] = {"unit": g["unit"].iloc[0], "ref": g["reference_range"].iloc[0], "lo": lo, "hi": hi,
                     "points": [[d.strftime("%Y-%m-%d"), _round(v, 2)] for d, v in zip(g["date"], vals)],
                     "first": _round(first, 2), "last": _round(last, 2), "change": _round(change, 2),
                     "direction": direction, "last_outside": bool(outside(last)), "first_outside": bool(outside(first))}
    return out


def window_mean(s: pd.Series, dates: pd.Series, a, b):
    m = (dates >= a) & (dates < b)
    return float(s[m].mean()) if m.any() else np.nan


def med_responses(pid, M, L, D, S) -> list[dict]:
    out = []
    for _, m in M.iterrows():
        eff = MED_EFFECTS.get(m["medication"])
        start = m["start_date"]
        if eff is None or pd.isna(start):
            continue
        resp = {"medication": m["medication"], "dose": m.get("dose"), "start": start.strftime("%Y-%m-%d"),
                "indication": m.get("indication"), "status": m.get("status"),
                "tolerance": m.get("tolerance_per_adverse_effect"), "items": []}
        for test in eff.get("labs", []):
            g = L[L["test_name"] == test].sort_values("date")
            before = g[(g["date"] < start) & (g["date"] >= start - pd.Timedelta(days=150))]
            after = g[g["date"] >= start + pd.Timedelta(days=30)]
            if len(before) and len(after):
                b, a = float(before["result"].mean()), float(after["result"].tail(2).mean())
                resp["items"].append({"kind": "lab", "name": test, "unit": g["unit"].iloc[0],
                                      "before": _round(b, 2), "after": _round(a, 2), "change": _round(a - b, 2),
                                      "meaningful": abs(a - b) >= LABS.get(test, (0,))[0],
                                      "n_before": len(before), "n_after": len(after)})
        for key in eff.get("signals", []):
            if start - pd.Timedelta(days=45) < WINDOW_START or start + pd.Timedelta(days=90) > WINDOW_START + pd.Timedelta(days=365):
                continue
            b = window_mean(D[key], D["date"], start - pd.Timedelta(days=60), start)
            a = window_mean(D[key], D["date"], start + pd.Timedelta(days=30), start + pd.Timedelta(days=120))
            if pd.notna(a) and pd.notna(b):
                tab, col, label, unit, dec, tol, pct = SIGNALS[key]
                tol_abs = abs(b) * tol / 100 if pct else tol
                resp["items"].append({"kind": "signal", "name": label, "key": key, "unit": unit,
                                      "before": _round(b, dec + 1), "after": _round(a, dec + 1),
                                      "change": _round(a - b, dec + 1), "meaningful": abs(a - b) >= tol_abs})
        for sym in eff.get("symptoms", []):
            g = S[S["symptom"] == sym]
            b = int(((g["date"] < start) & (g["date"] >= start - pd.Timedelta(days=120))).sum())
            a = int(((g["date"] >= start) & (g["date"] < start + pd.Timedelta(days=120))).sum())
            if a or b:
                resp["items"].append({"kind": "symptom", "name": sym, "before": b, "after": a, "change": a - b,
                                      "meaningful": abs(a - b) >= 2, "unit": "reports in 4 months"})
        if resp["items"]:
            out.append(resp)
    return out


def relationships(D: pd.DataFrame) -> list[dict]:
    """Only relationships that are statistically clear for THIS patient (p < 0.001, |r| >= 0.2)."""
    cand = [("stress", "sleep", 0, "Stress score that day", "Sleep that night (h)"),
            ("sleep", "stress", 1, "Sleep the night before (h)", "Stress score next day"),
            ("steps", "sleep", 0, "Steps that day", "Sleep that night (h)"),
            ("sleep", "rhr", 1, "Sleep the night before (h)", "Resting heart rate (bpm)"),
            ("sleep", "hrv", 1, "Sleep the night before (h)", "HRV next day (ms)"),
            ("steps", "sbp", 1, "Steps the day before", "Blood pressure top (mmHg)"),
            ("stress", "sbp", 0, "Stress score that day", "Blood pressure top (mmHg)"),
            ("active", "hrv", 1, "Active minutes the day before", "HRV next day (ms)")]
    out = []
    for x, y, lag, xl, yl in cand:
        xs = D[x].shift(lag)
        ok = xs.notna() & D[y].notna()
        n = int(ok.sum())
        if n < 60:
            continue
        a, b = xs[ok].values.astype(float), D[y][ok].values.astype(float)
        if a.std() == 0 or b.std() == 0:
            continue
        r = float(np.corrcoef(a, b)[0, 1])
        p = pearson_p(r, n)
        if abs(r) >= .2 and p < .001:
            slope, icpt = np.polyfit(a, b, 1)
            idx = np.linspace(0, n - 1, min(n, 80)).astype(int)
            out.append({"x": x, "y": y, "lag": lag, "xl": xl, "yl": yl, "r": round(r, 2), "p": float(f"{p:.2g}"),
                        "n": n, "slope": round(float(slope), 4), "icpt": round(float(icpt), 3),
                        "pts": [[round(float(a[i]), 2), round(float(b[i]), 2)] for i in idx]})
    return out


def cycle_summary(C: pd.DataFrame):
    if C.empty or C["cycle_length"].notna().sum() == 0:
        return None
    L = C.sort_values("start_date")
    lens = L["cycle_length"].dropna().astype(float)
    return {"n": int(len(lens)), "mean": round(float(lens.mean()), 1), "sd": round(float(lens.std()), 1) if len(lens) > 1 else 0.0,
            "long": int((lens > 35).sum()), "short": int((lens < 21).sum()), "max": int(lens.max()),
            "cycles": [[d.strftime("%Y-%m-%d") if pd.notna(d) else None, int(l) if pd.notna(l) else None,
                        int(b) if pd.notna(b) else None, s] for d, l, b, s in
                       zip(L["start_date"], L["cycle_length"], L["bleeding_days"], L["symptoms"])]}


def bp_above_target(D: pd.DataFrame) -> dict:
    s = pd.Series(((D["sbp"] >= 130) | (D["dbp"] >= 80)).where(D["sbp"].notna() | D["dbp"].notna()).astype(float).values,
                  index=pd.DatetimeIndex(D["date"]))
    monthly = (s.resample("MS").mean().reindex(MONTHS) * 100)
    base = float(s[s.index < MONTHS[3]].mean() * 100)
    recent = float(s[s.index >= MONTHS[9]].mean() * 100)
    return {"monthly": [_round(x, 0) for x in monthly.values], "baseline": round(base), "recent": round(recent)}


def adherence_summary(A: pd.DataFrame, M: pd.DataFrame):
    if A.empty:
        return []
    names = M.drop_duplicates("medication_id", keep="last").set_index("medication_id")["medication"].to_dict()
    out = []
    for mid, g in A.groupby("medication_id"):
        mon = g.groupby("month")["estimated_adherence_pct"].mean().reindex(MONTHS)
        out.append({"medication_id": mid, "medication": names.get(mid, mid),
                    "mean": _round(g["estimated_adherence_pct"].mean(), 0),
                    "monthly": [_round(x, 0) for x in mon.values],
                    "months_below_80": int((mon < 80).sum()),
                    "missed": int(g["approx_missed_doses"].sum())})
    return out


# ------------------------- scenarios -------------------------
def _sig(t, key):
    return t.get(key) or {}


def scenario_metabolic(p, hist, labs, tr, meds, resp, sym):
    ctx = []
    for f in hist:
        if f["finding"] in GLYCEMIC:
            ctx.append({"kind": "history", "text": f["finding"], "date": f["date"]})
    a1 = labs.get("HbA1c")
    if a1 and a1["last"] is not None and a1["last"] >= 5.7:
        ctx.append({"kind": "lab", "text": f"Recent HbA1c {a1['last']}% (5.7% or higher)", "date": a1["points"][-1][0]})
    if "diabetes" in str(p.get("family_history", "")).lower():
        ctx.append({"kind": "family", "text": p["family_history"], "date": None})
    if not any(c["kind"] in ("history", "lab") for c in ctx):
        return None
    ev = []
    for t in ["HbA1c", "Fasting glucose", "Triglycerides", "HDL cholesterol", "ALT"]:
        if t in labs and labs[t]["direction"] != "stable":
            ev.append({"kind": "lab", "name": t, "dir": labs[t]["direction"], "from": labs[t]["first"], "to": labs[t]["last"], "unit": labs[t]["unit"]})
    for k, worse in [("weight", "up"), ("steps", "down"), ("active", "down"), ("sleep", "down"), ("sedentary", "up")]:
        s = _sig(tr, k)
        if s.get("direction") in ("up", "down"):
            ev.append({"kind": "signal", "name": s["label"], "key": k, "dir": "worse" if s["direction"] == worse else "better",
                       "from": s["baseline"], "to": s["recent"], "unit": s["unit"]})
    if "Triglycerides" in labs and "HDL cholesterol" in labs and labs["HDL cholesterol"]["last"]:
        ratio = labs["Triglycerides"]["last"] / labs["HDL cholesterol"]["last"]
        if ratio >= 3:
            ev.append({"kind": "marker", "name": "Triglyceride/HDL ratio", "dir": "flag", "from": None, "to": round(ratio, 1), "unit": "",
                       "note": "A ratio of 3 or more (mg/dL) is often linked with insulin resistance in research."})
    for r in resp:
        if r["medication"].startswith("Metformin"):
            ev.append({"kind": "response", "name": r["medication"], "start": r["start"], "items": r["items"]})
    thirst = sum(1 for s in sym if s in ("Increased thirst", "Frequent urination"))
    if thirst >= 3:
        ev.append({"kind": "symptom", "name": "Thirst / frequent urination", "dir": "flag", "to": thirst, "unit": "reports"})
    return _score("metabolic", ctx, ev, labs, ["HbA1c", "Fasting glucose"])


def scenario_cardio(p, hist, labs, tr, meds, resp, bp, adh):
    ctx = []
    for f in hist:
        if f["finding"] in ("Hypertension", "Hyperlipidemia"):
            ctx.append({"kind": "history", "text": f["finding"], "date": f["date"]})
    sb, db = tr["sbp"]["baseline"] or 0, tr["dbp"]["baseline"] or 0
    if sb >= 130 or db >= 80:
        ctx.append({"kind": "signal", "text": f"Average home BP {round(sb)}/{round(db)} mmHg in the first 3 months (130/80 or higher)", "date": None})
    ldl = labs.get("LDL cholesterol")
    if ldl and ldl["first"] is not None and ldl["first"] >= 160:
        ctx.append({"kind": "lab", "text": f"LDL {ldl['first']} mg/dL at the start (160 or higher)", "date": ldl["points"][0][0]})
    fh = str(p.get("family_history", "")).lower()
    if "hypertension" in fh or "cardiovascular" in fh:
        ctx.append({"kind": "family", "text": p["family_history"], "date": None})
    if not any(c["kind"] in ("history", "lab", "signal") for c in ctx):
        return None
    ev = []
    for k, worse in [("sbp", "up"), ("dbp", "up"), ("rhr", "up"), ("hrv", "down"), ("steps", "down"), ("weight", "up"), ("stress", "up")]:
        s = _sig(tr, k)
        if s.get("direction") in ("up", "down"):
            ev.append({"kind": "signal", "name": s["label"], "key": k, "dir": "worse" if s["direction"] == worse else "better",
                       "from": s["baseline"], "to": s["recent"], "unit": s["unit"]})
    if abs(bp["recent"] - bp["baseline"]) >= 10:
        ev.append({"kind": "signal", "name": "Days with BP at or above 130/80", "key": "bp_target",
                   "dir": "worse" if bp["recent"] > bp["baseline"] else "better", "from": bp["baseline"], "to": bp["recent"], "unit": "% of days"})
    for t in ["LDL cholesterol", "Total cholesterol", "Triglycerides", "HDL cholesterol", "Urine albumin/creatinine", "eGFR"]:
        if t in labs and labs[t]["direction"] != "stable":
            ev.append({"kind": "lab", "name": t, "dir": labs[t]["direction"], "from": labs[t]["first"], "to": labs[t]["last"], "unit": labs[t]["unit"]})
    for r in resp:
        if r["medication"] in ("Amlodipine", "Atorvastatin"):
            ev.append({"kind": "response", "name": r["medication"], "start": r["start"], "items": r["items"]})
    for a in adh:
        if a["medication"] in ("Amlodipine", "Atorvastatin") and a["mean"] is not None and a["mean"] < 80:
            ev.append({"kind": "adherence", "name": f"{a['medication']} taken", "dir": "worse", "to": a["mean"], "unit": "% (estimated)"})
    return _score("cardio", ctx, ev, labs, ["LDL cholesterol"], bp=bp)


def scenario_pcos(p, hist, labs, tr, cyc, sym):
    if p.get("sex") != "Female":
        return None
    ctx = []
    for f in hist:
        if f["finding"] == "PCOS":
            ctx.append({"kind": "history", "text": "PCOS", "date": f["date"]})
    if cyc and (cyc["mean"] > 35 or cyc["long"] >= 2):
        ctx.append({"kind": "cycle", "text": f"Average cycle {cyc['mean']} days; {cyc['long']} cycles longer than 35 days", "date": None})
    if sum(1 for s in sym if s == "Irregular cycle"):
        ctx.append({"kind": "symptom", "text": "Irregular cycle reported", "date": None})
    if not ctx:
        return None
    ev = []
    if cyc:
        ev.append({"kind": "cycle", "name": "Cycle length", "dir": "flag" if cyc["mean"] > 35 else "stable", "to": cyc["mean"],
                   "sd": cyc["sd"], "long": cyc["long"], "n": cyc["n"], "unit": "days (typical 21–35)"})
    for k, worse in [("weight", "up"), ("sleep", "down"), ("stress", "up"), ("steps", "down")]:
        s = _sig(tr, k)
        if s.get("direction") in ("up", "down"):
            ev.append({"kind": "signal", "name": s["label"], "key": k, "dir": "worse" if s["direction"] == worse else "better",
                       "from": s["baseline"], "to": s["recent"], "unit": s["unit"]})
    for t in ["HbA1c", "Fasting glucose", "Triglycerides", "HDL cholesterol"]:
        if t in labs and (labs[t]["last_outside"] or labs[t]["direction"] != "stable"):
            ev.append({"kind": "lab", "name": t, "dir": labs[t]["direction"] if labs[t]["direction"] != "stable" else "flag",
                       "from": labs[t]["first"], "to": labs[t]["last"], "unit": labs[t]["unit"],
                       "note": "Metabolic markers are relevant in PCOS because insulin resistance is common."})
    return _score("pcos", ctx, ev, labs, [])


def _score(sid, ctx, ev, labs, key_labs, bp=None):
    worse = sum(1 for e in ev if e.get("dir") in ("worse",))
    better = sum(1 for e in ev if e.get("dir") == "better")
    for r in [e for e in ev if e["kind"] == "response"]:
        for it in r["items"]:
            if it.get("meaningful") and it["kind"] in ("lab", "signal"):
                tol, w = LABS.get(it["name"], (0, "up"))
                key = it.get("key")
                if key:
                    w = {"sbp": "up", "dbp": "up", "weight": "up", "rhr": "up", "spo2": "down"}.get(key, "up")
                if (it["change"] < 0) == (w == "up"):
                    better += 1
                else:
                    worse += 1
    above = [t for t in key_labs if t in labs and labs[t]["last_outside"]]
    if bp is not None and bp["recent"] >= 50:
        above.append("home blood pressure")
    flags = sum(1 for e in ev if e.get("dir") == "flag")
    if worse >= 2 and worse > better:
        status = "worsening"
    elif better >= 2 and better > worse and not above:
        status = "improving"
    elif worse and better:
        status = "mixed"
    elif better >= 1 and above:
        status = "improving_above_target"
    elif better >= 2:
        status = "improving"
    elif above or flags or worse:
        status = "needs_review"
    else:
        status = "stable"
    return {"id": sid, "context": ctx, "evidence": ev, "worse": worse, "better": better,
            "above_target": above, "status": status}


def analyse_all(T) -> tuple[list[dict], pd.DataFrame]:
    D_all = daily_frame(T)
    P = T["patients"].set_index("patient_id")
    groups = {k: dict(tuple(v.groupby("patient_id"))) for k, v in
              [("hist", T["medical_history"]), ("meds", T["medications"]), ("labs", T["labs"]), ("sym", T["symptoms"]),
               ("adh", T["adherence"]), ("cyc", T["cycles"]), ("enc", T["encounters"]), ("hab", T["habits_weekly"]),
               ("daily", D_all), ("iss", T["data_issues"])]}
    empty = lambda k: pd.DataFrame(columns=T[{"hist": "medical_history", "meds": "medications", "labs": "labs", "sym": "symptoms",
                                               "adh": "adherence", "cyc": "cycles", "enc": "encounters", "hab": "habits_weekly",
                                               "iss": "data_issues"}[k]].columns)
    results, rows = [], []
    for pid in P.index:
        g = {k: groups[k].get(pid, empty(k) if k != "daily" else None) for k in groups}
        p = P.loc[pid].to_dict()
        p["patient_id"] = pid
        D = g["daily"].reset_index(drop=True)
        tr = {k: trend_of(D[k], D["date"], k) for k in SIGNALS}
        bp = bp_above_target(D)
        labs = lab_summary(g["labs"], p.get("sex"))
        hist = [{"date": d.strftime("%Y-%m-%d") if pd.notna(d) else None, "type": t, "finding": f, "status": s, "notes": n}
                for d, t, f, s, n in g["hist"][["date", "encounter_per_type", "finding_per_event", "status", "notes"]].itertuples(index=False)]
        meds = [{"medication": r["medication"], "dose": r["dose"], "frequency": r["frequency"],
                 "start": r["start_date"].strftime("%Y-%m-%d") if pd.notna(r["start_date"]) else None,
                 "end": r["end_date"].strftime("%Y-%m-%d") if pd.notna(r["end_date"]) else None,
                 "status": r["status"], "indication": r["indication"], "tolerance": r["tolerance_per_adverse_effect"],
                 "rationale": r["change_rationale"]} for _, r in g["meds"].iterrows()]
        resp = med_responses(pid, g["meds"], g["labs"], D, g["sym"])
        adh = adherence_summary(g["adh"], g["meds"])
        cyc = cycle_summary(g["cyc"]) if p.get("sex") == "Female" else None
        sym_list = list(g["sym"]["symptom"])
        rel = relationships(D)
        habits = {c: _round(g["hab"][c].mean(), 1) for c in ["water_l_per_day", "fruit_per_veg_servings_per_day",
                  "exercise_sessions_per_week", "caffeine_cups_per_day", "alcohol_drinks_per_week", "late_meals_per_week"]} if len(g["hab"]) else {}
        if len(g["hab"]):
            habits["smoking"] = g["hab"]["smoking"].mode().iloc[0]
            habits["stress_reported"] = g["hab"]["self_reported_stress"].mode().iloc[0]
        sc = {
            "metabolic": scenario_metabolic(p, hist, labs, tr, meds, resp, sym_list),
            "cardio": scenario_cardio(p, hist, labs, tr, meds, resp, bp, adh),
            "pcos": scenario_pcos(p, hist, labs, tr, cyc, sym_list),
        }
        completeness = float(np.mean([tr[k]["completeness"] for k in ("sbp", "weight", "rhr", "steps", "sleep", "hrv")]))
        res = {"id": pid, "age": int(p["age"]), "sex": p["sex"], "height": p.get("height_cm"), "blood_group": p.get("blood_group"),
               "allergies": p.get("allergies"), "family": p.get("family_history"), "history": hist, "meds": meds,
               "responses": resp, "adherence": adh, "labs": labs, "trends": tr, "bp_target": bp, "cycles": cyc,
               "symptoms": [[d.strftime("%Y-%m-%d"), s, sev] for d, s, sev in g["sym"][["date", "symptom", "severity"]].itertuples(index=False) if pd.notna(d)],
               "relationships": rel, "habits": habits, "scenarios": sc, "completeness": round(completeness, 3),
               "issues": g["iss"][["sheet", "issue", "detail", "count"]].to_dict("records")}
        results.append(res)
        rows.append({"patient_id": pid, "age": res["age"], "sex": res["sex"], "completeness": res["completeness"],
                     **{f"{k}_status": (v["status"] if v else None) for k, v in sc.items()},
                     "n_relationships": len(rel), "n_responses": len(resp)})
    return results, pd.DataFrame(rows)
