import { useMemo } from "react";
import { systemStatus } from "../lib/model.js";
import PatientNav from "./PatientNav.jsx";
import PatientHeader from "./PatientHeader.jsx";
import ScenarioCard from "./ScenarioCard.jsx";
import ExplainPanel from "./ExplainPanel.jsx";
import BodySystemsList from "./BodySystemsList.jsx";

/** The patient overview screen: nav, header, scenario evidence, plain-words explanation, body systems. */
export default function PatientOverview({ index, patient, loading, onOpen }) {
  const status = useMemo(() => systemStatus(patient), [patient]);
  const active = Object.entries(patient.scenarios).filter(([, v]) => v);
  return (
    <main className="overview" aria-busy={loading}>
      <section className="card">
        <PatientNav index={index} current={patient.id} onOpen={onOpen} />
        <PatientHeader patient={patient} activeCount={active.length} />
        {!active.length && <p style={{ marginTop: 12 }}>No scenario pattern applies. {patient.id} has no glycemic, blood pressure, cholesterol or cycle history that meets the scenario rules, so VitaLens raises nothing. The body systems below still show this patient's 12 months.</p>}
        {active.map(([k, v]) => <ScenarioCard key={k} id={k} scenario={v} />)}
        <p className="small muted" style={{ marginTop: 10 }}>Changes compare the last three months with the first three (Sep–Nov 2025). Labs use each test's own reference range. This describes data; it is not a diagnosis.</p>
      </section>
      <ExplainPanel key={patient.id} patient={patient} />
      <BodySystemsList patient={patient} status={status} />
    </main>
  );
}
