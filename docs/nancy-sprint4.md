# Sprint 4: Nancy (Frontend & UX)

Built with AI assistance (Claude), reviewed by Nancy. **All Sprint 4 work is in new files. No existing file was changed**
(`README.md`, `.gitignore`, `web/index.html` and the Python pipeline are exactly as before).

## New files

| File | What it does |
|---|---|
| `web/demo-v0.5.html` | Copy of `web/index.html` (v0.4) with the "Explain in plain words" panel and the fixes from the laptop/phone test |
| `web/explain.js` | Evidence summary for the AI, preview explanation, safety checks (numbers, diagnosis words, disclaimer), readability check |
| `web/tests/explain.test.mjs` | 7 unit tests for the safety and readability rules |
| `web/tests/check_explanations.mjs` | Runs the checks on all 900 patients and writes a report |
| `web/tests/ui_check.mjs` | Laptop + phone test with screenshots |
| `frontend/` | React (Vite) app: patient overview screen (see `frontend/README.md`) |
| `docs/ai-explanation-panel.md` | Panel design and API contract for the AI endpoint (for Rishi) |
| `docs/testing/` | Test report, readability report, screenshots |
| `docs/trello-cards-nancy.md` | Trello card text |

## Run it

```bash
cd web && python -m http.server 8000      # open http://localhost:8000/demo-v0.5.html  (the old page is still at /)
node --test web/tests/explain.test.mjs    # from the repo root, Node 18+
node web/tests/check_explanations.mjs --report docs/testing/readability-report.md
cd frontend && npm install && npm run dev # React app at http://localhost:5173
```

Add `?demo=unsafe` to the page address to see what happens when a safety check fails.
When the team agrees, the panel can be moved into `web/index.html`; until then both pages work side by side.
