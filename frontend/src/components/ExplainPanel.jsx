// "Explain in plain words" panel · design notes in docs/ai-explanation-panel.md
import { useState } from "react";
import { getExplanation } from "@shared/explain.js";

const qs = new URLSearchParams(location.search);
const OPTS = { api: qs.get("api") || import.meta.env.VITE_AI_API || "", demoUnsafe: qs.get("demo") === "unsafe" };

function Checks({ x }) {
  const r = x.readability;
  const items = [...x.safety.checks, {
    id: "read", pass: r.pass, label: `Easy to read: ${r.level.toLowerCase()}`,
    detail: `Reading level grade ${r.grade} (target 8 or lower) · ${r.wordsPerSentence} words per sentence${r.jargon.length ? " · medical words to explain: " + r.jargon.map((j) => `${j.term} → ${j.plain}`).join(", ") : ""}`,
  }];
  return (
    <ul className="chk" aria-label="Checks on this explanation">
      {items.map((c) => (
        <li key={c.id} className={c.pass ? "pass" : "fail"}>
          <span className="ic" aria-hidden="true">{c.pass ? "✓" : "!"}</span>
          <span><b>{c.label}</b><span className="muted">{c.pass ? "" : "Failed · "}{c.detail}</span></span>
        </li>
      ))}
    </ul>
  );
}

export default function ExplainPanel({ patient }) {
  const [x, setX] = useState(null);       // null | "loading" | explanation | {error}
  const [big, setBig] = useState(false);

  const run = async () => {
    setX("loading");
    try { setX(await getExplanation(patient, OPTS)); } catch (e) { console.error(e); setX({ error: "Please try again in a moment." }); }
  };
  const read = () => { speechSynthesis.cancel(); const u = new SpeechSynthesisUtterance(x.text); u.rate = 0.95; u.lang = "en-CA"; speechSynthesis.speak(u); };
  const ready = x && x !== "loading" && !x.error;

  return (
    <section className={`card ex${big ? " big" : ""}`} aria-labelledby="exh">
      <div className="row">
        <h2 className="h3" id="exh">Your results in plain words</h2>
        {ready && <span className={`ex-src${x.source === "ai" ? " ai" : ""}`} title={x.model}>{x.source === "ai" ? "AI answer" : "Preview · AI not connected yet"}</span>}
      </div>

      {!x && <>
        <p className="muted lead">A short explanation of the changes above, written for patients. It uses only the evidence shown on this page and is checked before it is shown.</p>
        <div className="ex-tools"><button type="button" className="btn-primary" onClick={run}>Explain in plain words</button></div>
      </>}
      {x === "loading" && <p className="lead" role="status">Writing the explanation…</p>}
      {x?.error && <div className="blocked" role="alert"><p><b>The explanation could not be made.</b> {x.error}</p><button type="button" className="btn-ghost" onClick={run}>Try again</button></div>}

      {ready && !x.safety.pass && <>
        <div className="blocked" role="alert">
          <p><b>This explanation was held back.</b> It did not pass a safety check, so it is not shown to the patient.</p>
          <p className="small" style={{ marginTop: 6 }}>The evidence above is still correct. A doctor or care team member can explain these results.</p>
        </div>
        <Checks x={x} />
        <details className="team"><summary>Team view: show the blocked text</summary><pre>{x.text}</pre></details>
      </>}

      {ready && x.safety.pass && <>
        <div className="ex-body">
          {x.intro && <p>{x.intro}</p>}
          {x.sections.map((s, i) => <div key={i}>{s.area && <h3>{s.area}</h3>}<ul>{s.sentences.map((t, j) => <li key={j}>{t}</li>)}</ul></div>)}
          {x.disclaimer && <p className="ex-disc">{x.disclaimer}</p>}
        </div>
        <div className="ex-tools">
          {"speechSynthesis" in window && <button type="button" className="btn-ghost" onClick={read}>Read aloud</button>}
          <button type="button" className="btn-ghost" aria-pressed={big} onClick={() => setBig(!big)}>Bigger text</button>
          <button type="button" className="btn-ghost" onClick={run}>Explain again</button>
        </div>
        <p className="small muted" style={{ marginTop: 14 }}>Checked before showing</p>
        <Checks x={x} />
      </>}

      {ready && <details className="team"><summary>Team view: evidence given to the AI</summary><pre>{JSON.stringify(x.evidence, null, 1)}</pre></details>}
      {ready && x.apiError && <p className="small muted" style={{ marginTop: 6 }}>AI service not reached ({x.apiError}), showing the preview instead.</p>}
    </section>
  );
}
