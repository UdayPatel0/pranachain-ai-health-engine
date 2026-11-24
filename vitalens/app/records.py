"""What each viewer is allowed to see. Nothing outside these functions is ever sent to a shared link."""
from __future__ import annotations


def conditions(rec: dict) -> list[dict]:
    return [{"name": h["finding"], "since": h["date"], "status": h["status"]}
            for h in rec.get("history", []) if h.get("type") == "Clinical finding" and h.get("status") != "Resolved"]


def current_meds(rec: dict) -> list[dict]:
    seen, out = set(), []
    for m in rec.get("meds", []):
        if m.get("status") == "Active" and m["medication"] not in seen:
            seen.add(m["medication"])
            out.append({"name": m["medication"], "dose": m.get("dose"), "frequency": m.get("frequency"),
                        "for": m.get("indication"), "since": m.get("start")})
    return out


def emergency_card(rec: dict, profile: dict) -> dict:
    """Only what a stranger helping in an emergency needs."""
    return {
        "id": rec["id"], "age": rec["age"], "sex": rec["sex"],
        "blood_group": rec.get("blood_group"), "allergies": rec.get("allergies"),
        "conditions": conditions(rec), "medicines": current_meds(rec),
        "contact_name": profile.get("contact_name", ""), "contact_phone": profile.get("contact_phone", ""),
        "note": profile.get("note", ""),
    }


def doctor_view(rec: dict) -> dict:
    """A clinician summary: history, medicines and how they were taken, tests, trends, the year's findings."""
    adh = {a["medication"]: a for a in rec.get("adherence", [])}
    meds = [dict(m, adherence=adh.get(m["name"], {}).get("mean"),
                 months_below_80=adh.get(m["name"], {}).get("months_below_80")) for m in current_meds(rec)]
    return {
        "id": rec["id"], "age": rec["age"], "sex": rec["sex"], "height": rec.get("height"),
        "blood_group": rec.get("blood_group"), "allergies": rec.get("allergies"), "family": rec.get("family"),
        "history": rec.get("history", []), "medicines": meds, "responses": rec.get("responses", []),
        "labs": rec.get("labs", {}),
        "trends": {k: {x: v.get(x) for x in ("label", "unit", "monthly", "baseline", "recent", "dec")}
                   for k, v in rec.get("trends", {}).items()},
        "symptoms": rec.get("symptoms", []),
        "summary": rec.get("ai", {}).get("rule_text", ""),
        "scenarios": {k: ({"status": v.get("status"), "worse": v.get("worse"), "better": v.get("better"),
                           "above_target": v.get("above_target", [])} if v else None)
                      for k, v in rec.get("scenarios", {}).items()},
        "period": "September 2025 to August 2026",
    }
