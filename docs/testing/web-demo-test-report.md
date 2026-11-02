# Web demo test: laptop and phone (Sprint 4)

Owner: Nancy (Frontend & UX) · Tested 30 Oct 2026 · Built with AI assistance (Claude), reviewed by the team.

## What was tested

| | Laptop | Phone |
|---|---|---|
| Screen | 1366 × 768 | iPhone 13 size, 390 × 844, touch, 3× pixels |
| Browser | Chromium (Playwright) | Chromium with iPhone 13 emulation (Playwright) |
| Page | `web/demo-v0.5.html`: copy of `web/index.html` v0.4 + new "Explain in plain words" panel + the fixes below (`web/index.html` itself is unchanged) | same |

Steps (automated in `web/tests/ui_check.mjs`, screenshots in `docs/testing/screenshots/`):

1. Cohort view loads 900 patients
2. Open featured patient PC0989 (metabolic · worsening)
3. Press **Explain in plain words**
4. Open a body system (Pancreas & liver)
5. Next / previous patient
6. Type an unknown patient ID
7. Blocked state: `?demo=unsafe` adds a bad sentence and the panel must hold it back

Checked on every step: console errors, horizontal scrolling, and (phone) tap targets smaller than 44 px.

Run it again:

```bash
cd web && python -m http.server 8000           # terminal 1, then open http://localhost:8000/demo-v0.5.html
node web/tests/ui_check.mjs http://localhost:8000 docs/testing/screenshots   # terminal 2, from the repo root
```

## Result

All 7 steps pass on laptop and phone after the fixes below. No horizontal scrolling on either size. No JavaScript errors.

## Bugs found (each one is a Trello card)

| # | Bug | Where | Severity | Status |
|---|---|---|---|---|
| 1 | Typing an unknown patient ID (e.g. PC9999) and pressing Open did nothing, no message | Patient view, ID box | Medium | **Fixed**: red message under the box; IDs PC0201–PC0300 say "not received yet" |
| 2 | Tap targets too small on phone: body-system chips 29 px, "← overview" link 22 px, ‹ › buttons 30 px wide, Cohort/Patient switch 36 px (guideline is 44 px) | Patient view, header | Medium | **Fixed**: 44 px minimum on touch screens and narrow screens |
| 3 | When the 3D body cannot start (Three.js CDN blocked, or no WebGL) a 584 px empty dark box remains | Patient view, 3D stage | Medium | **Fixed**: box shrinks to the short message |
| 4 | On phone the patient's name and scenarios start below the 3D body (723 px down, past the first screen) | Patient view, phone | Medium | **Partly fixed**: 3D is 319 px tall on phones (was 430), details start at 611 px. Full fix in React: patient header above the 3D body on phones |
| 5 | Scenario bar segments on the cohort page are 34 px tall and some are only a few px wide, so they are hard to tap on a phone | Cohort, "Patients per scenario" | Low | Open: make the legend items tappable filters |
| 6 | "Read aloud" kept reading the previous patient after switching | New explain panel | Low | **Fixed**: speech stops when the patient changes |
| 7 | Page needs 3 outside sites (Google Fonts, cdnjs, jsDelivr). On a blocked network (some campus / hospital Wi-Fi) the fonts fall back and the 3D body is off | Whole page | Low | Open: bundle Three.js and fonts in the React app |
| 8 | Opening the first patient downloads a 1.6 MB file (100 patients per chunk), slow on mobile data | Data loading | Low | Open: one file per patient, or the FastAPI `/patients/{id}` endpoint (Kamran / Rishi) |

## Still to check by hand

The automated run uses Chromium with phone emulation. Before the partner demo, also check on real devices:

- [ ] iPhone Safari: pinch-zoom and drag on the 3D body, "Read aloud"
- [ ] Android Chrome: same
- [ ] Laptop Firefox and Safari
- [ ] Zoom the browser to 200%: nothing cut off
- [ ] Keyboard only: Tab through the patient page, Enter on "Explain in plain words"
