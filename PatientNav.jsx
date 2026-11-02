import { useEffect, useState } from "react";

/** ID box + Open, previous / next. Unknown IDs get a visible message (bug found in the HTML demo test). */
export default function PatientNav({ index, current, onOpen }) {
  const [value, setValue] = useState(current);
  const [msg, setMsg] = useState("");
  useEffect(() => { setValue(current); setMsg(""); }, [current]);
  const ids = index.rows.map((r) => r.id);
  const go = (e) => {
    e.preventDefault();
    const v = value.trim().toUpperCase();
    if (ids.includes(v)) return onOpen(v);
    setMsg(v >= "PC0201" && v <= "PC0300" ? `${v} is in the PC0201–PC0300 range, which has not been received yet.` : `No patient ${v || "ID"} found. IDs look like PC0412.`);
  };
  const step = (d) => { const i = ids.indexOf(current); onOpen(ids[(i + d + ids.length) % ids.length]); };
  return (
    <form className="pnav" onSubmit={go} role="search" aria-label="Open a patient">
      <label className="sr-only" htmlFor="pq">Patient ID</label>
      <input id="pq" value={value} onChange={(e) => { setValue(e.target.value); setMsg(""); }} aria-invalid={!!msg} aria-describedby="pqmsg" autoComplete="off" />
      <button type="submit">Open</button>
      <button type="button" onClick={() => step(-1)} aria-label="Previous patient">‹</button>
      <button type="button" onClick={() => step(1)} aria-label="Next patient">›</button>
      <p id="pqmsg" className="small err" role="alert">{msg}</p>
    </form>
  );
}
