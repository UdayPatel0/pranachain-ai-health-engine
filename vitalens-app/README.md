# VitaLens

VitaLens helps a patient understand a year of their own health data in plain words. It compares their readings with their own usual, shows what changed since they started a medicine, and uses AI to explain the results and answer questions: a **free local model through Ollama** by default, or **Claude** if you have an API key. Every AI answer is checked before it is shown.

## Security for doctor sharing (v1.2)

A doctor link alone shows nothing. To see the record a doctor needs:

1. **The link** (time-limited, can be stopped any time).
2. **A 6-digit access code**, shown to the patient once when the link is made and given to the doctor separately (said aloud or texted, never with the link). Stored only as a hash. **5 wrong codes switch the link off.** The patient can make a new code any time.
3. **The patient's approval** (on by default): after the right code, the patient sees "Dr. X wants to see your record" with **Approve / Deny**. The doctor's page waits and opens only when approved. One approval = one opening.
4. **A viewer session** for that browser only (signed, HttpOnly cookie, limited to that link, ends with the link or after 4 hours). Documents open only in that browser, so a forwarded link can't download them.

Every request, approval, denial, wrong code, lock, view and document opening goes into the patient's tamper-evident access log. All pages send security headers: no embedding in other sites (`frame-ancestors 'none'`, `X-Frame-Options: DENY`), `Referrer-Policy: no-referrer` (share links never leak to other sites), a Content-Security-Policy, `nosniff`, and `no-store` on all API answers.

Still to do before real patients: verified doctor identities (e.g. through PranaChain or a licensing body), HTTPS hosting, two-factor sign-in for patients, encryption of the database and uploads.

## What's new in v1.1

- **The three main health checks come first.** The Overview opens with PranaChain's three scenarios: blood sugar & metabolism (type 2 diabetes risk), heart & blood pressure, and hormones & cycle (PCOS). Each shows whether it is getting worse, getting better, mixed or steady, with the key readings. Tap one for the full details: why it's on your record, what changed (with charts and normal ranges), what changed since starting a medicine, and questions for the doctor.
- **Upload medical documents.** Patients can upload lab reports, prescriptions and scans (PDF, JPG, PNG or WebP, up to 10 MB), open, download or delete them. Doctors with a share link can open them, and every opening goes into the access log.
- **Cleaner layout.** Five tabs (Overview, Ask & explain, Medicines, Documents, Sharing & safety) instead of one long page; lighter cards; works on phones and in dark mode.
- **More demo patients** (password `vitalens-demo`): PC0989 (blood sugar worse), PC0431 (blood sugar improving, heart worse), PC0466 (blood sugar and PCOS worse), PC0588 (both improving), PC0387, PC0560.

## What's new in v1.0

- **Your data, your control:** share your record with a doctor through a time-limited, revocable link or QR code. The doctor gets a printable clinical view.
- **Who saw my record:** every sign-in, share, doctor view and emergency scan goes into a hash-chained, tamper-evident access log. A green badge shows the chain is intact; any edit turns it red.
- **Emergency travel card:** blood group, allergies, conditions, medicines and emergency contact, in 5 languages, behind a QR for your lock screen. Strangers see only the card, and each scan is logged.
- **AI answers with sources:** every sentence of an AI answer links to the exact readings it came from.
- **Medicine check-in:** tap Taken or Missed each day, see a 14-day strip, and add a daily reminder to your calendar.

Demo walkthrough for PranaChain: [docs/demo-script.md](docs/demo-script.md)

Built on PranaChain's 900 synthetic patients (IDs PC0001–PC1000; PC0201–PC0300 are not in the data).

## Run it

**Windows:** double-click `start_demo.bat`
**Mac / Linux:** `./start_demo.sh`

The first run installs everything (Python 3.10+ needed), creates demo accounts and opens http://localhost:8000.

| Demo sign-in | Password | What you'll see |
|---|---|---|
| PC0989 | vitalens-demo | 60, male: blood sugar rising after starting Metformin XR |
| PC0387 | vitalens-demo | 71, female: LDL cholesterol rising after starting Atorvastatin |
| PC0560 | vitalens-demo | Another sample patient |
| PC0431 | vitalens-demo | 51, female: blood sugar improving, heart getting worse |
| PC0466 | vitalens-demo | 42, female: blood sugar and PCOS both getting worse |
| PC0588 | vitalens-demo | 22, female: blood sugar and PCOS both improving |

### Turn on the AI (free)

1. Install Ollama from https://ollama.com/download (Windows, Mac or Linux) and open it once.
2. In a terminal, download the model (about 2 GB, one time):
   ```
   ollama pull llama3.2
   ```
3. Make sure `.env` has `AI_PROVIDER=ollama` (this is the default in `.env.example`).
4. Restart VitaLens. http://localhost:8000/api/health should show `"provider":"ollama"`.

Answers take 10–60 seconds on a normal laptop. More RAM? Use `OLLAMA_MODEL=llama3.1:8b` or `qwen2.5:7b` for better answers (run `ollama pull` for that model first).

**Claude instead (paid, best quality):** set `AI_PROVIDER=anthropic` and `ANTHROPIC_API_KEY=sk-ant-...` from https://console.anthropic.com.

**No AI:** `AI_PROVIDER=rule-based`. Everything else still works and "Explain my year" shows the rule-based summary.

### Manual setup

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                    # add your key
python scripts/create_accounts.py --demo
uvicorn app.main:app --port 8000
```

## What's inside

```
app/
  main.py     FastAPI server: sign-in, the person's own record, AI routes, serves the web app
  ai.py       Prompts, Ollama + Claude providers, the 3 safety checks, retry with reasons, rule-based fallback
  auth.py     PBKDF2 password hashes, signed session cookie, sign-in rate limit
  data.py     Loads the 900 processed patient records
  store.py    SQLite: share links, hash-chained access log, medicine check-ins, emergency contact
  records.py  Exactly what a doctor link and an emergency QR are allowed to show
web/index.html      The patient app (body map, areas, medicines, Explain, Ask, sharing, access log, emergency card, check-in)
web/doctor.html     What the doctor sees after opening a share link
web/emergency.html  The public emergency card page behind the QR code
web/card.js         Emergency card layout and its 5 languages
data/           index.json + chunks/*.json (processed PranaChain records)
scripts/create_accounts.py   Create logins
tests/          pytest: safety checks, sign-in, AI routes (no key needed)
```

## API

| Route | What it does |
|---|---|
| `GET /api/health` | Server status and which AI is active (`ollama`, `anthropic` or `rule-based`) |
| `POST /api/login` `{id, password}` | Signs in; sets an HttpOnly cookie |
| `POST /api/logout` | Signs out |
| `GET /api/me` | The signed-in person's record only |
| `GET /api/me/explain?lang=en&notes=[...]` | "Explain my year": AI text + check results |
| `POST /api/me/ask` `{question, lang, notes}` | "Ask VitaLens": AI answer + check results |

| `GET/POST /api/me/shares`, `DELETE /api/me/shares/{token}` | List, create, stop doctor links |
| `GET /api/me/shares/{token}/qr.svg` | QR code for a link |
| `GET /api/me/log` | Access log + chain verification |
| `GET /api/share/{token}`, `POST /api/share/{token}/open` | Doctor side: name + access code; returns the record, or a pending request |
| `POST /api/share/{token}/requests/{id}` | Doctor's page checks whether the patient approved |
| `GET /api/me/requests`, `POST /api/me/requests/{id}` | Patient sees and approves/denies requests |
| `POST /api/me/shares/{token}/code` | New access code |
| `GET /api/me/emergency`, `PUT /api/me/profile`, `POST /api/me/emergency/renew` | Emergency card, contact, replace QR |
| `GET /api/emergency/{token}` | Public emergency card (logged) |
| `GET/POST /api/me/doses`, `GET /api/me/reminder.ics` | Medicine check-in and calendar reminder |
| `GET/POST /api/me/documents`, `GET/DELETE /api/me/documents/{id}` | Upload, list, open and delete medical documents |
| `GET /api/share/{token}/documents/{id}` | Doctor opens a document (logged) |

Interactive docs: http://localhost:8000/api/docs

**Opening links on a phone:** start with `--host 0.0.0.0` and open the app using your laptop's IP address (for example http://192.168.1.20:8000), so the links inside the QR codes work on other devices on the same Wi-Fi.

## How the AI stays safe

1. **Evidence only.** The AI receives only that person's evidence summary (no other patients) plus the notes they wrote.
2. **Three checks on every answer:** numbers must match the data; no diagnosis or medicine instructions ("you have diabetes", "stop taking metformin"); the doctor reminder must be there.
3. **Retry, then block.** If a draft fails, the AI gets the reasons and tries again (up to 3 times). If it still fails, nothing is shown.
4. **Limits.** 40 AI calls per person per hour (`AI_CALLS_PER_HOUR`), 5 failed sign-ins per 10 minutes, explanations cached.

Languages: English, Hindi, Gujarati, Spanish, French.

## Accounts

```bash
python scripts/create_accounts.py --demo                          # PC0989, PC0387, PC0560 / vitalens-demo
python scripts/create_accounts.py --ids PC0412 --password secret1 # one person
python scripts/create_accounts.py                                  # everyone, random passwords
```

Passwords are stored only as hashes in `data/accounts.json`. New plain passwords go to `accounts_for_team.csv`: share privately, then delete it.

## Tests

```bash
python -m pytest -q
```

## Settings (`.env`)

| Name | Default | |
|---|---|---|
| `AI_PROVIDER` | `ollama` | `ollama` (free, local), `anthropic` (Claude) or `rule-based` |
| `OLLAMA_MODEL` | `llama3.2` | Any model you've pulled with `ollama pull` |
| `OLLAMA_URL` | `http://localhost:11434` | Where Ollama runs |
| `ANTHROPIC_API_KEY` | (empty) | For `AI_PROVIDER=anthropic` |
| `VITALENS_MODEL` | `claude-sonnet-5-5` | Claude model |
| `AI_CALLS_PER_HOUR` | 40 | Per person |
| `SESSION_SECRET` | auto | Cookie signing secret |
| `COOKIE_SECURE` | 0 | Set to 1 behind HTTPS |

## Next steps

User testing with 3–5 people · PostgreSQL instead of JSON files · password reset · HTTPS deployment.

*VitaLens does not diagnose. All AI text ends with a reminder to talk to a doctor.*
