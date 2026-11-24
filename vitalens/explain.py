"""Plain-words AI explanation for one patient (Rishi, COMP 8967 Group 1).

What it does
  1. Builds a small evidence summary from the patient's results (same shape as buildEvidence()
     in web/explain.js, so the web page and this backend talk about the same facts).
  2. Asks Claude to rewrite that evidence in everyday words. The AI only sees the evidence summary.
  3. Checks the answer before anyone sees it:
       - every number must be in the evidence (the AI is not allowed to change or invent numbers)
       - no diagnosis words and no "change your dose" advice
       - the disclaimer is added by this code, not by the AI, so it cannot be dropped
  4. If the answer fails a check, it asks again (up to MAX_TRIES). If it still fails, it falls
     back to the rule-based text built straight from the evidence.

Run it from the repo root:
    python -m vitalens.explain PC0989 PC0006 PC0560 --no-llm        # no key needed, rule-based text
    python -m vitalens.explain PC0989 PC0006 PC0560 --out docs/ai-explanations-sample.md

The API key is read from the ANTHROPIC_API_KEY environment variable. Never put it in a file in the repo.
FastAPI: mount make_router() to serve GET /patients/{id}/explanation (contract in docs/ai-explanation-panel.md).
"""
from __future__ import annotations

import argparse
import functools
import json
import math
import os
import re
import sys
from pathlib import Path

WEB_DATA = Path(__file__).resolve().parent.parent / "web" / "data"
MODEL = os.environ.get("VITALENS_MODEL", "claude-sonnet-5-5")
MAX_TRIES = 3

DISCLAIMER = "This is not a diagnosis. Please talk with your doctor or care team about these results."
INTRO = "Here is what changed in your health data. We compared your last 3 months with your first 3 months."
# numbers that may appear even though they are not patient values: comparison window, cycle range, BP line
STRUCTURAL_NUMBERS = [3, 12, 21, 35, 130, 80]

# plain name first, medical word in brackets so patients can match it to their lab report
PLAIN = {
    "weight": "weight", "steps": "daily steps", "active": "active minutes each day", "sedentary": "time spent sitting",
    "sleep": "sleep each night", "stress": "stress score", "rhr": "heart rate at rest", "hrv": "heart rhythm score (HRV)",
    "sbp": "top blood pressure number", "dbp": "bottom blood pressure number", "spo2": "oxygen level (SpO2)",
    "rr": "breathing rate", "bpdays": "share of days with blood pressure of 130/80 or higher",
    "HbA1c": "average blood sugar (HbA1c)", "Fasting glucose": "blood sugar before eating (fasting glucose)",
    "LDL cholesterol": "bad cholesterol (LDL)", "HDL cholesterol": "good cholesterol (HDL)",
    "Total cholesterol": "total cholesterol", "Triglycerides": "blood fat level (triglycerides)",
    "Triglyceride/HDL ratio": "blood fat balance (triglyceride to HDL ratio)", "eGFR": "kidney filter score (eGFR)",
    "Creatinine": "kidney waste level (creatinine)", "Urine albumin/creatinine": "protein in urine (albumin)",
    "ALT": "liver test (ALT)", "AST": "liver test (AST)", "TSH": "thyroid test (TSH)",
    "Free T4": "thyroid hormone (free T4)", "Vitamin D": "vitamin D", "Vitamin B12": "vitamin B12",
    "Hemoglobin": "iron in red blood cells (hemoglobin)", "Ferritin": "iron stores (ferritin)",
    "Potassium": "potassium", "Sodium": "salt level (sodium)",
}
SIGNAL_BY_NAME = {
    "Weight": "weight", "Daily steps": "steps", "Active minutes": "active", "Sedentary time": "sedentary",
    "Sleep": "sleep", "Stress score": "stress", "Resting heart rate": "rhr", "Heart rate variability": "hrv",
    "Home blood pressure (top)": "sbp", "Home blood pressure (bottom)": "dbp", "Blood oxygen (SpO2)": "spo2",
    "Breathing rate": "rr", "Days with BP at or above 130/80": "bpdays",
}
AREA = {"metabolic": "Blood sugar and weight", "cardio": "Heart and blood pressure", "pcos": "Monthly cycle"}
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September",
          "October", "November", "December"]


# ---------------------------------------------------------------- 1. load + evidence
@functools.lru_cache(maxsize=16)
def _read_chunk(path: Path) -> list:
    return json.loads(path.read_text(encoding="utf-8"))


def load_patient(pid: str, web_data: Path = WEB_DATA) -> dict:
    """Patients are stored 100 per chunk file: PC0989 is in PC0901.json."""
    n = int(pid.upper().replace("PC", ""))
    chunk = web_data / "chunks" / f"PC{((n - 1) // 100) * 100 + 1:04d}.json"
    for p in _read_chunk(chunk):
        if p["id"] == pid.upper():
            return p
    raise KeyError(f"{pid} not found in {chunk.name}")


def _half_up(v: float, decimals: int = 0):
    """Round .5 upwards like JavaScript's Math.round (Python's round() goes to the even number: 104.5 -> 104)."""
    f = 10 ** decimals
    r = math.floor(v * f + 0.5) / f
    return int(r) if decimals == 0 else r


def _round_for(e: dict, v):
    if v is None:
        return None
    u = e.get("unit") or ""
    if abs(v) >= 100 or u in ("steps", "min/day", "ms", "bpm") or u.startswith("% of days"):
        return _half_up(v)
    return _half_up(v, 1)


def _plain_of(e: dict) -> str:
    if e["kind"] == "signal":
        return PLAIN.get(e.get("key") or SIGNAL_BY_NAME.get(e["name"], ""), e["name"].lower())
    return PLAIN.get(e["name"], e["name"])


def build_evidence(p: dict) -> dict:
    """The ONLY facts the AI may state. Mirrors buildEvidence() in web/explain.js."""
    areas = []
    for sid, sc in (p.get("scenarios") or {}).items():
        if not sc:
            continue
        items = []
        for e in sc.get("evidence", []):
            if e["kind"] == "response":
                it = next((i for i in e.get("items", []) if i["kind"] != "symptom"
                           and i.get("before") is not None and i.get("after") is not None), None)
                items.append({
                    "kind": "response", "medicine": e["name"], "start": e.get("start"),
                    "measure": (PLAIN.get(it["name"]) or PLAIN.get(SIGNAL_BY_NAME.get(it["name"], "")) or it["name"]) if it else None,
                    "from": _round_for(it, it["before"]) if it else None,
                    "to": _round_for(it, it["after"]) if it else None,
                    "unit": it.get("unit") if it else None,
                    "meaningful": bool(it and it.get("meaningful")),
                })
            elif e["kind"] == "cycle":
                items.append({"kind": "cycle", "measure": "monthly cycle length", "to": e.get("to"),
                              "long": e.get("long"), "n": e.get("n"), "dir": e.get("dir")})
            else:
                items.append({"kind": e["kind"], "name": e["name"], "measure": _plain_of(e),
                              "from": _round_for(e, e.get("from")), "to": _round_for(e, e.get("to")),
                              "unit": e.get("unit"), "dir": e.get("dir") or "stable"})
        areas.append({"id": sid, "area": AREA.get(sid, sid), "status": sc.get("status"),
                      "above_target": [PLAIN.get(n, n) for n in sc.get("above_target", [])], "items": items})
    return {"patient": p["id"], "window": "first 3 months (Sep-Nov 2025) vs last 3 months (Jun-Aug 2026)", "areas": areas}


# ---------------------------------------------------------------- 2. safety checks
BLOCKED = [
    "diagnos", "diabetes", "diabetic", "prediabet", "hypertension", "hypertensive", "pcos", "polycystic",
    "disease", "disorder", "syndrome", "cancer", "tumou?r", "insulin resistance", "obese", "obesity",
    r"you have [a-z ]{0,20}(condition|illness)", "stop taking", "start taking", "increase your dose",
    "reduce your dose", "lower your dose", "change your dose", r"skip (a |your )?dose",
]
NUM_RE = re.compile(r"(?<![A-Za-z\d.])\d{1,3}(?:,\d{3})+(?:\.\d+)?(?![A-Za-z\d])|(?<![A-Za-z\d.])\d+(?:\.\d+)?(?![A-Za-z\d])")


def _norm(x: float) -> str:
    """'6.50' and '6.5' and '6' compare as the same number text, like Number() in JavaScript."""
    return str(int(x)) if float(x) == int(x) else repr(float(x))


def allowed_numbers(ev: dict) -> set[str]:
    ok = {_norm(n) for n in STRUCTURAL_NUMBERS}

    def add(v):
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            return
        for d in (0, 1, 2):
            ok.add(_norm(_half_up(v, d)))

    def walk(o):
        if o is None:
            return
        if isinstance(o, (int, float)) and not isinstance(o, bool):
            return add(o)
        if isinstance(o, str):
            m = re.match(r"^(\d{4})-(\d{2})(?:-(\d{2}))?$", o)
            if m:  # a date: the year and the day may be written out
                add(int(m.group(1)))
                add(int(m.group(3) or 1))
                return
            for n in re.findall(r"\d+(?:\.\d+)?", o):
                add(float(n))
            return
        if isinstance(o, list):
            return [walk(i) for i in o]
        if isinstance(o, dict):
            for v in o.values():
                walk(v)
            if isinstance(o.get("from"), (int, float)) and isinstance(o.get("to"), (int, float)):
                add(abs(o["to"] - o["from"]))  # a plain "went up by X" is allowed

    walk(ev["areas"])
    return ok


def numbers_in(text: str) -> list[str]:
    return [_norm(float(s.replace(",", ""))) for s in NUM_RE.findall(text)]


def safety_check(text: str, ev: dict) -> dict:
    allowed = allowed_numbers(ev)
    nums = numbers_in(text)
    unknown = sorted({n for n in nums if n not in allowed})
    lower = re.sub(r"(this is )?not a diagnosis", " ", text.lower())  # the disclaimer itself says it
    blocked = []
    for w in BLOCKED:
        m = re.search(rf"\b{w}[a-z]*", lower, re.I)
        if m:
            blocked.append(m.group(0))
    has_disclaimer = bool(re.search(r"not a diagnosis", text, re.I) and re.search(r"(doctor|care team)", text, re.I))
    checks = [
        {"id": "numbers", "label": "Numbers match the evidence", "pass": not unknown,
         "detail": f"Not in the evidence: {', '.join(unknown)}" if unknown else f"{len(nums)} numbers checked"},
        {"id": "words", "label": "No diagnosis or medicine-change words", "pass": not blocked,
         "detail": f"Found: {', '.join(sorted(set(blocked)))}" if blocked else "None found"},
        {"id": "disclaimer", "label": "Says it is not a diagnosis", "pass": has_disclaimer,
         "detail": "Disclaimer present" if has_disclaimer else "Disclaimer missing"},
    ]
    return {"pass": all(c["pass"] for c in checks), "checks": checks}


# ---------------------------------------------------------------- 3a. rule-based text (fallback)
def _fmt(v):
    if v is None:
        return ""
    if abs(v) >= 1000:
        return f"{round(v):,}"
    return str(int(v)) if float(v) == int(v) else str(v)


UNIT_WORD = {"%": "%", "kg": " kg", "steps": " steps", "min/day": " minutes", "h/night": " hours",
             "% of days": "%", "% (estimated)": "%", "bpm": " beats a minute", "of 10": " out of 10"}


def _month_year(iso):
    if not iso:
        return ""
    y, m = iso.split("-")[:2]
    return f"{MONTHS[int(m) - 1]} {y}"


def _sentence(it: dict):
    u = UNIT_WORD.get(it.get("unit"), "")
    k = it["kind"]
    if k in ("signal", "lab", "marker"):
        if it["from"] is None or it["to"] is None:
            return None
        move = "went up" if it["to"] > it["from"] else "went down" if it["to"] < it["from"] else "stayed the same"
        tail = " This is a good sign." if it.get("dir") == "better" else ""
        return f"Your {it['measure']} {move} from {_fmt(it['from'])}{u} to {_fmt(it['to'])}{u}.{tail}"
    if k == "response":
        when = _month_year(it["start"])
        if not it["measure"]:
            return f"You started {it['medicine']} in {when}."
        if not it["meaningful"]:
            return f"After you started {it['medicine']} in {when}, your {it['measure']} stayed about the same."
        return (f"After you started {it['medicine']} in {when}, your {it['measure']} went from "
                f"{_fmt(it['from'])} to {_fmt(it['to'])}{UNIT_WORD.get(it['unit'], '')}.")
    if k == "symptom":
        return f"You told us about feeling very thirsty or needing the bathroom often {it['to']} times this year."
    if k == "adherence":
        return f"You took {re.sub(r' taken$', '', it['name'])} about {_fmt(it['to'])}% of the time."
    if k == "cycle":
        return (f"Your monthly cycle was {it['to']} days long on average. A usual cycle is 21 to 35 days. "
                f"{it['long']} of your {it['n']} cycles were longer than 35 days.")
    return None


def rule_based(ev: dict) -> dict:
    rank = {"worse": 0, "flag": 1, "better": 2, "stable": 3}
    sections = []
    if not ev["areas"]:
        sections.append({"area": "Your year in numbers", "sentences": ["We did not find any big changes in your health data."]})
    for a in ev["areas"]:
        items = sorted(a["items"], key=lambda i: rank.get(i.get("dir"), 2))
        sents = [s for s in map(_sentence, items) if s][:4]
        if any(i.get("dir") == "worse" for i in items[:4]):
            sents.append("The changes that went the wrong way are worth a closer look with your care team.")
        if a["above_target"]:
            names = " and ".join(a["above_target"][:2])
            sents.append(f"Your {names} {'are' if len(a['above_target']) > 1 else 'is'} still above the healthy range.")
        sections.append({"area": a["area"], "sentences": sents or ["We did not find any big changes here."]})
    return {"model": "VitaLens rule-based text (no AI)", "intro": INTRO, "sections": sections, "disclaimer": DISCLAIMER}


def explanation_text(x: dict) -> str:
    return " ".join(filter(None, [x.get("intro"), *[s for sec in x["sections"] for s in sec["sentences"]], x.get("disclaimer")]))


# ---------------------------------------------------------------- 3b. ask Claude
SYSTEM_PROMPT = f"""You explain one patient's health results in simple words for the patient.
You are given an EVIDENCE summary as JSON. It is the only information you may use.

Hard rules:
1. Use numbers exactly as written in the evidence. Never round them again, never add, subtract or estimate,
   never write a number that is not in the evidence. You may say a value went up or down.
2. Never give a diagnosis and never name a condition (no diabetes, prediabetes, hypertension, PCOS, disease, syndrome).
   Do not say what the results "mean" for the patient's health condition.
3. Never tell the patient to start, stop or change a medicine or a dose. You may say a medicine was started
   and how the measure changed afterwards, as in the evidence. Do not say the medicine caused the change.
4. If something went the wrong way, say it is worth talking about with their doctor or care team. Do not scare.
5. Use the "measure" wording from the evidence (plain name first, medical word in brackets).
6. Short sentences, 20 words or fewer, everyday words, about a grade 6 reading level.
7. Do not add a disclaimer; it is added for you.

Reply with JSON only, no other text, in this shape:
{{"sections": [{{"area": "<area name from the evidence>", "sentences": ["...", "..."]}}]}}
Use one section per area in the evidence, with at most 4 sentences each. If the evidence has no areas, return one
section with the area "Your year in numbers" and one sentence saying no big changes were found.
"""


def ask_claude(ev: dict, feedback: str | None = None) -> dict:
    import anthropic  # imported here so the rest of the module works without the package

    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from the environment
    content = "EVIDENCE:\n" + json.dumps(ev, indent=1)
    if feedback:
        content += f"\n\nYour previous answer was rejected: {feedback}\nWrite it again and fix this."
    msg = client.messages.create(model=MODEL, max_tokens=1200, temperature=0, system=SYSTEM_PROMPT,
                                 messages=[{"role": "user", "content": content}])
    raw = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip())
    data = json.loads(raw)
    sections = [{"area": str(s.get("area", "")), "sentences": [str(x) for x in s.get("sentences", [])]}
                for s in data["sections"]]
    return {"model": MODEL, "intro": INTRO, "sections": sections, "disclaimer": DISCLAIMER}


def explain_patient(pid: str, use_llm: bool = True, web_data: Path = WEB_DATA) -> dict:
    """Returns the API response for GET /patients/{id}/explanation (see docs/ai-explanation-panel.md)."""
    ev = build_evidence(load_patient(pid, web_data))
    tries, feedback, x, safety = [], None, None, None
    if use_llm:
        for attempt in range(1, MAX_TRIES + 1):
            try:
                x = ask_claude(ev, feedback)
            except Exception as err:  # no key, network down, bad JSON: use the rule-based text
                tries.append({"attempt": attempt, "error": f"{type(err).__name__}: {err}"[:200]})
                x = None
                break
            safety = safety_check(explanation_text(x), ev)
            tries.append({"attempt": attempt, "pass": safety["pass"],
                          "failed": [c["detail"] for c in safety["checks"] if not c["pass"]]})
            if safety["pass"]:
                break
            feedback = "; ".join(c["detail"] for c in safety["checks"] if not c["pass"])
            x = None
    if x is None:  # AI off, failed, or never passed the checks: numbers come straight from the evidence
        x = rule_based(ev)
        safety = safety_check(explanation_text(x), ev)
    return {**x, "patient": ev["patient"], "safety": safety, "attempts": tries, "evidence": ev}


# ---------------------------------------------------------------- 4. FastAPI hook (Kamran mounts this)
def make_router():
    from fastapi import APIRouter, HTTPException

    router = APIRouter()

    @router.get("/patients/{pid}/explanation")
    def explanation(pid: str):
        try:
            out = explain_patient(pid)
        except (KeyError, ValueError, FileNotFoundError):
            raise HTTPException(status_code=404, detail=f"Patient {pid} not found")
        return {k: out[k] for k in ("model", "intro", "sections", "disclaimer", "safety")}

    return router


# ---------------------------------------------------------------- 5. command line
def main(argv=None):
    ap = argparse.ArgumentParser(description="Explain patient results in plain words")
    ap.add_argument("ids", nargs="+", help="patient ids, e.g. PC0989 PC0006 PC0560")
    ap.add_argument("--no-llm", action="store_true", help="use the rule-based text, no API call")
    ap.add_argument("--out", help="write a markdown file with the explanations")
    args = ap.parse_args(argv)

    lines = ["# AI explanations: sample output", "",
             "Made by `python -m vitalens.explain`. Evidence comes from `web/data`; every answer went through the safety checks "
             "(numbers match the evidence, no diagnosis or dose words, disclaimer present).", ""]
    for pid in args.ids:
        out = explain_patient(pid, use_llm=not args.no_llm)
        s = out["safety"]
        print(f"{pid}: {out['model']} | safety {'PASS' if s['pass'] else 'FAIL'} | tries {out['attempts']}")
        lines += [f"## {pid}", f"Source: {out['model']} | Safety: {'PASS' if s['pass'] else 'FAIL'}", "", out["intro"], ""]
        for sec in out["sections"]:
            lines += [f"**{sec['area']}**"] + [f"- {t}" for t in sec["sentences"]] + [""]
        lines += [f"_{out['disclaimer']}_", "", "Checks: " + "; ".join(
            f"{'PASS' if c['pass'] else 'FAIL'} {c['label']} ({c['detail']})" for c in s["checks"]), ""]
    if args.out:
        Path(args.out).write_text("\n".join(lines), encoding="utf-8")
        print("wrote", args.out)


if __name__ == "__main__":
    sys.exit(main())
