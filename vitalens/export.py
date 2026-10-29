"""Export analysis results as compact JSON for the VitaLens web demo.

Writes:
  <out>/index.json            cohort summary + one light row per patient
  <out>/chunks/PC0001.json    full results for 100 patients per file
"""
from __future__ import annotations

import collections
import json
import math
import os

import numpy as np


def _clean(o):
    if isinstance(o, float):
        return None if (math.isnan(o) or math.isinf(o)) else o
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return _clean(float(o))
    if isinstance(o, dict):
        return {k: _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    return o


def cohort_summary(R, issues_df=None) -> dict:
    status = {s: collections.Counter() for s in ("metabolic", "cardio", "pcos")}
    for x in R:
        for s, v in x["scenarios"].items():
            status[s][v["status"] if v else "none"] += 1
    rel = collections.Counter((r["x"], r["y"]) for x in R for r in x["relationships"])
    rel_r = collections.defaultdict(list)
    for x in R:
        for r in x["relationships"]:
            rel_r[(r["x"], r["y"])].append(r["r"])
    resp = collections.defaultdict(list)
    for x in R:
        for m in x["responses"]:
            for it in m["items"]:
                if it["kind"] in ("lab", "signal", "symptom"):
                    resp[(m["medication"].replace(" XR", ""), it["name"], it.get("unit"))].append(it["change"])
    responses = [{"medication": k[0], "measure": k[1], "unit": k[2], "n": len(v),
                  "mean": round(float(np.mean(v)), 2), "median": round(float(np.median(v)), 2),
                  "share_down": round(float(np.mean(np.array(v) < 0)), 2)}
                 for k, v in resp.items() if len(v) >= 15]
    responses.sort(key=lambda r: (-r["n"]))
    hist = collections.Counter(f["finding"] for x in R for f in x["history"])
    featured = []
    def pick(sid, statuses, label):
        cands = [x for x in R if x["scenarios"][sid] and x["scenarios"][sid]["status"] in statuses]
        cands.sort(key=lambda x: (-len(x["scenarios"][sid]["evidence"]), -x["completeness"], x["id"]))
        if cands:
            featured.append({"id": cands[0]["id"], "scenario": sid, "status": cands[0]["scenarios"][sid]["status"], "label": label})
    pick("metabolic", ("worsening",), "Metabolic · worsening")
    pick("metabolic", ("improving",), "Metabolic · improving")
    pick("cardio", ("worsening",), "Cardiovascular · worsening")
    pick("cardio", ("mixed",), "Cardiovascular · mixed")
    pick("pcos", ("worsening", "mixed", "needs_review"), "PCOS · needs review")
    calm = [x for x in R if not any(x["scenarios"].values())]
    calm.sort(key=lambda x: (-x["completeness"], x["id"]))
    if calm:
        featured.append({"id": calm[0]["id"], "scenario": None, "status": "none", "label": "No scenario · control"})
    return {"patients": len(R),
            "sex": dict(collections.Counter(x["sex"] for x in R)),
            "age": {"min": min(x["age"] for x in R), "max": max(x["age"] for x in R),
                    "mean": round(float(np.mean([x["age"] for x in R])), 1)},
            "scenario_status": {k: dict(v) for k, v in status.items()},
            "relationships": [{"x": k[0], "y": k[1], "patients": n, "median_r": round(float(np.median(rel_r[k])), 2)}
                              for k, n in rel.most_common()],
            "responses": responses,
            "history": dict(hist.most_common()),
            "featured": featured,
            "completeness": {"mean": round(float(np.mean([x["completeness"] for x in R])), 3),
                             "min": round(float(min(x["completeness"] for x in R)), 3)}}


def export(R, out_dir: str, audit: dict | None = None, chunk: int = 100) -> dict:
    os.makedirs(os.path.join(out_dir, "chunks"), exist_ok=True)
    rows = []
    R = sorted(R, key=lambda x: x["id"])
    chunks = collections.defaultdict(list)
    for x in R:
        n = int(x["id"][2:])
        key = f"PC{((n - 1) // chunk) * chunk + 1:04d}"
        chunks[key].append(_clean(x))
        sc = x["scenarios"]
        rows.append([x["id"], x["age"], x["sex"][0], key,
                     (sc["metabolic"] or {}).get("status"), (sc["cardio"] or {}).get("status"), (sc["pcos"] or {}).get("status"),
                     x["completeness"]])
    for key, items in chunks.items():
        with open(os.path.join(out_dir, "chunks", f"{key}.json"), "w") as f:
            json.dump(items, f, separators=(",", ":"))
    index = {"summary": cohort_summary(R), "audit": audit or {},
             "columns": ["id", "age", "sex", "chunk", "metabolic", "cardio", "pcos", "completeness"], "rows": rows}
    with open(os.path.join(out_dir, "index.json"), "w") as f:
        json.dump(_clean(index), f, separators=(",", ":"))
    return {"chunks": len(chunks), "patients": len(R)}
