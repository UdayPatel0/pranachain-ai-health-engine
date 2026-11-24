"""VitaLens server: patient sign-in, each person's own record, and checked AI explanations.

Run:  uvicorn app.main:app --port 8000   (or start_demo.bat / start_demo.sh)
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from fastapi import Cookie, FastAPI, HTTPException, Query, Response  # noqa: E402
from fastapi import File, Form, Request, UploadFile  # noqa: E402
from fastapi.responses import FileResponse, Response as RawResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

from . import ai, auth, data, newpatients, records, store  # noqa: E402

WEB = Path(__file__).resolve().parent.parent / "web"
COOKIE = "vl_session"
app = FastAPI(title="VitaLens", version="1.0", docs_url="/api/docs", redoc_url=None)
limiter = auth.LoginLimiter()

CSP = ("default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
       "font-src 'self' https://fonts.gstatic.com; img-src 'self' data: blob:; connect-src 'self'; frame-src 'self'; "
       "object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'")


@app.middleware("http")
async def security_headers(request, call_next):
    resp = await call_next(request)
    h = resp.headers
    h.setdefault("X-Content-Type-Options", "nosniff")
    h.setdefault("Referrer-Policy", "no-referrer")  # share links never leak to other sites
    h.setdefault("X-Frame-Options", "DENY")
    h.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    if h.get("content-type", "").startswith("text/html"):
        h.setdefault("Content-Security-Policy", CSP)
    if request.url.path.startswith("/api/"):
        h.setdefault("Cache-Control", "no-store")
    return resp
budget = ai.Budget()
_explain_cache: dict[str, dict] = {}


class Login(BaseModel):
    id: str = Field(max_length=20)
    password: str = Field(max_length=200)


class Ask(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    lang: str = "en"
    notes: list[str] = Field(default_factory=list, max_length=30)


def _me(token: str | None) -> dict:
    pid = auth.read_token(token)
    rec = data.get_patient(pid) if pid else None
    if not rec:
        raise HTTPException(401, "Please sign in.")
    return rec


def _clean_notes(notes: list[str]) -> list[str]:
    return [str(n).strip()[:200] for n in notes if str(n).strip()][:30]


def _ai_or_error(rec: dict, build, lang: str, notes: list[str]) -> dict:
    if not budget.take(rec["id"]):
        raise HTTPException(429, "You've asked a lot this hour. Please try again later.")
    try:
        # Numbers the person wrote in their own notes are allowed too, like in the web app.
        return ai.generate(build, {**rec["ai"]["evidence"], "patient_notes": notes}, lang)
    except ai.AIError as e:
        return {"provider": ai.provider(), "error": str(e), "text": "", "checks": [], "passed": False}


# ---------------- API ----------------
@app.get("/api/health")
def health():
    return {"status": "ok", "provider": ai.provider(), "model": ai.model(),
            "patients": len(data.patients()), "accounts": len(auth.load_accounts())}


@app.post("/api/login")
def login(body: Login, response: Response):
    pid = body.id.strip().upper()
    if limiter.blocked(pid):
        raise HTTPException(429, "Too many tries. Please wait 10 minutes and try again.")
    stored = auth.load_accounts().get(pid)
    if not stored or not auth.verify_password(body.password.strip(), stored) or not data.get_patient(pid):
        limiter.fail(pid)
        raise HTTPException(401, "That ID and password don't match.")
    limiter.reset(pid)
    store.log(pid, "You", "Signed in", "")
    response.set_cookie(COOKIE, auth.make_token(pid), max_age=auth.SESSION_HOURS * 3600, httponly=True,
                        samesite="strict", secure=os.getenv("COOKIE_SECURE", "0") == "1")
    return {"ok": True, "id": pid}


@app.post("/api/logout")
def logout(response: Response):
    response.delete_cookie(COOKIE)
    return {"ok": True}


@app.get("/api/me")
def me(vl_session: str | None = Cookie(default=None)):
    return _me(vl_session)


@app.get("/api/me/explain")
def explain(lang: str = Query("en", max_length=5), notes: str = Query("[]", max_length=8000),
            vl_session: str | None = Cookie(default=None)):
    rec = _me(vl_session)
    if ai.provider() == "rule-based":
        return {"provider": "rule-based", "text": rec["ai"]["rule_text"], "checks": [], "passed": True}
    try:
        note_list = _clean_notes(json.loads(notes)) if notes else []
    except (ValueError, TypeError):
        note_list = []
    key = hashlib.sha256(json.dumps([rec["id"], lang, note_list], ensure_ascii=False).encode()).hexdigest()
    if key in _explain_cache:
        return _explain_cache[key]
    out = _ai_or_error(rec, lambda pr: ai.explain_prompt(rec["ai"]["evidence"], lang, note_list, pr), lang, note_list)
    if out.get("passed"):
        _explain_cache[key] = out
    return out


@app.post("/api/me/ask")
def ask(body: Ask, vl_session: str | None = Cookie(default=None)):
    rec = _me(vl_session)
    if ai.provider() == "rule-based":
        return {"provider": "rule-based", "text": "", "checks": [], "passed": False}
    notes = _clean_notes(body.notes)
    return _ai_or_error(rec, lambda pr: ai.ask_prompt(rec["ai"]["evidence"], body.question.strip(), body.lang, notes, pr),
                        body.lang, notes)


# ---------------- share with a doctor + access log ----------------
class ShareIn(BaseModel):
    label: str = Field(default="My doctor", max_length=80)
    hours: int = Field(default=24, ge=1, le=24 * 30)
    approval: bool = True


class OpenIn(BaseModel):
    viewer: str = Field(min_length=2, max_length=80)
    role: str = Field(default="Doctor", max_length=40)
    code: str = Field(default="", max_length=12)


class ClaimIn(BaseModel):
    secret: str = Field(max_length=64)


VIEW_COOKIE = "vl_view"


def _link(request: Request, s: dict) -> str:
    return str(request.base_url).rstrip("/") + ("/e/" if s["kind"] == "emergency" else "/s/") + s["token"]


def _public_share(s: dict, request: Request) -> dict:
    return {k: s[k] for k in ("token", "kind", "label", "created", "expires", "revoked", "views", "active")} | {
        "url": _link(request, s), "approval": bool(s.get("approval"))}


def _qr_svg(text: str) -> bytes:
    import io

    import qrcode
    import qrcode.image.svg

    img = qrcode.make(text, image_factory=qrcode.image.svg.SvgPathImage, box_size=10, border=2)
    b = io.BytesIO()
    img.save(b)
    return b.getvalue()


@app.get("/api/me/shares")
def my_shares(request: Request, vl_session: str | None = Cookie(default=None)):
    rec = _me(vl_session)
    return [_public_share(s, request) for s in store.list_shares(rec["id"]) if s["kind"] == "doctor"]


@app.post("/api/me/shares")
def new_share(body: ShareIn, request: Request, vl_session: str | None = Cookie(default=None)):
    rec = _me(vl_session)
    s = store.create_share(rec["id"], "doctor", body.label.strip() or "My doctor", body.hours)
    code = store.new_code()
    store.set_share_security(s["token"], code, body.approval)
    store.log(rec["id"], "You", "Shared your record",
              f"{s['label']} · for {body.hours} h · access code{' + your approval' if body.approval else ''}")
    # The code is shown once, to the patient only. It is stored as a hash.
    return _public_share(store.get_share(s["token"]), request) | {"code": code}


@app.post("/api/me/shares/{token}/code")
def new_share_code(token: str, request: Request, vl_session: str | None = Cookie(default=None)):
    rec = _me(vl_session)
    s = store.get_share(token)
    if not s or s["pid"] != rec["id"] or s["kind"] != "doctor" or not s["active"]:
        raise HTTPException(404, "Link not found.")
    code = store.new_code()
    store.set_share_security(token, code, bool(s.get("approval")))
    store.log(rec["id"], "You", "Changed an access code", s["label"])
    return {"code": code}


@app.delete("/api/me/shares/{token}")
def stop_share(token: str, request: Request, vl_session: str | None = Cookie(default=None)):
    rec = _me(vl_session)
    s = store.revoke_share(rec["id"], token)
    if not s:
        raise HTTPException(404, "Link not found.")
    store.log(rec["id"], "You", "Stopped sharing" if s["kind"] == "doctor" else "Replaced emergency link", s["label"])
    return _public_share(s, request)


@app.get("/api/me/shares/{token}/qr.svg")
def share_qr(token: str, request: Request, vl_session: str | None = Cookie(default=None)):
    rec = _me(vl_session)
    s = store.get_share(token)
    if not s or s["pid"] != rec["id"]:
        raise HTTPException(404, "Link not found.")
    return RawResponse(_qr_svg(_link(request, s)), media_type="image/svg+xml")


@app.get("/api/me/log")
def my_log(vl_session: str | None = Cookie(default=None)):
    rec = _me(vl_session)
    return {"entries": store.read_log(rec["id"]), "verify": store.verify_log(rec["id"])}


def _active_share(token: str, kind: str) -> dict:
    s = store.get_share(token)
    if not s or s["kind"] != kind:
        raise HTTPException(404, "This link doesn't exist.")
    if not s["active"]:
        raise HTTPException(410, "This link has expired or the patient stopped sharing it.")
    return s


@app.get("/api/share/{token}")
def share_info(token: str):
    s = _active_share(token, "doctor")
    return {"label": s["label"], "expires": s["expires"], "approval": bool(s.get("approval"))}


def _doctor_payload(s: dict) -> dict:
    rec = data.get_patient(s["pid"])
    docs = [_doc_public(d) for d in store.list_documents(s["pid"])]
    return records.doctor_view(rec) | {"expires": s["expires"], "documents": docs}


def _grant(response: Response, s: dict, req: dict) -> None:
    """Let this browser in: a signed, HttpOnly cookie that only works for this link, until the link ends (max 4 h)."""
    from datetime import datetime, timezone
    left = 4.0
    if s["expires"]:
        left = min(left, max(0.01, (datetime.fromisoformat(s["expires"].replace("Z", "+00:00")) -
                                    datetime.now(timezone.utc)).total_seconds() / 3600))
    tok = auth.sign({"t": s["token"], "r": req["id"], "v": f"{req['viewer']} ({req['role']})"}, left)
    response.set_cookie(VIEW_COOKIE, tok, max_age=int(left * 3600), httponly=True, samesite="strict",
                        path=f"/api/share/{s['token']}", secure=os.getenv("COOKIE_SECURE", "0") == "1")
    store.count_view(s["token"])
    store.log(s["pid"], f"{req['viewer']} ({req['role']})", "Viewed your record", f"via link '{s['label']}'")


@app.post("/api/share/{token}/open")
def share_open(token: str, body: OpenIn, response: Response):
    s = _active_share(token, "doctor")
    viewer, role = body.viewer.strip(), body.role.strip() or "Doctor"
    result = store.check_code(token, body.code)
    if result == "locked":
        store.log(s["pid"], f"{viewer} ({role})", "Link locked", f"5 wrong access codes on '{s['label']}'")
        raise HTTPException(423, "Too many wrong codes. This link is now switched off; ask the patient for a new one.")
    if result != "ok":
        store.log(s["pid"], f"{viewer} ({role})", "Entered a wrong code", f"on link '{s['label']}'")
        left = store.MAX_CODE_TRIES - (store.get_share(token).get("fails") or 0)
        raise HTTPException(401, f"That access code isn't right. {left} {'try' if left == 1 else 'tries'} left.")
    if s.get("approval"):
        req, secret = store.create_request(token, s["pid"], viewer, role, "pending")
        store.log(s["pid"], f"{viewer} ({role})", "Asked to view your record", f"via link '{s['label']}'")
        return {"pending": True, "request": req["id"], "secret": secret}
    req, _ = store.create_request(token, s["pid"], viewer, role, "approved")
    _grant(response, s, req)
    return _doctor_payload(s)


@app.post("/api/share/{token}/requests/{rid}")
def share_claim(token: str, rid: str, body: ClaimIn, response: Response):
    """The doctor's page asks every few seconds: has the patient approved yet?"""
    s = _active_share(token, "doctor")
    req = store.get_request(rid)
    if not req or req["token"] != token or not store.request_secret_ok(req, body.secret):
        raise HTTPException(404, "Request not found.")
    if req["status"] == "pending":
        return {"pending": True}
    if req["status"] == "denied":
        raise HTTPException(403, "The patient said no to this request.")
    if req["status"] == "opened":
        raise HTTPException(409, "This request was already used. Enter the code again.")
    store.con().execute("UPDATE requests SET status='opened' WHERE id=?", (rid,))
    store.con().commit()
    _grant(response, s, req)
    return _doctor_payload(s)


@app.get("/api/me/requests")
def my_requests(vl_session: str | None = Cookie(default=None)):
    rec = _me(vl_session)
    return [{k: r[k] for k in ("id", "viewer", "role", "label", "created")} for r in store.pending_requests(rec["id"])
            if (store.get_share(r["token"]) or {}).get("active")]


class DecideIn(BaseModel):
    approve: bool


@app.post("/api/me/requests/{rid}")
def decide(rid: str, body: DecideIn, vl_session: str | None = Cookie(default=None)):
    rec = _me(vl_session)
    r = store.decide_request(rec["id"], rid, body.approve)
    if not r:
        raise HTTPException(404, "Request not found or already answered.")
    store.log(rec["id"], "You", "Approved access" if body.approve else "Denied access", f"{r['viewer']} ({r['role']})")
    return {"ok": True}


# ---------------- emergency travel card ----------------
class ProfileIn(BaseModel):
    contact_name: str = Field(default="", max_length=80)
    contact_phone: str = Field(default="", max_length=40)
    note: str = Field(default="", max_length=200)


@app.get("/api/me/emergency")
def my_emergency(request: Request, vl_session: str | None = Cookie(default=None)):
    rec = _me(vl_session)
    s = store.emergency_share(rec["id"])
    return {"card": records.emergency_card(rec, store.get_profile(rec["id"])), "link": _public_share(s, request)}


@app.put("/api/me/profile")
def save_profile(body: ProfileIn, vl_session: str | None = Cookie(default=None)):
    rec = _me(vl_session)
    store.set_profile(rec["id"], store.get_profile(rec["id"]) | body.model_dump())
    store.log(rec["id"], "You", "Updated emergency contact", "")
    return {"ok": True}


@app.post("/api/me/emergency/renew")
def renew_emergency(request: Request, vl_session: str | None = Cookie(default=None)):
    rec = _me(vl_session)
    old = store.emergency_share(rec["id"])
    store.revoke_share(rec["id"], old["token"])
    store.log(rec["id"], "You", "Replaced emergency link", "The old QR code no longer works")
    return {"link": _public_share(store.emergency_share(rec["id"]), request)}


@app.get("/api/emergency/{token}")
def emergency_open(token: str):
    s = _active_share(token, "emergency")
    rec = data.get_patient(s["pid"])
    store.count_view(token)
    store.log(s["pid"], "Someone with your emergency QR", "Opened your emergency card", "")
    return records.emergency_card(rec, store.get_profile(s["pid"]))


# ---------------- medicine check-in ----------------
class DoseIn(BaseModel):
    med: str = Field(max_length=80)
    day: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    status: str | None = Field(default=None, pattern="^(taken|missed)$")


@app.get("/api/me/doses")
def my_doses(since: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2}$"), vl_session: str | None = Cookie(default=None)):
    rec = _me(vl_session)
    return {"meds": records.current_meds(rec), "log": store.doses(rec["id"], since)}


@app.post("/api/me/doses")
def log_dose(body: DoseIn, vl_session: str | None = Cookie(default=None)):
    rec = _me(vl_session)
    names = {m["name"] for m in records.current_meds(rec)}
    if body.med not in names:
        raise HTTPException(400, "That medicine isn't on your list.")
    store.set_dose(rec["id"], body.day, body.med, body.status)
    return {"ok": True}


@app.get("/api/me/reminder.ics")
def reminder(time: str = Query("20:00", pattern=r"^\d{2}:\d{2}$"), vl_session: str | None = Cookie(default=None)):
    rec = _me(vl_session)
    names = ", ".join(m["name"] for m in records.current_meds(rec)) or "your medicines"
    hh, mm = time.split(":")
    from datetime import date
    start = date.today().strftime("%Y%m%d")
    ics = "\r\n".join([
        "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//VitaLens//Medicine reminder//EN", "BEGIN:VEVENT",
        f"UID:vitalens-{rec['id']}-{hh}{mm}@vitalens", f"DTSTAMP:{start}T000000Z",
        f"DTSTART:{start}T{hh}{mm}00", "DURATION:PT10M", "RRULE:FREQ=DAILY",
        f"SUMMARY:Take {names}", "DESCRIPTION:Then tap Taken in VitaLens.",
        "BEGIN:VALARM", "ACTION:DISPLAY", "DESCRIPTION:Medicine time", "TRIGGER:PT0M", "END:VALARM",
        "END:VEVENT", "END:VCALENDAR", ""])
    return RawResponse(ics, media_type="text/calendar",
                       headers={"Content-Disposition": 'attachment; filename="vitalens-medicine-reminder.ics"'})


# ---------------- medical documents ----------------
def _doc_public(d: dict) -> dict:
    return {k: d[k] for k in ("id", "title", "kind", "doc_date", "filename", "mime", "size", "uploaded")}


@app.get("/api/me/documents")
def my_documents(vl_session: str | None = Cookie(default=None)):
    rec = _me(vl_session)
    return {"documents": [_doc_public(d) for d in store.list_documents(rec["id"])], "kinds": store.DOC_KINDS}


@app.post("/api/me/documents")
async def upload_document(file: UploadFile = File(...), title: str = Form(""), kind: str = Form("Other"),
                          doc_date: str = Form(""), vl_session: str | None = Cookie(default=None)):
    rec = _me(vl_session)
    blob = await file.read(store.MAX_DOC_BYTES + 1)
    if len(blob) > store.MAX_DOC_BYTES:
        raise HTTPException(413, "That file is larger than 10 MB.")
    if not blob:
        raise HTTPException(400, "That file is empty.")
    import re as _re
    date = doc_date if _re.fullmatch(r"\d{4}-\d{2}-\d{2}", doc_date or "") else None
    name = (file.filename or "document").replace("\\", "/").split("/")[-1][:120]
    title = (title.strip() or name.rsplit(".", 1)[0])[:120]
    kind = kind if kind in store.DOC_KINDS else "Other"
    try:
        d = store.add_document(rec["id"], blob, title, kind, date, name)
    except ValueError as e:
        raise HTTPException(415, str(e)) from e
    store.log(rec["id"], "You", "Uploaded a document", f"{kind}: {title}")
    out = _doc_public(d)
    if rec.get("is_new"):  # read lab values from the report; the patient confirms them before saving
        out["found"] = newpatients.find_values(newpatients.extract_text(blob, d["mime"])) | {"readable": d["mime"] == "application/pdf"}
    return out


def _send_doc(d: dict, download: bool) -> FileResponse:
    safe = "".join(c for c in d["filename"] if c.isalnum() or c in " ._-")[:100] or "document"
    return FileResponse(store.document_path(d), media_type=d["mime"], filename=safe,
                        content_disposition_type="attachment" if download else "inline",
                        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})


@app.get("/api/me/documents/{did}")
def open_document(did: str, download: int = 0, vl_session: str | None = Cookie(default=None)):
    rec = _me(vl_session)
    d = store.get_document(rec["id"], did)
    if not d:
        raise HTTPException(404, "Document not found.")
    return _send_doc(d, bool(download))


@app.delete("/api/me/documents/{did}")
def remove_document(did: str, vl_session: str | None = Cookie(default=None)):
    rec = _me(vl_session)
    d = store.delete_document(rec["id"], did)
    if not d:
        raise HTTPException(404, "Document not found.")
    store.log(rec["id"], "You", "Deleted a document", d["title"])
    return {"ok": True}


@app.get("/api/share/{token}/documents/{did}")
def shared_document(token: str, did: str, vl_view: str | None = Cookie(default=None)):
    s = _active_share(token, "doctor")
    g = auth.unsign(vl_view)
    if not g or g.get("t") != token:
        raise HTTPException(401, "Open the record with the access code first.")
    d = store.get_document(s["pid"], did)
    if not d:
        raise HTTPException(404, "Document not found.")
    store.log(s["pid"], g.get("v", "Doctor"), "Opened a document", d["title"])
    return _send_doc(d, False)


# ---------------- life notes ----------------
class NotesIn(BaseModel):
    notes: list[str] = Field(default_factory=list, max_length=30)


@app.get("/api/me/notes")
def get_notes(vl_session: str | None = Cookie(default=None)):
    rec = _me(vl_session)
    return {"notes": store.get_profile(rec["id"]).get("notes", [])}


@app.put("/api/me/notes")
def put_notes(body: NotesIn, vl_session: str | None = Cookie(default=None)):
    rec = _me(vl_session)
    prof = store.get_profile(rec["id"])
    prof["notes"] = _clean_notes(body.notes)
    store.set_profile(rec["id"], prof)
    return {"notes": prof["notes"]}


# ---------------- new patients: sign up, results, scenario judgment ----------------
class MedIn(BaseModel):
    name: str = Field(max_length=60)
    dose: str = Field(default="", max_length=30)
    start: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")


class RegisterIn(BaseModel):
    password: str = Field(min_length=8, max_length=200)
    age: int = Field(ge=13, le=110)
    sex: str = Field(pattern="^(Female|Male)$")
    height: int | None = Field(default=None, ge=80, le=250)
    conditions: list[str] = Field(default_factory=list, max_length=10)
    family: list[str] = Field(default_factory=list, max_length=5)
    meds: list[MedIn] = Field(default_factory=list, max_length=10)
    blood_group: str = Field(default="", max_length=5)
    allergies: str = Field(default="", max_length=120)


reg_limiter = auth.LoginLimiter(limit=5, window=3600)


@app.post("/api/register")
def register(body: RegisterIn, request: Request, response: Response):
    ip = request.client.host if request.client else "?"
    if reg_limiter.blocked(ip):
        raise HTTPException(429, "Too many new accounts from this computer. Please try again later.")
    reg_limiter.fail(ip)
    prof = body.model_dump(exclude={"password"})
    prof["conditions"] = [c for c in body.conditions if c in newpatients.CONDITIONS]
    prof["family"] = [f for f in body.family if f in newpatients.FAMILY]
    prof["meds"] = [m for m in prof["meds"] if m["name"].strip()]
    pid = store.create_new_patient(prof)
    auth.add_account(pid, body.password)
    store.log(pid, "You", "Created your account", "")
    response.set_cookie(COOKIE, auth.make_token(pid), max_age=auth.SESSION_HOURS * 3600, httponly=True,
                        samesite="strict", secure=os.getenv("COOKIE_SECURE", "0") == "1")
    return {"ok": True, "id": pid}


class ResultIn(BaseModel):
    test: str = Field(max_length=40)
    value: float = Field(ge=0, le=5000)
    date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")


class ResultsIn(BaseModel):
    items: list[ResultIn] = Field(min_length=1, max_length=40)
    source: str = Field(default="Typed in", max_length=120)


def _new_me(token: str | None) -> dict:
    rec = _me(token)
    if not rec.get("is_new"):
        raise HTTPException(403, "This account's results come from PranaChain's records.")
    return rec


@app.get("/api/me/results")
def my_results(vl_session: str | None = Cookie(default=None)):
    rec = _new_me(vl_session)
    return {"results": store.list_results(rec["id"]), "tests": newpatients.TESTS + ["Period start"],
            "units": {t: v[0] for t, v in newpatients.REF.items()}}


@app.post("/api/me/results")
def save_results(body: ResultsIn, vl_session: str | None = Cookie(default=None)):
    from datetime import date as _d
    rec = _new_me(vl_session)
    ok = []
    for it in body.items:
        if it.test not in newpatients.REF and it.test != "Period start":
            raise HTTPException(400, f"Unknown test: {it.test}")
        try:
            dt = _d.fromisoformat(it.date)
        except ValueError:
            raise HTTPException(400, f"Bad date: {it.date}")
        if dt > _d.today() or dt.year < 1990:
            raise HTTPException(400, "Dates must be in the past.")
        ok.append(it.model_dump())
    n = store.add_results(rec["id"], ok, body.source.strip() or "Typed in")
    store.log(rec["id"], "You", "Added results", f"{n} from {body.source.strip() or 'Typed in'}")
    return {"ok": True, "added": n}


@app.delete("/api/me/results/{rid}")
def remove_result(rid: str, vl_session: str | None = Cookie(default=None)):
    rec = _new_me(vl_session)
    if not store.delete_result(rec["id"], rid):
        raise HTTPException(404, "Result not found.")
    return {"ok": True}


@app.post("/api/me/documents/{did}/read")
def read_document(did: str, vl_session: str | None = Cookie(default=None)):
    rec = _new_me(vl_session)
    d = store.get_document(rec["id"], did)
    if not d:
        raise HTTPException(404, "Document not found.")
    blob = store.document_path(d).read_bytes()
    return newpatients.find_values(newpatients.extract_text(blob, d["mime"])) | {"readable": d["mime"] == "application/pdf"}


# ---------------- web app ----------------
@app.get("/s/{token}", include_in_schema=False)
def doctor_page(token: str):
    return FileResponse(WEB / "doctor.html", headers={"Cache-Control": "no-store"})


@app.get("/e/{token}", include_in_schema=False)
def emergency_page(token: str):
    return FileResponse(WEB / "emergency.html", headers={"Cache-Control": "no-store"})


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(WEB / "index.html", headers={"Cache-Control": "no-store"})


app.mount("/", StaticFiles(directory=WEB), name="web")
