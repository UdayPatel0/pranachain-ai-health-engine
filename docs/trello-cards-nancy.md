# Trello cards: Nancy (Frontend & UX), Sprint 4

Board: **PranaChain AI Health Intelligence Engine (Group 1)**. Format follows the team brief: title, labels,
due date (sprint end), description, checklist, research notes, links. Paste the GitHub commit link into each card
once pushed.

---

## Card 1 · Test the web demo on laptop and phone
**List:** Review (move to Done after the team looks) · **Labels:** Nancy, Frontend · **Due:** sprint end

**Description:** Test the web demo (fixes go in the new page web/demo-v0.5.html; web/index.html stays unchanged) on a laptop (1366×768) and a phone (iPhone 13 size) so the partner demo
works on both. Every bug found becomes its own card.

**Checklist**
- [x] Write an automated test (`web/tests/ui_check.mjs`) for 7 steps: cohort, patient, explain, body system, next/prev, unknown ID, blocked state
- [x] Run on laptop and phone, save screenshots (`docs/testing/screenshots/`)
- [x] Check for horizontal scrolling, JavaScript errors, tap targets < 44 px
- [x] Write the report (`docs/testing/web-demo-test-report.md`)
- [x] Add one Trello card per bug (cards B1–B8 below)
- [ ] Check by hand on a real iPhone (Safari) and Android (Chrome)

**Research notes:** 7/7 steps pass on both sizes after fixes. 8 bugs found, 5 fixed. Apple and WCAG advise 44 px
minimum tap targets. Test uses Chromium with phone emulation, so a real-phone check is still needed.

**Links:** commit: _paste here_

---

## Card 2 · Add "Explain in plain words" button on the patient page
**List:** Review · **Labels:** Nancy, Frontend, AI · **Due:** sprint end

**Description:** A button on the patient overview that shows the AI's explanation of the evidence in everyday
words. Uses Rishi's endpoint when it is running; until then a rule-based preview is shown with a clear label.

**Checklist**
- [x] Shared module `web/explain.js`: evidence summary, preview explanation, call to `/patients/{id}/explanation`
- [x] Panel under the scenario evidence, above Body systems
- [x] Label showing "AI answer" or "Preview · AI not connected yet"
- [x] Bigger text and Read aloud buttons
- [x] Blocked state when a safety check fails (test with `?demo=unsafe`)
- [x] Same panel in the React app
- [ ] Connect to Rishi's endpoint when ready and test 3 patients

**Research notes:** API contract agreed in `docs/ai-explanation-panel.md`. The LLM input is `buildEvidence(patient)`
so both sides check numbers against the same facts.

**Links:** commit: _paste here_

---

## Card 3 · Check the AI's words are easy for patients to understand
**List:** Review · **Labels:** Nancy, AI, Frontend · **Due:** sprint end

**Description:** Every explanation is checked for reading level and medical words before it is shown, plus the
3 safety checks (numbers match evidence, no diagnosis words, disclaimer).

**Checklist**
- [x] Readability check: reading grade ≤ 8, ≤ 20 words per sentence, medical words only in brackets after a plain name
- [x] Plain names list (e.g. HbA1c → "average blood sugar (HbA1c)")
- [x] Safety checks run in the browser on every answer
- [x] 7 unit tests (`node --test web/tests/explain.test.mjs`)
- [x] Run on all 900 patients (`web/tests/check_explanations.mjs`), report in `docs/testing/readability-report.md`
- [ ] Rerun on Rishi's AI answers with `--ai` when available

**Research notes:** NIH and AMA advise patient materials at grade 6–8. Preview results: 900/900 safe,
900/900 easy to read, median grade 1.9, hardest grade 6.7.

**Links:** commit: _paste here_

---

## Card 4 · Design the AI explanation panel
**List:** Review · **Labels:** Nancy, Frontend, Docs · **Due:** sprint end

**Description:** Where the explanation appears and how a failed safety check is shown. Keeps the plain-language
and accessibility ideas from prototype v0.1.

**Checklist**
- [x] Placement decided: patient overview, under the evidence
- [x] States designed: before, loading, passed, blocked, AI down
- [x] Failed check: text hidden, red box, reason listed, evidence stays visible
- [x] Written up in `docs/ai-explanation-panel.md`
- [ ] Show to the team at the weekly meeting

**Links:** commit: _paste here_

---

## Card 5 · React patient overview screen
**List:** Review · **Labels:** Nancy, Frontend · **Due:** sprint end

**Description:** Start the React app (Vite) and rebuild the patient overview from web/index.html as components
that read the same JSON.

**Checklist**
- [x] Vite + React app in `frontend/` (`npm run dev`)
- [x] Reads web/data/index.json and chunks/*.json
- [x] Components: PatientNav, PatientHeader, ScenarioCard, EvidenceItem, ExplainPanel, BodySystemsList
- [x] Patient ID in the URL (`#/patient/PC0989`)
- [x] Tested on laptop and phone: no horizontal scroll, no errors, 44 px tap targets
- [ ] Next sprint: cohort view, body-system detail, 3D body component

**Links:** commit: _paste here_

---

## Bug cards (from the test)

| Card | List | Labels |
|---|---|---|
| B1 · Unknown patient ID shows no message | Done (fixed) | Nancy, Frontend |
| B2 · Tap targets under 44 px on phone (chips, back link, ‹ ›) | Done (fixed) | Nancy, Frontend |
| B3 · Empty 3D box when Three.js / WebGL cannot load | Done (fixed) | Nancy, Frontend |
| B4 · Phone: patient details start below the 3D body | In progress (partly fixed; full fix in React) | Nancy, Frontend |
| B5 · Scenario bar segments too small to tap on phone | Backlog | Nancy, Frontend |
| B6 · Read aloud continues after switching patient | Done (fixed) | Nancy, Frontend |
| B7 · Page depends on 3 CDNs (fonts, Three.js) | Backlog | Nancy, Frontend |
| B8 · 1.6 MB download to open the first patient on mobile | Backlog | Kamran, Rishi, Data |

## Backlog cards with Nancy's name (from the brief)

- Sprint 5 · React app: cohort view, patient view, body systems, lab charts · Nancy
- Sprint 6 · Patient and doctor views; plain-language help; accessibility check · Nancy
- Sprint 6 · Life events and fasting/season awareness on real data · Uday, Nancy
- Sprint 7 · Multi-language explanations (English + Hindi + Gujarati) · Rishi, Nancy
- Doctor view and printable summary · Nancy
