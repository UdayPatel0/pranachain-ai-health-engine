"""Everything the patient creates: share links, the access log, medicine check-ins, emergency contact.

Stored in data/vitalens.db (SQLite, created automatically).

The access log is hash-chained, like a small private ledger: each entry stores the hash of the entry before it,
so if anyone edits or deletes an old entry, verify_log() finds the break. This is the same idea PranaChain uses on
its blockchain, kept local for the prototype (a production version would anchor these hashes on PranaChain).
"""
from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

DB_FILE = Path(__file__).resolve().parent.parent / "data" / "vitalens.db"
GENESIS = "0" * 64
_lock = threading.Lock()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(d: datetime) -> str:
    return d.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _db() -> sqlite3.Connection:
    con = sqlite3.connect(DB_FILE, check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.executescript("""
    CREATE TABLE IF NOT EXISTS shares(token TEXT PRIMARY KEY, pid TEXT, kind TEXT, label TEXT,
        created TEXT, expires TEXT, revoked TEXT, views INTEGER DEFAULT 0);
    CREATE TABLE IF NOT EXISTS audit(seq INTEGER PRIMARY KEY AUTOINCREMENT, pid TEXT, ts TEXT, actor TEXT,
        action TEXT, detail TEXT, prev TEXT, hash TEXT);
    CREATE INDEX IF NOT EXISTS audit_pid ON audit(pid, seq);
    CREATE TABLE IF NOT EXISTS doses(pid TEXT, day TEXT, med TEXT, status TEXT, ts TEXT, PRIMARY KEY(pid, day, med));
    CREATE TABLE IF NOT EXISTS profile(pid TEXT PRIMARY KEY, data TEXT);
    CREATE TABLE IF NOT EXISTS documents(id TEXT PRIMARY KEY, pid TEXT, title TEXT, kind TEXT, doc_date TEXT,
        filename TEXT, mime TEXT, size INTEGER, sha256 TEXT, uploaded TEXT);
    CREATE INDEX IF NOT EXISTS documents_pid ON documents(pid, uploaded);
    CREATE TABLE IF NOT EXISTS new_patients(pid TEXT PRIMARY KEY, profile TEXT, created TEXT);
    CREATE TABLE IF NOT EXISTS results(id TEXT PRIMARY KEY, pid TEXT, test TEXT, value REAL, date TEXT, source TEXT, created TEXT);
    CREATE INDEX IF NOT EXISTS results_pid ON results(pid, date);
    CREATE TABLE IF NOT EXISTS requests(id TEXT PRIMARY KEY, token TEXT, pid TEXT, viewer TEXT, role TEXT,
        secret_hash TEXT, status TEXT, created TEXT, decided TEXT);
    CREATE INDEX IF NOT EXISTS requests_pid ON requests(pid, status);
    """)
    have = {r[1] for r in con.execute("PRAGMA table_info(shares)")}
    for col, ddl in (("code_hash", "TEXT"), ("approval", "INTEGER DEFAULT 0"), ("fails", "INTEGER DEFAULT 0")):
        if col not in have:  # upgrade databases made by v1.0 / v1.1
            con.execute(f"ALTER TABLE shares ADD COLUMN {col} {ddl}")
    con.commit()
    return con


_con: sqlite3.Connection | None = None


def con() -> sqlite3.Connection:
    global _con
    if _con is None:
        _con = _db()
    return _con


def reset_for_tests(path: Path) -> None:
    global DB_FILE, _con, UPLOADS
    DB_FILE, _con, UPLOADS = path, None, path.parent / "uploads"


# ---------------- access log (hash chain) ----------------
def _entry_hash(prev: str, pid: str, ts: str, actor: str, action: str, detail: str) -> str:
    return hashlib.sha256(json.dumps([prev, pid, ts, actor, action, detail], ensure_ascii=False).encode()).hexdigest()


def log(pid: str, actor: str, action: str, detail: str = "") -> dict:
    with _lock:
        c = con()
        row = c.execute("SELECT hash FROM audit WHERE pid=? ORDER BY seq DESC LIMIT 1", (pid,)).fetchone()
        prev = row["hash"] if row else GENESIS
        ts = _iso(_now())
        h = _entry_hash(prev, pid, ts, actor, action, detail)
        c.execute("INSERT INTO audit(pid,ts,actor,action,detail,prev,hash) VALUES(?,?,?,?,?,?,?)",
                  (pid, ts, actor, action, detail, prev, h))
        c.commit()
    return {"ts": ts, "actor": actor, "action": action, "detail": detail, "hash": h}


def read_log(pid: str, limit: int = 200) -> list[dict]:
    rows = con().execute("SELECT * FROM audit WHERE pid=? ORDER BY seq DESC LIMIT ?", (pid, limit)).fetchall()
    return [{k: r[k] for k in ("ts", "actor", "action", "detail", "hash", "prev")} for r in rows]


def verify_log(pid: str) -> dict:
    prev = GENESIS
    rows = con().execute("SELECT * FROM audit WHERE pid=? ORDER BY seq", (pid,)).fetchall()
    for i, r in enumerate(rows):
        if r["prev"] != prev or _entry_hash(prev, pid, r["ts"], r["actor"], r["action"], r["detail"]) != r["hash"]:
            return {"ok": False, "entries": len(rows), "broken_at": i + 1, "head": None}
        prev = r["hash"]
    return {"ok": True, "entries": len(rows), "broken_at": None, "head": prev}


# ---------------- share links ----------------
def create_share(pid: str, kind: str, label: str, hours: int | None) -> dict:
    token = secrets.token_urlsafe(18)
    created = _now()
    expires = _iso(created + timedelta(hours=hours)) if hours else None
    con().execute("INSERT INTO shares(token,pid,kind,label,created,expires) VALUES(?,?,?,?,?,?)",
                  (token, pid, kind, label, _iso(created), expires))
    con().commit()
    return get_share(token)


def _share_dict(r: sqlite3.Row) -> dict:
    d = dict(r)
    d["active"] = not d["revoked"] and (not d["expires"] or d["expires"] > _iso(_now()))
    return d


def get_share(token: str) -> dict | None:
    r = con().execute("SELECT * FROM shares WHERE token=?", (token,)).fetchone()
    return _share_dict(r) if r else None


def list_shares(pid: str) -> list[dict]:
    rows = con().execute("SELECT * FROM shares WHERE pid=? ORDER BY created DESC", (pid,)).fetchall()
    return [_share_dict(r) for r in rows]


def revoke_share(pid: str, token: str) -> dict | None:
    s = get_share(token)
    if not s or s["pid"] != pid:
        return None
    con().execute("UPDATE shares SET revoked=? WHERE token=?", (_iso(_now()), token))
    con().commit()
    return get_share(token)


def count_view(token: str) -> None:
    con().execute("UPDATE shares SET views=views+1 WHERE token=?", (token,))
    con().commit()


def emergency_share(pid: str) -> dict:
    """The patient's one standing emergency link (created on first use, can be replaced)."""
    for s in list_shares(pid):
        if s["kind"] == "emergency" and s["active"]:
            return s
    return create_share(pid, "emergency", "Emergency card", None)


# ---------------- medicine check-in ----------------
def set_dose(pid: str, day: str, med: str, status: str | None) -> None:
    if status is None:
        con().execute("DELETE FROM doses WHERE pid=? AND day=? AND med=?", (pid, day, med))
    else:
        con().execute("INSERT OR REPLACE INTO doses(pid,day,med,status,ts) VALUES(?,?,?,?,?)",
                      (pid, day, med, status, _iso(_now())))
    con().commit()


def doses(pid: str, since: str) -> list[dict]:
    rows = con().execute("SELECT day,med,status FROM doses WHERE pid=? AND day>=? ORDER BY day", (pid, since)).fetchall()
    return [dict(r) for r in rows]


# ---------------- profile (emergency contact) ----------------
def get_profile(pid: str) -> dict:
    r = con().execute("SELECT data FROM profile WHERE pid=?", (pid,)).fetchone()
    return json.loads(r["data"]) if r else {}


def set_profile(pid: str, data: dict) -> dict:
    con().execute("INSERT OR REPLACE INTO profile(pid,data) VALUES(?,?)", (pid, json.dumps(data, ensure_ascii=False)))
    con().commit()
    return data


# ---------------- medical documents ----------------
UPLOADS = Path(__file__).resolve().parent.parent / "data" / "uploads"
DOC_KINDS = ("Lab report", "Prescription", "Imaging / scan", "Doctor's letter", "Discharge summary", "Vaccination", "Other")
MAX_DOC_BYTES = 10 * 1024 * 1024
_MAGIC = [(b"%PDF-", "application/pdf", "pdf"), (b"\x89PNG\r\n\x1a\n", "image/png", "png"),
          (b"\xff\xd8\xff", "image/jpeg", "jpg")]


def sniff(blob: bytes) -> tuple[str, str] | None:
    """Trust the file's first bytes, not its name: only real PDFs, PNGs, JPEGs and WebPs are accepted."""
    for magic, mime, ext in _MAGIC:
        if blob.startswith(magic):
            return mime, ext
    if blob[:4] == b"RIFF" and blob[8:12] == b"WEBP":
        return "image/webp", "webp"
    return None


def add_document(pid: str, blob: bytes, title: str, kind: str, doc_date: str | None, filename: str) -> dict:
    mime, ext = sniff(blob) or (None, None)
    if not mime:
        raise ValueError("Only PDF, JPG, PNG or WebP files can be uploaded.")
    did = secrets.token_urlsafe(9)
    folder = UPLOADS / pid
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{did}.{ext}").write_bytes(blob)
    row = (did, pid, title, kind, doc_date, filename, mime, len(blob), hashlib.sha256(blob).hexdigest(), _iso(_now()))
    con().execute("INSERT INTO documents VALUES(?,?,?,?,?,?,?,?,?,?)", row)
    con().commit()
    return get_document(pid, did)


def list_documents(pid: str) -> list[dict]:
    rows = con().execute("SELECT * FROM documents WHERE pid=? ORDER BY COALESCE(doc_date, substr(uploaded,1,10)) DESC, uploaded DESC",
                         (pid,)).fetchall()
    return [dict(r) for r in rows]


def get_document(pid: str, did: str) -> dict | None:
    r = con().execute("SELECT * FROM documents WHERE pid=? AND id=?", (pid, did)).fetchone()
    return dict(r) if r else None


def document_path(doc: dict) -> Path:
    ext = {"application/pdf": "pdf", "image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}[doc["mime"]]
    return UPLOADS / doc["pid"] / f"{doc['id']}.{ext}"


def delete_document(pid: str, did: str) -> dict | None:
    d = get_document(pid, did)
    if not d:
        return None
    document_path(d).unlink(missing_ok=True)
    con().execute("DELETE FROM documents WHERE pid=? AND id=?", (pid, did))
    con().commit()
    return d



# ---------------- doctor access: code, approval requests ----------------
MAX_CODE_TRIES = 5


def _h(x: str) -> str:
    return hashlib.sha256(x.encode()).hexdigest()


def new_code() -> str:
    return f"{secrets.randbelow(10**6):06d}"


def set_share_security(token: str, code: str, approval: bool) -> None:
    con().execute("UPDATE shares SET code_hash=?, approval=?, fails=0 WHERE token=?", (_h(token + ":" + code), int(approval), token))
    con().commit()


def check_code(token: str, code: str) -> str:
    """'ok', 'wrong' or 'locked' (after MAX_CODE_TRIES wrong codes the link is switched off)."""
    import hmac
    s = get_share(token)
    if not s or not s.get("code_hash"):
        return "wrong"
    if hmac.compare_digest(s["code_hash"], _h(token + ":" + code.strip())):
        con().execute("UPDATE shares SET fails=0 WHERE token=?", (token,))
        con().commit()
        return "ok"
    fails = (s.get("fails") or 0) + 1
    con().execute("UPDATE shares SET fails=? WHERE token=?", (fails, token))
    if fails >= MAX_CODE_TRIES:
        con().execute("UPDATE shares SET revoked=? WHERE token=?", (_iso(_now()), token))
    con().commit()
    return "locked" if fails >= MAX_CODE_TRIES else "wrong"


def create_request(token: str, pid: str, viewer: str, role: str, status: str) -> tuple[dict, str]:
    rid, secret = secrets.token_urlsafe(9), secrets.token_urlsafe(18)
    con().execute("INSERT INTO requests VALUES(?,?,?,?,?,?,?,?,?)",
                  (rid, token, pid, viewer, role, _h(secret), status, _iso(_now()), _iso(_now()) if status != "pending" else None))
    con().commit()
    return get_request(rid), secret


def get_request(rid: str) -> dict | None:
    r = con().execute("SELECT * FROM requests WHERE id=?", (rid,)).fetchone()
    return dict(r) if r else None


def request_secret_ok(req: dict, secret: str) -> bool:
    import hmac
    return hmac.compare_digest(req["secret_hash"], _h(secret))


def pending_requests(pid: str) -> list[dict]:
    rows = con().execute("SELECT r.*, s.label FROM requests r JOIN shares s ON s.token=r.token WHERE r.pid=? AND r.status='pending' "
                         "ORDER BY r.created", (pid,)).fetchall()
    return [dict(r) for r in rows]


def decide_request(pid: str, rid: str, approve: bool) -> dict | None:
    r = get_request(rid)
    if not r or r["pid"] != pid or r["status"] != "pending":
        return None
    con().execute("UPDATE requests SET status=?, decided=? WHERE id=?", ("approved" if approve else "denied", _iso(_now()), rid))
    con().commit()
    return get_request(rid)


# ---------------- new patients and their own results ----------------
def create_new_patient(profile: dict) -> str:
    with _lock:
        n = con().execute("SELECT COUNT(*) FROM new_patients").fetchone()[0] + 1
        pid = f"NP{n:04d}"
        while con().execute("SELECT 1 FROM new_patients WHERE pid=?", (pid,)).fetchone():
            n += 1
            pid = f"NP{n:04d}"
        con().execute("INSERT INTO new_patients VALUES(?,?,?)", (pid, json.dumps(profile, ensure_ascii=False), _iso(_now())))
        con().commit()
    return pid


def new_patient_profile(pid: str) -> dict | None:
    r = con().execute("SELECT profile, created FROM new_patients WHERE pid=?", (pid,)).fetchone()
    if not r:
        return None
    return json.loads(r["profile"]) | {"created": r["created"][:10]}


def add_results(pid: str, items: list[dict], source: str) -> int:
    for it in items:
        con().execute("INSERT INTO results VALUES(?,?,?,?,?,?,?)",
                      (secrets.token_urlsafe(9), pid, it["test"], float(it["value"]), it["date"], source, _iso(_now())))
    con().commit()
    return len(items)


def list_results(pid: str) -> list[dict]:
    return [dict(r) for r in con().execute("SELECT * FROM results WHERE pid=? ORDER BY date, test", (pid,)).fetchall()]


def delete_result(pid: str, rid: str) -> bool:
    c = con().execute("DELETE FROM results WHERE pid=? AND id=?", (pid, rid))
    con().commit()
    return c.rowcount > 0
