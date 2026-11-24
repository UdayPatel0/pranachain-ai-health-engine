/* Emergency travel card: shared by the patient app (index.html) and the public QR page (emergency.html). */
(function () {
  const L = {
    en: { title: "Medical emergency card", help: "I may need medical help. Please read this card.", blood: "Blood group", allergy: "Allergies", cond: "Health conditions", meds: "Medicines I take", contact: "Emergency contact", note: "Note", none: "None recorded", since: "since", age: "Age", sex: { Male: "Male", Female: "Female" }, foot: "From VitaLens · PranaChain. Shown by the patient's choice; every opening is recorded." },
    hi: { title: "चिकित्सा आपातकालीन कार्ड", help: "मुझे चिकित्सा सहायता की ज़रूरत हो सकती है। कृपया यह कार्ड पढ़ें।", blood: "ब्लड ग्रुप", allergy: "एलर्जी", cond: "स्वास्थ्य स्थितियाँ", meds: "मेरी दवाइयाँ", contact: "आपातकालीन संपर्क", note: "नोट", none: "कुछ दर्ज नहीं", since: "से", age: "उम्र", sex: { Male: "पुरुष", Female: "महिला" }, foot: "VitaLens · PranaChain से। मरीज़ की अनुमति से दिखाया गया; हर बार खोलना दर्ज होता है।" },
    gu: { title: "તબીબી ઇમરજન્સી કાર્ડ", help: "મને તબીબી મદદની જરૂર પડી શકે છે. કૃપા કરીને આ કાર્ડ વાંચો.", blood: "બ્લડ ગ્રુપ", allergy: "એલર્જી", cond: "આરોગ્ય સ્થિતિઓ", meds: "મારી દવાઓ", contact: "ઇમરજન્સી સંપર્ક", note: "નોંધ", none: "કંઈ નોંધાયેલ નથી", since: "થી", age: "ઉંમર", sex: { Male: "પુરુષ", Female: "સ્ત્રી" }, foot: "VitaLens · PranaChain તરફથી. દર્દીની પસંદગીથી બતાવેલ; દરેક વખત ખોલવું નોંધાય છે." },
    es: { title: "Tarjeta de emergencia médica", help: "Puedo necesitar ayuda médica. Por favor, lea esta tarjeta.", blood: "Grupo sanguíneo", allergy: "Alergias", cond: "Condiciones de salud", meds: "Medicamentos que tomo", contact: "Contacto de emergencia", note: "Nota", none: "Nada registrado", since: "desde", age: "Edad", sex: { Male: "Hombre", Female: "Mujer" }, foot: "De VitaLens · PranaChain. Mostrado por decisión del paciente; cada apertura queda registrada." },
    fr: { title: "Carte d'urgence médicale", help: "J'ai peut-être besoin d'aide médicale. Merci de lire cette carte.", blood: "Groupe sanguin", allergy: "Allergies", cond: "Problèmes de santé", meds: "Mes médicaments", contact: "Contact d'urgence", note: "Note", none: "Rien d'enregistré", since: "depuis", age: "Âge", sex: { Male: "Homme", Female: "Femme" }, foot: "De VitaLens · PranaChain. Affiché au choix du patient ; chaque ouverture est enregistrée." },
  };
  const esc = s => String(s == null ? "" : s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const NOALLERGY = /^no known/i;

  function render(c, lang, second) {
    const t = L[lang] || L.en, e = second && second !== lang ? L[second] : null;
    const lab = k => esc(t[k]) + (e ? `<span class="ec-2">${esc(e[k])}</span>` : "");
    const allergy = NOALLERGY.test(c.allergies || "") ? `<span class="ec-ok">${esc(c.allergies)}</span>` : `<b class="ec-warn">⚠ ${esc(c.allergies || t.none)}</b>`;
    return `<article class="ecard" lang="${esc(lang)}">
      <header><span class="ec-cross" aria-hidden="true">✚</span><div><h2>${lab("title")}</h2><p>${esc(t.help)}${e ? `<span class="ec-2">${esc(e.help)}</span>` : ""}</p></div></header>
      <div class="ec-grid">
        <div class="ec-big"><span class="ec-l">${lab("blood")}</span><b>${esc(c.blood_group || "?")}</b></div>
        <div class="ec-big"><span class="ec-l">${lab("age")}</span><b>${esc(c.age)} · ${esc((t.sex || {})[c.sex] || c.sex)}</b></div>
      </div>
      <div class="ec-row"><span class="ec-l">${lab("allergy")}</span>${allergy}</div>
      <div class="ec-row"><span class="ec-l">${lab("cond")}</span>${c.conditions.length ? c.conditions.map(x => `<span class="ec-tag">${esc(x.name)}</span>`).join(" ") : esc(t.none)}</div>
      <div class="ec-row"><span class="ec-l">${lab("meds")}</span>${c.medicines.length ? `<ul>${c.medicines.map(m => `<li><b>${esc(m.name)}</b> ${esc(m.dose || "")} · ${esc(m.frequency || "")}</li>`).join("")}</ul>` : esc(t.none)}</div>
      <div class="ec-row"><span class="ec-l">${lab("contact")}</span>${c.contact_name || c.contact_phone ? `<b>${esc(c.contact_name)}</b> ${c.contact_phone ? `<a href="tel:${esc(c.contact_phone.replace(/[^\d+]/g, ""))}">${esc(c.contact_phone)}</a>` : ""}` : esc(t.none)}</div>
      ${c.note ? `<div class="ec-row"><span class="ec-l">${lab("note")}</span>${esc(c.note)}</div>` : ""}
      <footer>${esc(c.id)} · ${esc(t.foot)}</footer></article>`;
  }

  const CSS = `.ecard{border:3px solid #C62828;border-radius:16px;background:#fff;color:#1b1b1b;padding:18px 20px;max-width:560px;font-family:"Atkinson Hyperlegible",system-ui,sans-serif}
  .ecard header{display:flex;gap:14px;align-items:flex-start;border-bottom:1px solid #f0d0d0;padding-bottom:12px;margin-bottom:12px}
  .ec-cross{background:#C62828;color:#fff;border-radius:10px;width:44px;height:44px;display:grid;place-items:center;font-size:26px;flex:none}
  .ecard h2{margin:0;font:600 20px/1.2 "Lexend",system-ui,sans-serif;color:#9b1c1c}.ecard header p{margin:4px 0 0;font-size:15px}
  .ec-2{display:block;font-size:.82em;color:#666;font-weight:400}
  .ec-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:6px}.ec-big{background:#fdf1f1;border-radius:10px;padding:8px 12px}.ec-big b{display:block;font-size:24px}
  .ec-row{padding:8px 0;border-top:1px solid #f3e3e3;font-size:16px}.ec-row ul{margin:2px 0 0;padding-left:18px}
  .ec-l{display:block;font-size:12px;letter-spacing:.04em;text-transform:uppercase;color:#7a4b4b;margin-bottom:2px}
  .ec-warn{color:#b71c1c}.ec-ok{color:#2e7a4a}.ec-tag{display:inline-block;background:#fff3e0;border-radius:999px;padding:2px 10px;margin:2px 4px 2px 0}
  .ecard footer{margin-top:10px;font-size:12px;color:#777}.ecard a{color:#9b1c1c;font-weight:700}`;

  window.VLCard = { render, CSS, LANGS: Object.keys(L) };
})();
