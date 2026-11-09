# Medicine results: hand check (5 patients)

Owner: Rishi · Task: check 5 patients' medicine results by hand against the raw workbooks, not against the pipeline.

## How the pipeline works it out (`med_responses` in `vitalens/analysis.py`)

- **Lab tests:** *before* = mean of that test's results in the 150 days before the medicine start date. *After* = mean of the last 2 results dated 30 or more days after the start. Both need at least 1 result. *Meaningful* = the change is at least the test's own limit in `LABS`.
- **Daily signals (weight, blood pressure):** *before* = mean of the 60 days before the start. *After* = mean of days 30 to 120 after the start. Missing days are left out, not filled.
- Raw data: the patient's workbook in `data/raw/` (sheets for medications, lab results and daily readings; `SHEETS` in `vitalens/loader.py` lists the names).

## Steps for each patient

1. Open `data/raw/<patient id>.xlsx` (it may sit in a sub-folder). Note the medicine start date from the medications sheet.
2. Labs: list the results inside the windows above, write them in the table, and work out the means with a calculator.
3. Signals: filter the daily sheet to the window and use `AVERAGE` (blank cells are skipped).
4. Compare with the *pipeline* columns. A match means within rounding (2 decimals for labs, 1 decimal for signals).

## Patients

Pipeline values below come from `web/data/chunks`. Fill the **My value** columns from the workbook.

### PC0989: Metformin XR

Clinical history in the data: Prediabetes

Start date: **2026-01-20** · dose 500 mg · status Active

| Measure | Unit | Pipeline before | Pipeline after | Pipeline change | n before / after | My before | My after | Match? |
|---|---|---|---|---|---|---|---|---|
| HbA1c | % | 5.67 | 6.46 | 0.79 | 1 / 3 |  |  |  |
| Fasting glucose | mg/dL | 131.4 | 111.45 | -19.95 | 1 / 4 |  |  |  |
| Weight | kg | 88.54 | 89.07 | 0.53 | daily |  |  |  |

Notes:

### PC0003: Atorvastatin

Clinical history in the data: Borderline glycemic markers

Start date: **2026-02-01** · dose 10 mg · status Active

| Measure | Unit | Pipeline before | Pipeline after | Pipeline change | n before / after | My before | My after | Match? |
|---|---|---|---|---|---|---|---|---|
| LDL cholesterol | mg/dL | 124.55 | 103.05 | -21.5 | 2 / 3 |  |  |  |
| Total cholesterol | mg/dL | 179.7 | 172.4 | -7.3 | 2 / 2 |  |  |  |

Notes:

### PC0311: Cholecalciferol

Clinical history in the data: Vitamin D insufficiency, Iron deficiency, Hypothyroidism

Start date: **2025-12-29** · dose 1000 IU · status Active

| Measure | Unit | Pipeline before | Pipeline after | Pipeline change | n before / after | My before | My after | Match? |
|---|---|---|---|---|---|---|---|---|
| Vitamin D | ng/mL | 18.6 | 34.4 | 15.8 | 1 / 4 |  |  |  |

Notes:

### PC0309: Ferrous sulfate

Clinical history in the data: Hypothyroidism, Iron deficiency, Migraine, GERD

Start date: **2025-11-07** · dose 325 mg · status Active

| Measure | Unit | Pipeline before | Pipeline after | Pipeline change | n before / after | My before | My after | Match? |
|---|---|---|---|---|---|---|---|---|
| Hemoglobin | g/dL | 11.3 | 13.8 | 2.5 | 1 / 3 |  |  |  |
| Ferritin | ng/mL | 16.7 | 59.15 | 42.45 | 1 / 3 |  |  |  |

Notes:

### PC0301: Amlodipine

Clinical history in the data: Hypertension, Hyperlipidemia, Prediabetes

Start date: **2025-12-26** · dose 5 mg · status Active

| Measure | Unit | Pipeline before | Pipeline after | Pipeline change | n before / after | My before | My after | Match? |
|---|---|---|---|---|---|---|---|---|
| Home blood pressure (top) | mmHg | 130.3 | 129.5 | -0.8 | daily |  |  |  |
| Home blood pressure (bottom) | mmHg | 83.5 | 83.7 | 0.2 | daily |  |  |  |

Notes:

## Result

- Patients matching: _ / 5
- Differences found and why: _
- Anything to report to Uday (analysis.py) or Kamran (loader.py): _
