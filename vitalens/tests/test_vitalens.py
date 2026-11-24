"""Run with:  python -m pytest -q"""
import json

import pytest
from fastapi.testclient import TestClient

from app import ai, auth, data, store
from app.main import app, budget, limiter, _explain_cache

EN = ai.LANGS["en"][1]
EV = data.get_patient("PC0989")["ai"]["evidence"]


# ---------- safety checks ----------
def test_good_text_passes():
    t = f"Your HbA1c went from 5.7% to 6.46%. Your HDL went up to 53.2. {EN}"
    assert all(c["passed"] for c in ai.checks(t, EV, "en"))


def test_made_up_number_fails():
    ck = ai.checks(f"Your HbA1c is 9.9%. {EN}", EV, "en")
    assert not ck[0]["passed"] and "9.9" in ck[0]["detail"]


@pytest.mark.parametrize("bad", ["You have diabetes.", "You should stop taking metformin.", "This confirms it."])
def test_diagnosis_and_medicine_advice_fail(bad):
    assert not ai.checks(f"{bad} {EN}", EV, "en")[1]["passed"]


def test_missing_disclaimer_fails():
    assert not ai.checks("Your HbA1c went up.", EV, "en")[2]["passed"]


def test_retry_until_safe():
    drafts = iter(["You have diabetes.", f"Your HbA1c went from 5.7% to 6.46%. {EN}"])
    prompts = []
    out = ai.generate(lambda pr: prompts.append(pr) or "p", EV, "en", complete=lambda p: next(drafts))
    assert out["passed"] and out["attempts"] == 2 and prompts[1]  # second prompt carries the reasons


def test_never_shows_unsafe_text():
    out = ai.generate(lambda pr: "p", EV, "en", complete=lambda p: "You have diabetes.")
    assert not out["passed"] and out["text"] == "" and out["attempts"] == ai.MAX_ATTEMPTS


# ---------- API ----------
@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(auth, "ACCOUNTS_FILE", tmp_path / "accounts.json")
    store.reset_for_tests(tmp_path / "test.db")
    monkeypatch.setenv("SESSION_SECRET", "test-secret")
    (tmp_path / "accounts.json").write_text(json.dumps({"PC0989": auth.hash_password("pw1"), "PC0387": auth.hash_password("pw2")}))
    limiter.fails.clear(); budget.calls.clear(); _explain_cache.clear()
    from app.main import reg_limiter; reg_limiter.fails.clear()
    return TestClient(app)


def login(c, pid, pw):
    return c.post("/api/login", json={"id": pid, "password": pw})


def test_sign_in_and_only_own_data(client):
    assert client.get("/api/me").status_code == 401
    assert login(client, "PC0989", "wrong").status_code == 401
    assert login(client, "pc0989", "pw1").status_code == 200
    assert client.get("/api/me").json()["id"] == "PC0989"
    client.post("/api/logout")
    client.cookies.clear()
    assert client.get("/api/me").status_code == 401


def test_forged_cookie_rejected(client):
    login(client, "PC0989", "pw1")
    tok = client.cookies.get("vl_session")
    body, sig = tok.rsplit(".", 1)
    import base64
    forged = base64.urlsafe_b64encode(json.dumps({"id": "PC0387", "exp": 9999999999}).encode()).decode()
    client.cookies.clear()
    client.cookies.set("vl_session", f"{forged}.{sig}")
    assert client.get("/api/me").status_code == 401


def test_login_rate_limit(client):
    for _ in range(5):
        login(client, "PC0387", "bad")
    assert login(client, "PC0387", "pw2").status_code == 429


def test_rule_based_without_key(client, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert client.get("/api/health").json()["provider"] == "rule-based"
    login(client, "PC0989", "pw1")
    j = client.get("/api/me/explain?lang=en").json()
    assert j["provider"] == "rule-based" and "HbA1c" in j["text"]


def test_ai_explain_and_ask(client, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    seen = []
    monkeypatch.setattr(ai, "_complete", lambda p: seen.append(p) or f"Your HbA1c went from 5.7% to 6.46%. {EN}")
    login(client, "PC0989", "pw1")
    j = client.get("/api/me/explain", params={"lang": "en", "notes": json.dumps(["Travelled for 3 weeks"])}).json()
    assert j["passed"] and j["checks"] and "Travelled for 3 weeks" in seen[-1]
    j = client.post("/api/me/ask", json={"question": "Why is my sugar going up?", "lang": "en", "notes": []}).json()
    assert j["passed"] and "QUESTION: Why is my sugar going up?" in seen[-1]


def test_ai_error_is_reported(client, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")

    def boom(p):
        raise ai.AIError("The AI key in .env was not accepted. Check ANTHROPIC_API_KEY.")
    monkeypatch.setattr(ai, "_complete", boom)
    login(client, "PC0989", "pw1")
    assert "not accepted" in client.post("/api/me/ask", json={"question": "hi"}).json()["error"]


# ---------- free local AI (Ollama) ----------
def test_tidy_adds_reminder_and_drops_markdown():
    t = ai.tidy("**Your HbA1c** went from 5.7% to 6.46%.", "en")
    assert "**" not in t and t.endswith(EN)


def test_ollama_call(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "ollama")
    sent = {}

    class R:
        status_code = 200
        def json(self):
            return {"message": {"content": "Your HbA1c went from 5.7% to 6.46%."}}

    import httpx
    monkeypatch.setattr(httpx, "post", lambda url, json, timeout: sent.update(url=url, body=json) or R())
    out = ai.generate(lambda pr: "prompt", EV, "en")
    assert out["passed"] and out["provider"] == "ollama" and sent["url"].endswith("/api/chat")
    assert sent["body"]["model"] == ai.OLLAMA_MODEL and sent["body"]["stream"] is False


def test_ollama_not_running(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "ollama")
    monkeypatch.setattr(ai, "OLLAMA_URL", "http://127.0.0.1:9")
    with pytest.raises(ai.AIError, match="Ollama isn't running"):
        ai._complete("hi")


# ---------- sources ----------
def test_sentences_get_sources():
    fs = ai.facts(EV)
    out = ai.sources(f"Your HbA1c went from 5.7% to 6.46%. You took Metformin XR on 82% of days. {EN}", fs)
    byid = {f["id"]: f["text"] for f in fs}
    assert any("HbA1c" in byid[i] for i in out[0]["sources"])
    assert any("82%" in byid[i] for i in out[1]["sources"])
    assert out[-1]["sources"] == []


# ---------- sharing + access log ----------
def test_share_view_revoke_and_log(client):
    login(client, "PC0989", "pw1")
    s = client.post("/api/me/shares", json={"label": "Dr. Shah", "hours": 24, "approval": False}).json()
    assert s["active"] and s["url"].endswith("/s/" + s["token"]) and len(s["code"]) == 6
    assert client.get(f"/api/me/shares/{s['token']}/qr.svg").headers["content-type"].startswith("image/svg")
    doc = TestClient(app)  # the doctor: not signed in
    assert doc.get(f"/api/share/{s['token']}").json()["label"] == "Dr. Shah"
    v = doc.post(f"/api/share/{s['token']}/open", json={"viewer": "Dr. Priya Shah", "role": "Doctor", "code": s["code"]}).json()
    assert v["id"] == "PC0989" and "labs" in v and "ai" not in v
    log = client.get("/api/me/log").json()
    assert log["verify"]["ok"] and log["entries"][0]["actor"] == "Dr. Priya Shah (Doctor)"
    client.delete(f"/api/me/shares/{s['token']}")
    assert doc.post(f"/api/share/{s['token']}/open", json={"viewer": "Dr. X", "code": s["code"]}).status_code == 410


def test_cannot_revoke_someone_elses_link(client):
    login(client, "PC0989", "pw1")
    s = client.post("/api/me/shares", json={"label": "x", "hours": 1}).json()
    client.cookies.clear()
    login(client, "PC0387", "pw2")
    assert client.delete(f"/api/me/shares/{s['token']}").status_code == 404
    assert client.get(f"/api/me/shares/{s['token']}/qr.svg").status_code == 404


def test_log_detects_tampering(client):
    login(client, "PC0989", "pw1")
    client.post("/api/me/shares", json={"label": "Dr. A", "hours": 1})
    assert store.verify_log("PC0989")["ok"]
    store.con().execute("UPDATE audit SET actor='Nobody' WHERE seq=1")
    v = store.verify_log("PC0989")
    assert not v["ok"] and v["broken_at"] == 1


# ---------- emergency card ----------
def test_emergency_card_shows_only_essentials(client):
    login(client, "PC0989", "pw1")
    client.put("/api/me/profile", json={"contact_name": "Asha", "contact_phone": "+1 416 555 0100"})
    j = client.get("/api/me/emergency").json()
    tok = j["link"]["token"]
    card = TestClient(app).get(f"/api/emergency/{tok}").json()
    assert card["blood_group"] == "B-" and card["contact_name"] == "Asha" and card["medicines"][0]["name"] == "Metformin XR"
    assert "labs" not in card and "history" not in card
    new = client.post("/api/me/emergency/renew").json()["link"]["token"]
    assert new != tok and TestClient(app).get(f"/api/emergency/{tok}").status_code == 410
    assert any(e["action"] == "Opened your emergency card" for e in client.get("/api/me/log").json()["entries"])


# ---------- medicine check-in ----------
def test_dose_log_and_reminder(client):
    login(client, "PC0989", "pw1")
    assert client.post("/api/me/doses", json={"med": "Metformin XR", "day": "2026-11-18", "status": "taken"}).status_code == 200
    assert client.post("/api/me/doses", json={"med": "Aspirin", "day": "2026-11-18", "status": "taken"}).status_code == 400
    log = client.get("/api/me/doses?since=2026-11-01").json()["log"]
    assert log == [{"day": "2026-11-18", "med": "Metformin XR", "status": "taken"}]
    ics = client.get("/api/me/reminder.ics?time=08:30").text
    assert "RRULE:FREQ=DAILY" in ics and "T083000" in ics and "Metformin XR" in ics


# ---------- medical documents ----------
PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF"


def test_upload_view_share_delete_document(client):
    login(client, "PC0989", "pw1")
    r = client.post("/api/me/documents", files={"file": ("HbA1c report.pdf", PDF, "application/pdf")},
                    data={"title": "July blood test", "kind": "Lab report", "doc_date": "2026-07-10"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["title"] == "July blood test" and d["mime"] == "application/pdf"
    assert client.get("/api/me/documents").json()["documents"][0]["id"] == d["id"]
    f = client.get(f"/api/me/documents/{d['id']}")
    assert f.content == PDF and f.headers["x-content-type-options"] == "nosniff"
    # the doctor sees and opens it through a share link; the opening is logged
    s = client.post("/api/me/shares", json={"label": "Dr. Shah", "hours": 1, "approval": False}).json()
    doc = TestClient(app)
    assert TestClient(app).get(f"/api/share/{s['token']}/documents/{d['id']}").status_code == 401  # link alone isn't enough
    v = doc.post(f"/api/share/{s['token']}/open", json={"viewer": "Dr. Shah", "code": s["code"]}).json()
    assert v["documents"][0]["title"] == "July blood test" and v["scenarios"]["metabolic"]["status"] == "worsening"
    assert doc.get(f"/api/share/{s['token']}/documents/{d['id']}").content == PDF
    assert client.get("/api/me/log").json()["entries"][0]["action"] == "Opened a document"
    # another patient can't reach it
    other = TestClient(app)
    login(other, "PC0387", "pw2")
    assert other.get(f"/api/me/documents/{d['id']}").status_code == 404
    assert client.delete(f"/api/me/documents/{d['id']}").status_code == 200
    assert client.get("/api/me/documents").json()["documents"] == []


def test_upload_rejects_non_documents(client):
    login(client, "PC0989", "pw1")
    r = client.post("/api/me/documents", files={"file": ("x.pdf", b"<html><script>alert(1)</script>", "application/pdf")})
    assert r.status_code == 415


# ---------- secure doctor access ----------
def test_link_without_right_code_shows_nothing_and_locks(client):
    login(client, "PC0989", "pw1")
    s = client.post("/api/me/shares", json={"label": "Dr. A", "hours": 1, "approval": False}).json()
    doc = TestClient(app)
    for i in range(4):
        r = doc.post(f"/api/share/{s['token']}/open", json={"viewer": "Someone", "code": "000000" if s["code"] != "000000" else "111111"})
        assert r.status_code == 401 and "labs" not in r.text
    wrong = "000000" if s["code"] != "000000" else "111111"
    assert doc.post(f"/api/share/{s['token']}/open", json={"viewer": "Someone", "code": wrong}).status_code == 423
    # locked for good, even with the right code
    assert doc.post(f"/api/share/{s['token']}/open", json={"viewer": "Dr. A", "code": s["code"]}).status_code == 410
    assert any(e["action"] == "Link locked" for e in client.get("/api/me/log").json()["entries"])


def test_patient_approval_flow(client):
    login(client, "PC0989", "pw1")
    s = client.post("/api/me/shares", json={"label": "Dr. B", "hours": 1}).json()  # approval is on by default
    doc = TestClient(app)
    p = doc.post(f"/api/share/{s['token']}/open", json={"viewer": "Dr. Bose", "role": "Doctor", "code": s["code"]}).json()
    assert p["pending"] and "labs" not in p
    claim = lambda: doc.post(f"/api/share/{s['token']}/requests/{p['request']}", json={"secret": p["secret"]})
    assert claim().json() == {"pending": True}
    assert doc.post(f"/api/share/{s['token']}/requests/{p['request']}", json={"secret": "guess"}).status_code == 404
    reqs = client.get("/api/me/requests").json()
    assert reqs[0]["viewer"] == "Dr. Bose"
    client.post(f"/api/me/requests/{reqs[0]['id']}", json={"approve": True})
    v = claim().json()
    assert v["id"] == "PC0989"
    assert claim().status_code == 409  # one approval = one opening


def test_patient_can_deny(client):
    login(client, "PC0989", "pw1")
    s = client.post("/api/me/shares", json={"label": "Dr. C", "hours": 1}).json()
    doc = TestClient(app)
    p = doc.post(f"/api/share/{s['token']}/open", json={"viewer": "Stranger", "code": s["code"]}).json()
    client.post(f"/api/me/requests/{p['request']}", json={"approve": False})
    assert doc.post(f"/api/share/{s['token']}/requests/{p['request']}", json={"secret": p["secret"]}).status_code == 403


def test_new_code_replaces_old(client):
    login(client, "PC0989", "pw1")
    s = client.post("/api/me/shares", json={"label": "Dr. D", "hours": 1, "approval": False}).json()
    new = client.post(f"/api/me/shares/{s['token']}/code").json()["code"]
    doc = TestClient(app)
    if new != s["code"]:
        assert doc.post(f"/api/share/{s['token']}/open", json={"viewer": "Dr. D", "code": s["code"]}).status_code == 401
    assert doc.post(f"/api/share/{s['token']}/open", json={"viewer": "Dr. D", "code": new}).json()["id"] == "PC0989"


def test_security_headers(client):
    h = client.get("/").headers
    assert h["x-frame-options"] == "DENY" and h["referrer-policy"] == "no-referrer"
    assert "frame-ancestors 'none'" in h["content-security-policy"]
    assert client.get("/api/health").headers["cache-control"] == "no-store"


# ---------- new patients: sign-up, results from reports, scenario judgment ----------
from pathlib import Path
from app import newpatients

REPORTS = Path(__file__).parent / "sample_reports"


def test_read_values_from_lab_reports():
    m = newpatients.find_values(newpatients.extract_text((REPORTS / "lab_march.pdf").read_bytes(), "application/pdf"))
    v = {x["test"]: x["value"] for x in m["values"]}
    assert m["date"] == "2026-03-12" and v["HbA1c"] == 5.8
    assert round(v["Fasting glucose"]) == 106 and round(v["LDL cholesterol"]) == 135  # converted from mmol/L
    o = newpatients.find_values(newpatients.extract_text((REPORTS / "lab_october.pdf").read_bytes(), "application/pdf"))
    assert o["date"] == "2026-10-02" and {x["test"]: x["value"] for x in o["values"]}["Vitamin D"] == 24


def test_value_wording_and_units():
    f = lambda t: {x["test"]: x["value"] for x in newpatients.find_values(t)["values"]}
    assert f("HbA1c: 48 mmol/mol")["HbA1c"] == 6.54
    assert f("Glycated haemoglobin 6.1 %\nHemoglobin 14.2 g/dL") == {"HbA1c": 6.1, "Hemoglobin": 14.2}
    assert f("Hemoglobin 139 g/L")["Hemoglobin"] == 13.9


def _new_patient(client, sex="Female", **kw):
    body = {"password": "longpassword1", "age": 47, "sex": sex, "conditions": ["prediabetes"], "family": ["heart"]} | kw
    r = client.post("/api/register", json=body)
    assert r.status_code == 200, r.text
    return r.json()["id"]


def test_register_then_sign_in(client):
    pid = _new_patient(client)
    assert pid.startswith("NP") and client.get("/api/me").json()["is_new"]
    client.cookies.clear()
    assert login(client, pid, "longpassword1").status_code == 200
    assert client.post("/api/register", json={"password": "short", "age": 40, "sex": "Male"}).status_code == 422


def test_upload_reports_and_judge_all_three(client):
    pid = _new_patient(client, meds=[{"name": "Metformin", "dose": "500 mg", "start": "2026-05-01"}])
    me = client.get("/api/me").json()
    assert me["scenarios"]["metabolic"]["status"] == "not_enough" and me["scenarios"]["cardio"]["status"] == "not_enough"
    for f in ("lab_march.pdf", "lab_october.pdf"):
        up = client.post("/api/me/documents", files={"file": (f, (REPORTS / f).read_bytes(), "application/pdf")}).json()
        items = [{"test": v["test"], "value": v["value"], "date": up["found"]["date"]} for v in up["found"]["values"]]
        assert client.post("/api/me/results", json={"items": items, "source": f}).status_code == 200
    client.post("/api/me/results", json={"items": [{"test": "Period start", "value": 0, "date": d} for d in
                                                   ("2026-06-01", "2026-07-14", "2026-08-29", "2026-10-10")]})
    me = client.get("/api/me").json()
    s = me["scenarios"]
    assert s["metabolic"]["status"] == "worsening" and "HbA1c" in s["metabolic"]["above_target"]
    assert s["cardio"]["status"] == "improving_above_target"
    assert s["pcos"]["status"] == "worsening" and me["cycles"]["mean"] > 35
    assert any(e["kind"] == "response" and e["name"] == "Metformin" for e in s["metabolic"]["evidence"])
    assert not any(e["kind"] == "response" for e in s["cardio"]["evidence"])
    assert "HbA1c went from 5.8 to 6.3" in me["ai"]["rule_text"]
    # the AI checks accept numbers from the new patient's own evidence
    t = f"Your HbA1c went from 5.8% to 6.3%. {EN}"
    assert all(c["passed"] for c in ai.checks(t, me["ai"]["evidence"], "en"))


def test_results_validation_and_ownership(client):
    _new_patient(client, sex="Male")
    assert client.post("/api/me/results", json={"items": [{"test": "Magic", "value": 1, "date": "2026-01-01"}]}).status_code == 400
    assert client.post("/api/me/results", json={"items": [{"test": "HbA1c", "value": 6, "date": "2099-01-01"}]}).status_code == 400
    client.post("/api/me/results", json={"items": [{"test": "HbA1c", "value": 6.0, "date": "2026-01-01"}]})
    rid = client.get("/api/me/results").json()["results"][0]["id"]
    assert client.get("/api/me").json()["scenarios"]["pcos"] is None  # PCOS never applies to men
    other = TestClient(app)
    login(other, "PC0989", "pw1")
    assert other.get("/api/me/results").status_code == 403  # dataset patients' results come from PranaChain
    assert other.delete(f"/api/me/results/{rid}").status_code == 403
    assert client.delete(f"/api/me/results/{rid}").status_code == 200
