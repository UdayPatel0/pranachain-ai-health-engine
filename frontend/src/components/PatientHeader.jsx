export default function PatientHeader({ patient: p, activeCount }) {
  return (
    <>
      <div className="row" style={{ marginTop: 12 }}>
        <h1 className="h2"><span className="mono">{p.id}</span> · {p.age} · {p.sex}</h1>
        <span className={`pill st-${activeCount ? "mixed" : "none"}`}>{activeCount ? `${activeCount} scenario${activeCount > 1 ? "s" : ""}` : "No scenario"}</span>
      </div>
      <p className="small muted" style={{ marginTop: 4 }}>{p.family} · Allergies: {p.allergies} · Daily data present {Math.round(p.completeness * 100)}%</p>
    </>
  );
}
