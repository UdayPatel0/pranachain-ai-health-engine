"""Load PranaChain patient workbooks into clean tables.

Each workbook has 11 sheets. This module turns every sheet into a tidy pandas
DataFrame with a `patient_id` column, real dates, numeric columns as numbers,
and a list of data-quality issues found along the way. Nothing is ever filled
in: missing values stay missing (NaN / NaT).

Usage:
    from vitalens.loader import read_workbook, load_folder
    tables, issues = read_workbook("PC0001.xlsx")
    load_folder("data/raw", "data/vitalens.db")
"""
from __future__ import annotations

import datetime as dt
import glob
import os
import sqlite3
from multiprocessing import Pool

import numpy as np
import pandas as pd

EXCEL_EPOCH = dt.datetime(1899, 12, 30)

# sheet name in the workbook -> (table name, date columns, numeric columns)
SHEETS = {
    "Medical History": ("medical_history", ["Date"], []),
    "Medication History": ("medications", ["Start Date", "End Date"], []),
    "Lab Results": ("labs", ["Date"], ["Result"]),
    "Vitals Daily": ("vitals_daily", ["Date"],
                     ["Systolic BP", "Diastolic BP", "Resting HR", "Weight kg", "BMI",
                      "SpO2 %", "Temp C", "Respiratory Rate"]),
    "Wearable Daily": ("wearable_daily", ["Date"],
                       ["Steps", "Sleep Hours", "Active Minutes", "Resting HR", "HRV ms",
                        "Calories kcal", "Sedentary Hours", "Stress Score 1-10"]),
    "Habits Weekly": ("habits_weekly", ["Week Start"],
                      ["Water L/day", "Fruit/Veg servings/day", "Exercise sessions/week",
                       "Caffeine cups/day", "Alcohol drinks/week", "Late meals/week"]),
    "Symptoms Timeline": ("symptoms", ["Date"], []),
    "Encounters & Notes": ("encounters", ["Date"], []),
    "Medication Adherence": ("adherence", ["Month"], ["Estimated Adherence %", "Approx Missed Doses"]),
    "Women Health": ("cycles", ["Start Date"], ["Cycle Length", "Bleeding Days"]),
}

# plausible physical limits: values outside are flagged (not removed)
LIMITS = {
    "Systolic BP": (70, 230), "Diastolic BP": (40, 140), "Resting HR": (30, 200),
    "Weight kg": (30, 250), "BMI": (12, 70), "SpO2 %": (70, 100), "Temp C": (34, 42),
    "Respiratory Rate": (6, 40), "Steps": (0, 60000), "Sleep Hours": (0, 16),
    "Active Minutes": (0, 600), "HRV ms": (5, 250), "Calories kcal": (500, 6000),
    "Sedentary Hours": (0, 24), "Stress Score 1-10": (1, 10),
}

UNIT_FIXES = {"10^9/L": "x10^9/L"}


def to_snake(name: str) -> str:
    out = name.lower()
    for a, b in [("%", "pct"), ("/", "_per_"), ("&", "and"), ("²", "2"), ("-", "_"), (" ", "_"), (".", "")]:
        out = out.replace(a, b)
    while "__" in out:
        out = out.replace("__", "_")
    return out.strip("_")


def parse_date(v):
    """Excel serial number, datetime, or ISO text -> pandas Timestamp (or NaT)."""
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return pd.NaT
    if isinstance(v, (int, float, np.integer, np.floating)):
        return pd.Timestamp(EXCEL_EPOCH + dt.timedelta(days=float(v)))
    if isinstance(v, (dt.datetime, dt.date, pd.Timestamp)):
        return pd.Timestamp(v)
    if isinstance(v, str):
        s = v.strip()
        if s in ("", "—", "-", "N/A", "NA"):
            return pd.NaT
        return pd.to_datetime(s, errors="coerce")
    return pd.NaT


def date_format_of(v) -> str:
    if isinstance(v, (int, float, np.integer, np.floating)):
        return "excel-number"
    if isinstance(v, (dt.datetime, dt.date, pd.Timestamp)):
        return "date"
    if isinstance(v, str):
        return "text"
    return "empty"


def read_workbook(path: str):
    """Return (tables, profile, issues) for one patient workbook."""
    raw = pd.read_excel(path, sheet_name=None, header=0, dtype=object, engine="openpyxl")
    issues: list[dict] = []
    fname = os.path.basename(path)

    prof_df = raw.get("Patient Profile")
    profile = {}
    if prof_df is not None:
        for _, r in prof_df.dropna(how="all").iterrows():
            profile[str(r.iloc[0]).strip()] = r.iloc[1]
    pid = str(profile.get("Patient ID") or os.path.splitext(fname)[0])
    if pid != os.path.splitext(fname)[0]:
        issues.append({"patient_id": pid, "sheet": "Patient Profile", "issue": "id_mismatch",
                       "detail": f"file {fname} contains {pid}", "count": 1})

    tables: dict[str, pd.DataFrame] = {}
    for sheet, (table, date_cols, num_cols) in SHEETS.items():
        if sheet not in raw:
            issues.append({"patient_id": pid, "sheet": sheet, "issue": "missing_sheet", "detail": "", "count": 1})
            continue
        df = raw[sheet].dropna(how="all").copy()
        # placeholder rows such as '—' (e.g. Women Health for men) mean "not applicable"
        first = df.columns[0]
        df = df[~df[first].astype(str).str.strip().isin(["—", "-", "N/A"])]
        for c in date_cols:
            if c in df:
                fmts = df[c].dropna().map(date_format_of).value_counts()
                for f, n in fmts.items():
                    if f != "date":
                        issues.append({"patient_id": pid, "sheet": sheet, "issue": "date_format",
                                       "detail": f"{c}: {f}", "count": int(n)})
                df[c] = pd.to_datetime(df[c].map(parse_date), errors="coerce")
        for c in num_cols:
            if c in df:
                before = df[c].notna().sum()
                df[c] = pd.to_numeric(df[c], errors="coerce")
                bad = int(before - df[c].notna().sum())
                if bad:
                    issues.append({"patient_id": pid, "sheet": sheet, "issue": "not_a_number",
                                   "detail": c, "count": bad})
        if table == "labs" and "Unit" in df:
            n = int(df["Unit"].isin(UNIT_FIXES.keys()).sum())
            if n:
                issues.append({"patient_id": pid, "sheet": sheet, "issue": "unit_variant",
                               "detail": "10^9/L written without 'x'", "count": n})
            df["Unit"] = df["Unit"].replace(UNIT_FIXES)
        if table in ("vitals_daily", "wearable_daily"):
            for c in num_cols:
                miss = int(df[c].isna().sum())
                if miss:
                    issues.append({"patient_id": pid, "sheet": sheet, "issue": "missing_value",
                                   "detail": c, "count": miss})
                lo, hi = LIMITS.get(c, (None, None))
                if lo is not None:
                    out = int(((df[c] < lo) | (df[c] > hi)).sum())
                    if out:
                        issues.append({"patient_id": pid, "sheet": sheet, "issue": "out_of_range",
                                       "detail": f"{c} outside {lo}–{hi}", "count": out})
            dup = int(df["Date"].duplicated().sum())
            if dup:
                issues.append({"patient_id": pid, "sheet": sheet, "issue": "duplicate_date", "detail": "", "count": dup})
        if table == "medications" and df.empty:
            issues.append({"patient_id": pid, "sheet": sheet, "issue": "no_rows", "detail": "no medication rows", "count": 1})
        df.columns = [to_snake(c) for c in df.columns]
        df.insert(0, "patient_id", pid)
        tables[table] = df

    profile_row = {
        "patient_id": pid,
        "age": pd.to_numeric(profile.get("Age"), errors="coerce"),
        "sex": profile.get("Sex"),
        "height_cm": pd.to_numeric(profile.get("Height (cm)"), errors="coerce"),
        "blood_group": profile.get("Blood Group"),
        "allergies": profile.get("Allergies"),
        "family_history": profile.get("Family History"),
        "data_window": profile.get("Data Window"),
        "source_file": fname,
    }
    tables["patients"] = pd.DataFrame([profile_row])
    return tables, issues


def _read_safe(path):
    try:
        t, i = read_workbook(path)
        return path, t, i, None
    except Exception as e:  # keep going; report the file
        return path, None, [], repr(e)


def load_folder(raw_dir: str, db_path: str, workers: int = 2, verbose: bool = True) -> dict:
    """Read every workbook under raw_dir and write all tables to a SQLite database."""
    files = sorted(glob.glob(os.path.join(raw_dir, "**", "*.xlsx"), recursive=True))
    with Pool(workers) as pool:
        results = pool.map(_read_safe, files, chunksize=8)
    merged: dict[str, list[pd.DataFrame]] = {}
    issues, failed = [], []
    for path, tables, iss, err in results:
        if err:
            failed.append({"file": path, "error": err})
            continue
        issues.extend(iss)
        for name, df in tables.items():
            merged.setdefault(name, []).append(df)
    if os.path.exists(db_path):
        os.remove(db_path)
    con = sqlite3.connect(db_path)
    counts = {}
    for name, parts in merged.items():
        df = pd.concat(parts, ignore_index=True)
        for c in df.columns:
            if pd.api.types.is_datetime64_any_dtype(df[c]):
                df[c] = df[c].dt.strftime("%Y-%m-%d")
        df.to_sql(name, con, index=False)
        counts[name] = len(df)
    pd.DataFrame(issues, columns=["patient_id", "sheet", "issue", "detail", "count"]).to_sql("data_issues", con, index=False)
    for t, col in [("vitals_daily", "date"), ("wearable_daily", "date"), ("labs", "date")]:
        con.execute(f"CREATE INDEX idx_{t} ON {t}(patient_id, {col})")
    con.commit()
    con.close()
    if verbose:
        print(f"Loaded {len(files) - len(failed)} of {len(files)} workbooks into {db_path}")
        for k, v in counts.items():
            print(f"  {k:<16} {v:>8,} rows")
        if failed:
            print("Failed files:", failed)
    return {"files": len(files), "failed": failed, "counts": counts, "issues": len(issues)}
