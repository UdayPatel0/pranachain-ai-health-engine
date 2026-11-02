import { fmtD, num } from "../lib/model.js";

const Tag = ({ dir }) => (dir && dir !== "stable" ? <span className={`tag ${dir}`}>{dir === "flag" ? "note" : dir}</span> : null);
const d = (u) => (u === "%" ? 2 : 1);

/** One line of scenario evidence (same wording as evText() in web/index.html). */
export default function EvidenceItem({ e }) {
  switch (e.kind) {
    case "lab": case "signal":
      return <li>{e.name}: {num(e.from, d(e.unit))} → {num(e.to, d(e.unit))} {e.unit}<Tag dir={e.dir} /></li>;
    case "marker":
      return <li>{e.name}: {e.to}<Tag dir={e.dir} /> <span className="muted small">{e.note || ""}</span></li>;
    case "response": {
      const items = e.items.filter((i) => i.kind !== "symptom");
      return <li>After <b>{e.name}</b> started ({fmtD(e.start)}): {items.map((i) => `${i.name} ${num(i.before, d(i.unit))} → ${num(i.after, d(i.unit))} ${i.unit}`).join("; ") || "no matching measurements"}</li>;
    }
    case "adherence": return <li>{e.name}: about {e.to}% of doses<Tag dir={e.dir} /></li>;
    case "symptom": return <li>{e.name}: {e.to} {e.unit} this year<Tag dir={e.dir} /></li>;
    case "cycle": return <li>Average cycle {e.to} days (typical 21–35), {e.long} of {e.n} cycles longer than 35 days, variation ±{e.sd} days<Tag dir={e.dir} /></li>;
    default: return <li>{e.name}</li>;
  }
}
