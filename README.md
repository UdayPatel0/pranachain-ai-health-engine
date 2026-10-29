# VitaLens pipeline (COMP 8967 · Group 1 · PranaChain)

Loads PranaChain's synthetic patient workbooks, audits them, analyses every patient against
their own baseline, and exports results for the VitaLens web demo.

> Built with AI assistance (Claude, Anthropic) and reviewed by the team, as required by our team agreement.

## Run it

```bash
pip install -r requirements.txt
# put the unzipped workbooks under data/raw/ (any sub-folders, *.xlsx)
python run_pipeline.py --raw data/raw --db data/vitalens.db --out web/data
# view the demo (it reads web/data with fetch, so it needs a local server)
cd web && python -m http.server 8000   # then open http://localhost:8000
```

On 900 workbooks this takes about 2 minutes: around 70 s to load, 45 s to analyse.

## Repository layout

```
vitalens/          Python package: loader, analysis, export
run_pipeline.py    runs everything end to end
web/               demo website + generated results (web/data)
prototypes/        earlier demo versions (v0.1 languages, v0.2 scenarios, v0.3 3D body on sample data)
docs/              setup report, sprint deck, demo script
data/              put the raw workbooks here locally (not committed)
```

## Progress log

| Stage | What happened |
|---|---|
| Setup | Initial setup report submitted (problem, roles, scenarios, sprint plan) |
| Sprint 2 | Clickable prototypes on sample data: patient view in 5 languages, life events, season awareness (`prototypes/v0.1`) |
| Partner meeting 1 | Feedback: focus on the three validation scenarios and go beyond basic metrics |
| Sprint 3 | Three-scenario prototype (`v0.2`) and 3D body with advanced metrics (`v0.3`, sample data) |
| Sprint 3 | Real data: 900 PranaChain workbooks loaded, audited and analysed. Website on real data (`web/`) |

## What is in the code

| File | What it does | Owner (per report) |
|---|---|---|
| `vitalens/loader.py` | Reads all 11 sheets, converts dates (Excel numbers, dates and text), forces numbers, normalises lab units, flags missing and impossible values, writes SQLite | Kamran |
| `vitalens/analysis.py` | Personal baselines and trends, lab trajectories against reference ranges, medication responses, per-patient relationships, three scenario rules | Uday (detection), Rishi (evidence) |
| `vitalens/export.py` | Cohort summary and compact JSON per 100 patients for the web | Kamran / Rishi |
| `web/index.html` | Cohort view + 3D body patient view | Nancy |
| `run_pipeline.py` | Runs everything end to end | All |

SQLite is used for the prototype. The tables map directly onto the PostgreSQL schema in the report.

## Method (all per patient, no diagnosis)

- **Baseline:** the first 3 months (Sep–Nov 2025), compared with the last 3 months (Jun–Aug 2026).
  A change counts only if it passes a meaningful limit (for example 5 mmHg systolic, 2% of weight,
  15% of steps, 0.4 h of sleep) and holds in at least 2 of the last 3 months.
- **Labs:** first vs last values (averaging two when there are 4 or more results), checked against
  each test's own reference range from the workbook.
- **Medication response:** labs in the 150 days before a start vs results from 30 days after.
  Daily signals: 60 days before vs days 30–120 after.
- **Relationships:** 8 candidate links (for example stress → sleep, steps → next-day BP), kept only
  when p < 0.001 and |r| ≥ 0.2 for that patient.
- **Scenarios:**
  - Metabolic = glycemic history or recent HbA1c ≥ 5.7%.
  - Cardiovascular = hypertension or hyperlipidemia history, average home BP ≥ 130/80 in the first 3 months, or LDL ≥ 160.
  - PCOS = PCOS history, average cycle > 35 days, or 2 or more cycles > 35 days.
  - Status (worsening, mixed, improving, still above target, stable) comes from counting the evidence that got worse or better.

## Results on 900 patients (PC0201–PC0300 not received)

| Scenario | Patients | Worsening | Mixed | Improving, above target | Review | Improving | Stable |
|---|---|---|---|---|---|---|---|
| Metabolic | 539 | 82 | 123 | 166 | 103 | 47 | 18 |
| Cardiovascular | 493 | 72 | 156 | 211 | 52 | 2 | 0 |
| PCOS | 21 | 3 | 4 | 0 | 7 | 7 | 0 |

Medication responses (median across patients):

- Atorvastatin: LDL −10 mg/dL (198 patients, 77% down)
- Metformin: fasting glucose −3.75 mg/dL, weight −0.4 kg
- Ferrous sulfate: ferritin +15 ng/mL
- Cholecalciferol: vitamin D +8 ng/mL
- **Amlodipine: no change in home BP**

Relationships: stress → same-night sleep is clear in 507 patients (median r −0.25). Most other
day-to-day pairs (sleep → heart rate, steps → BP) show no link in this dataset.

## Data audit

- 11 sheets per workbook (the report said 9). Every file has the same sheets and columns.
- Dates in 3 formats: Excel numbers (344 files), text (56), real dates (rest). All converted.
- About 5–6% of daily cells are empty for every patient. Gaps are at most 10 days, and they are kept as missing.
- Lab units "10^9/L" vs "x10^9/L" (200 files). Normalised.
- 123 patients have no medication rows. 303 women have cycle data.
- 0 impossible values, 0 duplicate days.
- Cycle and history sheets reuse templates across patients (for example PC0303 = PC0603 cycles). Daily data and labs are unique.
