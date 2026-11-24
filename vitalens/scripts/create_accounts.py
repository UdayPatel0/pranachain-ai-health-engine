"""Create sign-in accounts for VitaLens.

  python scripts/create_accounts.py                 # every patient gets a random password
  python scripts/create_accounts.py --ids PC0989 PC0387 --password demo1234
  python scripts/create_accounts.py --demo          # the demo people from docs, password "vitalens-demo"

Passwords are stored only as PBKDF2 hashes in data/accounts.json.
The plain passwords are written once to accounts_for_team.csv: share it privately, then delete it.
"""
from __future__ import annotations

import argparse
import csv
import json
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import auth, data  # noqa: E402

DEMO_IDS = ["PC0989", "PC0431", "PC0466", "PC0588", "PC0387", "PC0560"]
WORDS = "amber birch cedar delta ember fable grove harbor indigo juniper kestrel lumen maple nectar orchid prairie quartz river sable tundra umber velvet willow zephyr".split()


def new_password() -> str:
    return "-".join(secrets.choice(WORDS) for _ in range(3)) + str(secrets.randbelow(90) + 10)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids", nargs="*", help="patient IDs (default: all)")
    ap.add_argument("--password", help="use this password for all the given IDs")
    ap.add_argument("--demo", action="store_true", help=f"accounts for {', '.join(DEMO_IDS)} with password vitalens-demo")
    a = ap.parse_args()

    if a.demo:
        ids, fixed = DEMO_IDS, "vitalens-demo"
    else:
        ids, fixed = [i.upper() for i in a.ids] if a.ids else sorted(data.patients()), a.password
    missing = [i for i in ids if not data.get_patient(i)]
    if missing:
        sys.exit(f"Unknown patient IDs: {', '.join(missing)}")

    accounts = auth.load_accounts()
    rows = []
    for pid in ids:
        pw = fixed or new_password()
        accounts[pid] = auth.hash_password(pw)
        rows.append((pid, pw))
    auth.ACCOUNTS_FILE.write_text(json.dumps(accounts, indent=1), encoding="utf-8")

    out = ROOT / "accounts_for_team.csv"
    new_file = not out.exists()
    with out.open("a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(["patient_id", "password"])
        w.writerows(rows)
    print(f"Saved {len(rows)} account(s). {len(accounts)} accounts in total.")
    print(f"Passwords written to {out.name} (share privately, then delete it).")


if __name__ == "__main__":
    main()
