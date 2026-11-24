"""Loads the processed PranaChain patient records (data/chunks/*.json) into memory."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


@lru_cache(maxsize=1)
def patients() -> dict[str, dict]:
    out: dict[str, dict] = {}
    for f in sorted((DATA_DIR / "chunks").glob("*.json")):
        for rec in json.loads(f.read_text(encoding="utf-8")):
            out[rec["id"]] = rec
    if not out:
        raise RuntimeError(f"No patient data found in {DATA_DIR / 'chunks'}")
    return out


def get_patient(pid: str) -> dict | None:
    pid = pid.strip().upper()
    if pid.startswith("NP"):  # a new patient who signed up: built from their own results
        from . import newpatients, store
        prof = store.new_patient_profile(pid)
        return newpatients.build(pid, prof, store.list_results(pid)) if prof else None
    return patients().get(pid)


@lru_cache(maxsize=1)
def summary() -> dict:
    f = DATA_DIR / "index.json"
    return json.loads(f.read_text(encoding="utf-8")).get("summary", {}) if f.exists() else {}
