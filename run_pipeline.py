"""Run the full VitaLens pipeline.

    python run_pipeline.py --raw data/raw --db data/vitalens.db --out web/data

1. Load every PranaChain workbook into a SQLite database (with a data-issues table)
2. Analyse every patient: baselines, lab trajectories, medication responses,
   relationships and the three validation scenarios
3. Export compact JSON for the web demo, plus an audit summary
"""
import argparse
import json
import os
import sqlite3
import time

import pandas as pd

from vitalens.analysis import analyse_all, load_tables
from vitalens.export import export
from vitalens.loader import load_folder


def audit_summary(db_path: str) -> dict:
    con = sqlite3.connect(db_path)
    iss = pd.read_sql("select issue, detail, count(distinct patient_id) patients, sum(count) total "
                      "from data_issues group by issue, detail order by issue, patients desc", con)
    counts = {t: con.execute(f"select count(*) from {t}").fetchone()[0] for t in
              ["patients", "medical_history", "medications", "labs", "vitals_daily", "wearable_daily",
               "habits_weekly", "symptoms", "encounters", "adherence", "cycles"]}
    window = con.execute("select min(date), max(date) from vitals_daily").fetchone()
    con.close()
    return {"rows": counts, "window": list(window), "issues": iss.to_dict("records")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default="data/raw")
    ap.add_argument("--db", default="data/vitalens.db")
    ap.add_argument("--out", default="web/data")
    ap.add_argument("--skip-load", action="store_true", help="reuse an existing database")
    a = ap.parse_args()
    t = time.time()
    if not a.skip_load:
        load_folder(a.raw, a.db)
        print(f"[{time.time() - t:.0f}s] loaded")
    audit = audit_summary(a.db)
    T = load_tables(a.db)
    R, df = analyse_all(T)
    os.makedirs(a.out, exist_ok=True)
    df.to_csv(os.path.join(a.out, "patient_summary.csv"), index=False)
    print(f"[{time.time() - t:.0f}s] analysed {len(R)} patients")
    info = export(R, a.out, audit=audit)
    print(f"[{time.time() - t:.0f}s] exported {info['patients']} patients in {info['chunks']} files to {a.out}")
    with open(os.path.join(a.out, "audit.json"), "w") as f:
        json.dump(audit, f, indent=1, default=str)


if __name__ == "__main__":
    main()
