import { ORDER, SYS, systemSummary } from "../lib/model.js";

const LABEL = { worse: "something got worse", flag: "outside reference or on record", ok: "within usual range", nodata: "no data" };

/** Body systems list. In Sprint 5 each row opens the system view and the 3D body is added beside it. */
export default function BodySystemsList({ patient, status }) {
  return (
    <section className="card">
      <h2 className="h3">Body systems</h2>
      <ul className="syslist">
        {ORDER.filter((k) => k !== "hormones" || patient.sex === "Female").map((k) => (
          <li key={k} className="sysrow">
            <span className={`dot ${status[k]}`} role="img" aria-label={LABEL[status[k]]} />
            <span><b>{SYS[k].name}</b><span className="s">{systemSummary(patient, k, status[k])}</span></span>
          </li>
        ))}
      </ul>
    </section>
  );
}
