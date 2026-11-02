# VitaLens React app (Sprint 4: patient overview)

Owner: Nancy (Frontend & UX) · Built with AI assistance (Claude), reviewed by the team.

The start of the React version of `web/index.html`. This sprint rebuilds the **patient overview** screen as
components. It reads the same JSON as the HTML demo (`web/data/index.json` and `web/data/chunks/*.json`) and uses
the same safety and readability rules (`web/explain.js`).

## Run it

```bash
cd frontend
npm install
npm run dev          # open http://localhost:5173/#/patient/PC0989
npm run build        # production build in frontend/dist
```

Options in the address bar:

- `#/patient/PC0412` opens a patient (shareable link)
- `?api=http://localhost:8001` uses Rishi's AI endpoint for the explanation (otherwise the preview is shown)
- `?demo=unsafe` shows what happens when a safety check fails

## Components

```
src/App.jsx                         loads the index, reads the patient ID from the URL
src/lib/data.js                     loadIndex(), loadPatient(id): swap to FastAPI in Sprint 5
src/lib/model.js                    status labels, body systems, systemStatus(): same rules as web/index.html
src/components/PatientOverview.jsx  the screen
  PatientNav.jsx                    ID box, Open, previous / next, message for unknown IDs
  PatientHeader.jsx                 ID · age · sex, family history, data completeness
  ScenarioCard.jsx + EvidenceItem   one card per scenario with its evidence lines
  ExplainPanel.jsx                  "Explain in plain words" (design: docs/ai-explanation-panel.md)
  BodySystemsList.jsx               10 body systems with worse / note / ok / no-data dot
```

## Next (Sprint 5 card)

Cohort view, body-system detail with lab charts, the Three.js 3D body as a component, patient header above
the 3D body on phones (test bug #4).
