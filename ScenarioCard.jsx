import { SCN, STATUS, fmtD } from "../lib/model.js";
import EvidenceItem from "./EvidenceItem.jsx";

export default function ScenarioCard({ id, scenario: v }) {
  const s = SCN[id];
  return (
    <div className="sc">
      <div className="row"><span className="eyebrow">{s.n} · {s.t} · {s.s}</span><span className={`pill st-${v.status}`}>{STATUS[v.status]}</span></div>
      <p className="small muted" style={{ marginTop: 6 }}>Why this scenario: {v.context.map((c) => c.text + (c.date ? ` (${fmtD(c.date)})` : "")).join(" · ")}</p>
      <ul>{v.evidence.length ? v.evidence.map((e, i) => <EvidenceItem key={i} e={e} />) : <li className="muted">No change beyond the meaningful-change limits.</li>}</ul>
      {v.above_target.length > 0 && <p className="small warn" style={{ marginTop: 8 }}>Still above target: {v.above_target.join(", ")}</p>}
    </div>
  );
}
