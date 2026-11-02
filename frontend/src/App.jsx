// VitaLens React app · Sprint 4: patient overview screen (rebuilt from web/index.html)
// Owner: Nancy (Frontend & UX) · built with AI assistance (Claude), reviewed by the team
import { useEffect, useState } from "react";
import { loadIndex, loadPatient } from "./lib/data.js";
import PatientOverview from "./components/PatientOverview.jsx";

// The patient ID lives in the URL (#/patient/PC0989) so a link opens the same patient.
const idFromHash = () => (location.hash.match(/#\/patient\/(PC\d{4})/i) || [])[1]?.toUpperCase() || null;

export default function App() {
  const [index, setIndex] = useState(null);
  const [error, setError] = useState(null);
  const [id, setId] = useState(idFromHash());
  const [patient, setPatient] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => { loadIndex().then(setIndex).catch((e) => setError(String(e.message || e))); }, []);
  useEffect(() => { const on = () => setId(idFromHash()); addEventListener("hashchange", on); return () => removeEventListener("hashchange", on); }, []);
  useEffect(() => { if (index && !id) location.hash = `#/patient/${index.summary.featured[0]?.id || index.rows[0].id}`; }, [index, id]);
  useEffect(() => {
    if (!index || !id) return;
    let live = true; setLoading(true);
    loadPatient(id).then((p) => { if (live) { setPatient(p); setLoading(false); if ("speechSynthesis" in window) speechSynthesis.cancel(); } })
      .catch((e) => live && (setError(String(e.message || e)), setLoading(false)));
    return () => { live = false; };
  }, [index, id]);

  const open = (pid) => { location.hash = `#/patient/${pid}`; window.scrollTo({ top: 0 }); };

  return (
    <div className="page">
      <header className="top">
        <div className="logo"><span>Vita<b>Lens</b></span><span className="badge">{index ? `PRANACHAIN DATA · ${index.rows.length} PATIENTS` : "PRANACHAIN DATA"}</span></div>
        <span className="badge">React · Sprint 4</span>
      </header>
      {error && <div className="card" role="alert"><h2>The data could not be loaded</h2><p className="muted">{error}. Run <span className="mono">npm run dev</span> inside <span className="mono">frontend/</span> so the JSON in <span className="mono">web/data</span> is served.</p></div>}
      {!error && (!index || (!patient && loading)) && <div className="card loading" role="status">Loading…</div>}
      {index && patient && <PatientOverview index={index} patient={patient} loading={loading} onOpen={open} />}
      {index && !loading && id && !patient && !error && <div className="card" role="alert">Patient {id} was not found.</div>}
      <footer>VitaLens React app v0.1 · Team VitaLens, COMP 8967, Group 1 · Synthetic patient workbooks provided by PranaChain · Built with AI assistance · Describes changes in data; not a diagnosis</footer>
    </div>
  );
}
