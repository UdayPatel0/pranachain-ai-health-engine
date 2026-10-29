# VitaLens demo script: PranaChain meeting (real data, about 5 minutes)

Demo: `web/` served locally (`py -m http.server 8000` → http://localhost:8000), or the published link.

## 1. Uday: opening and scenarios (1 min 30 s)
- Last meeting's feedback: focus on the three scenarios and go beyond basic metrics. This week VitaLens ran on PranaChain's real data.
- Each patient is compared with their own first 3 months, changes are linked to clinical history, and nothing is diagnosed.
- Patients per scenario: 539 metabolic, 493 cardiovascular, 21 PCOS, each with a worsening, mixed or improving status.
- Example PC0989 (open it, then tap the pancreas): prediabetes, metformin from January. Fasting glucose improved, but HbA1c rose from 5.67% to 6.62%, triglycerides and ALT rose, and about 82% of doses were taken.

## 2. Kamran: data and audit (1 min)
- 900 workbooks loaded. PC0201–PC0300 not received.
- 11 sheets per workbook (not 9): 657k daily readings, 61k lab results.
- Audit: 3 date formats, lab units written two ways, about 5–6% of daily values missing (kept missing, never filled). 0 impossible values, 0 duplicate days.

## 3. Rishi: evidence and medicine responses (1 min)
- Atorvastatin: LDL down about 10 mg/dL (77% of patients). Metformin: fasting glucose down.
- Amlodipine: no change in home BP. Ask whether this is expected.
- Only stress ↔ sleep is clearly linked (507 patients). Other daily pairs show no link, so only statistically clear links are shown.
- Next: evidence summaries feed the AI explanation step, with checks (numbers must match, no diagnosis words).

## 4. Nancy: interface and PCOS (1 min)
- The 3D body glows where something got worse. Tapping a part shows real labs, trends and medicines.
- PC0560 (tap the ovaries): 8 of 10 cycles longer than 35 days.
- 7 patients have long cycles but no PCOS diagnosis. These are worth reviewing, not diagnosing.
- Ask the partner to pick any patient ID.

## 5. Uday: close (30 s)
- One framework, three scenarios, evidence from real data. Built with AI assistance (cited in the README).
- Questions for PranaChain: Is the amlodipine result expected? Which scenario should we prioritise? Can we get PC0201–PC0300?

## Next tasks (one GitHub issue each)
| Member | Task |
|---|---|
| Uday | Understand and tune the `analysis.py` scenario rules and change limits |
| Kamran | Verify `loader.py`, load PC0201–PC0300, start moving to PostgreSQL |
| Rishi | Check 5 patients' medicine results by hand; start the AI explanation step with safety checks |
| Nancy | Test `web/index.html` on laptop and phone; start a React version of one screen |
