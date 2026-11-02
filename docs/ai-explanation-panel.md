# "Explain in plain words" panel: design and API contract

Owner: Nancy (Frontend & UX) · Sprint 4 · Built with AI assistance (Claude), reviewed by the team.
Code: `web/explain.js` (shared rules), `web/demo-v0.5.html` (HTML demo v0.5: a copy of `web/index.html` with the panel added; the original page is unchanged), `frontend/src/components/ExplainPanel.jsx` (React).

## Where it appears

On the patient overview, **directly under the scenario evidence and above Body systems**. The patient (or the
doctor sitting with them) reads the evidence first, then presses **Explain in plain words** to get the same facts
in everyday language. It is not shown on the cohort page, because explanations are always about one person.

## What the panel shows

| State | What the user sees |
|---|---|
| Before pressing | Title, one line on what it does, the button |
| Loading | "Writing the explanation…" (announced to screen readers) |
| Passed all safety checks | Large text (17 px, 20 px with **Bigger text**), one heading per area (Blood sugar and weight / Heart and blood pressure / Monthly cycle), short bullet sentences, the disclaimer in a yellow-edged box, **Read aloud**, **Explain again**, and the 4 check results underneath |
| Failed a safety check | The AI text is **not shown**. Red box: "This explanation was held back. It did not pass a safety check." Below it, which check failed and why. The evidence above stays visible. A "Team view" drop-down shows the blocked text for testing only |
| AI service down | The rule-based preview is shown with a grey "Preview · AI not connected yet" label and a small note |

A label next to the title always says where the words came from: **AI answer** (teal) or **Preview · AI not connected yet** (grey).

## The checks

Run in the browser on every answer, even if the backend already checked it (two layers of safety).

| Check | Rule | Fails when |
|---|---|---|
| Numbers match the evidence | Every number in the text must appear in the evidence summary (rounded to 0, 1 or 2 decimals), or be one of the fixed numbers 3, 12, 21, 35, 130, 80 (comparison window, cycle range, BP line) | The AI writes a value that is not in the data |
| No diagnosis or medicine-change words | Blocks words like diabetes, hypertension, PCOS, disease, diagnosed, and advice like "stop taking", "increase your dose" | The AI names a condition or gives dosing advice |
| Says it is not a diagnosis | Must contain "not a diagnosis" and mention a doctor or care team | Disclaimer missing |
| Easy to read | Reading grade ≤ 8 (ideal ≤ 6), ≤ 20 words per sentence, medical words only in brackets after a plain name, e.g. "average blood sugar (HbA1c)" | Too hard to read. Shown as a warning; it does not hide the text |

Results on all 900 patients with the preview: 900/900 pass safety, 900/900 pass readability, median grade 1.9
(`docs/testing/readability-report.md`).

## Accessibility (kept from prototype v0.1)

- Plain name first, medical word in brackets, so patients can match their lab report
- Atkinson Hyperlegible font, large line height, short sentences as bullets
- **Bigger text** and **Read aloud** buttons, 44 px tap targets
- Status is never colour only: every check has ✓ or ! and a written label
- Later sprint: Hindi and Gujarati versions (backlog card "Multi-language explanations")

## API contract for Rishi (FastAPI)

The frontend calls this when the page is opened with `?api=http://localhost:8001` (or `VITE_AI_API` in React):

```
GET /patients/{id}/explanation
```

Preferred response:

```json
{
  "model": "name of the LLM",
  "intro": "Here is what changed in your health data. …",
  "sections": [
    {"area": "Blood sugar and weight", "sentences": ["Your average blood sugar (HbA1c) went up from 5.7% to 6.5%.", "…"]}
  ],
  "disclaimer": "This is not a diagnosis. Please talk with your doctor or care team about these results.",
  "safety": {"pass": true, "checks": []}
}
```

A simpler `{"text": "...", "model": "..."}` also works. The input the LLM should get is exactly
`buildEvidence(patient)` from `web/explain.js` (open "Team view: evidence given to the AI" in the panel to see it),
so the numbers check on both sides uses the same facts. If the endpoint is down or slow (12 s), the preview is shown.

To test the blocked state without the AI: open the page with `?demo=unsafe`.
