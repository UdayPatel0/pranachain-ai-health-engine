# VitaLens v1.0: demo for the PranaChain founder (about 7 minutes)

**One line:** PranaChain gives people ownership of their health records. VitaLens makes that record *understandable*, *shareable in seconds*, and *useful in an emergency*, with AI that can't make things up.

## Before the demo (5 minutes)

1. Open the Ollama app (or set a Claude key in `.env`).
2. Start VitaLens: `start_demo.bat` (or `.\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000`).
3. Open http://127.0.0.1:8000/api/health: it should say `"provider":"ollama"` (or `anthropic`).
4. Sign in once as **PC0989 / vitalens-demo** and click **Explain** once, so the AI model is warmed up.
5. Have a phone ready on the same Wi-Fi (optional: start with `--host 0.0.0.0` and use the laptop's IP so the QR codes open on the phone).

## The story

| # | Time | Show | Say |
|---|---|---|---|
| 1 | 30 s | Sign-in screen | "Abhishek, you built PranaChain on one idea: *your health records belong to you*. We asked: once people own their records, what do they actually *do* with them?" |
| 2 | 1 min | Home: "2 areas got worse this year", body map, Blood sugar | "This is a 60-year-old man from your data. His HbA1c went from 5.70 to 6.46% after he started Metformin. He's compared with *his own* usual, not population averages." |
| 3 | 1 min 30 s | **Explain** → click a small number ¹ | "The AI explains his year in plain words, in 5 languages including Hindi and Gujarati. Every sentence has a number: click it and you see the exact reading it came from. And three checks run before anything is shown: numbers must match his data, no diagnosis, a doctor reminder. If it fails, the patient never sees it." |
| 4 | 1 min 30 s | **Your data, your control** → "Dr. Shah", 1 day → **Create link** → QR. Open the link (second window or phone), type "Dr. Priya Shah" → full clinical view | "Share with any doctor in seconds: your promise, working. The doctor gets labs with reference ranges, trends, medicines and how often they were taken, in a printable view." |
| 5 | 1 min | Back to patient → **Who saw my record**: "Dr. Priya Shah (Doctor) viewed your record", green **Tamper-proof** badge → **Stop sharing** → doctor refreshes: "link not available" | "*See exactly who accessed it and when.* Every entry carries the fingerprint of the one before it, the same chaining idea as your blockchain. If anyone edits the log, the badge turns red. Here it's a local ledger; in production these fingerprints anchor on PranaChain." |
| 6 | 1 min | **Show my emergency card** → set contact → switch card to Gujarati → scan QR with phone → Spanish | "You told the story of falling ill in another city or country. This is for that moment. One QR on the lock screen. A paramedic in Mexico sees blood group, allergies, medicines and who to call, in Spanish, and nothing else. The patient sees that it was opened." |
| 7 | 30 s | **Did you take your medicines today?** → Taken → calendar reminder | "Fourteen-day strip, daily reminder in their own calendar. Now when HbA1c goes up, the doctor can tell whether the medicine isn't working or the doses were missed." |
| 8 | 30 s | Close | "Understand, share, stay safe, stay on track: four reasons to open PranaChain every week, not once a year. Next: test with 5 real users, connect to PranaChain's API, and anchor the access log on-chain." |

## If something goes wrong

- **AI is slow or says it isn't running:** open the Ollama app; the rule-based summary still shows, and every other feature works without AI.
- **Port 8000 in use:** add `--port 8001` and use that address.
- **A QR opens nothing on the phone:** the server was started on 127.0.0.1. Restart with `--host 0.0.0.0`, or open the link on the laptop instead.

## Likely questions

- **Is this on the blockchain?** The log uses the same hash-chain idea and can be verified; anchoring the chain head on PranaChain is the next step (one hash per patient per day).
- **Can the AI invent numbers?** Any number not in the patient's data blocks the answer. We tested this in `tests/test_vitalens.py`.
- **Who can see the emergency card?** Only someone with the QR, only those fields, and every opening is logged. The patient can replace the QR any time.
- **Is the data real?** No: PranaChain's synthetic dataset, 900 patients.
