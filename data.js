// Reads the same JSON as web/index.html. Later (Sprint 5) these two functions switch to the FastAPI endpoints
// /patients and /patients/{id}; the components do not need to change.
const BASE = import.meta.env.VITE_DATA_URL || import.meta.env.BASE_URL; // "./" in dev and build
const chunks = {};
let indexPromise = null;

export function loadIndex() {
  if (!indexPromise) {
    indexPromise = fetch(`${BASE}index.json`).then((r) => { if (!r.ok) throw new Error(`index.json: HTTP ${r.status}`); return r.json(); })
      .then((idx) => ({ ...idx, rows: idx.rows.map((r) => Object.fromEntries(idx.columns.map((c, i) => [c, r[i]]))) }));
  }
  return indexPromise;
}

export async function loadPatient(id) {
  const idx = await loadIndex();
  const row = idx.rows.find((r) => r.id === id);
  if (!row) return null;
  if (!chunks[row.chunk]) chunks[row.chunk] = fetch(`${BASE}chunks/${row.chunk}.json`).then((r) => { if (!r.ok) throw new Error(`chunk ${row.chunk}: HTTP ${r.status}`); return r.json(); });
  return (await chunks[row.chunk]).find((p) => p.id === id) || null;
}
