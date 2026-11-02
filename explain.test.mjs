// Unit tests for web/explain.js · run: node --test web/tests/
import test from "node:test";
import assert from "node:assert/strict";
import { buildEvidence, previewExplanation, explanationText, safetyCheck, readability, DISCLAIMER } from "../explain.js";

const patient = {
  id: "PCTEST",
  scenarios: {
    metabolic: {
      status: "worsening", above_target: ["HbA1c"],
      evidence: [
        { kind: "lab", name: "HbA1c", dir: "worse", from: 5.7, to: 6.5, unit: "%" },
        { kind: "signal", name: "Daily steps", key: "steps", dir: "better", from: 7243.4, to: 9068.7, unit: "steps" },
        { kind: "response", name: "Metformin", start: "2025-10-01", items: [{ kind: "lab", name: "HbA1c", unit: "%", before: 6.09, after: 5.86, meaningful: true }] },
      ],
    },
    cardio: null, pcos: null,
  },
};
const ev = buildEvidence(patient);
const ok = (t) => safetyCheck(t, ev);

test("preview explanation passes safety and readability", () => {
  const text = explanationText(previewExplanation(ev));
  assert.equal(ok(text).pass, true, JSON.stringify(ok(text).checks));
  assert.equal(readability(text).pass, true);
  assert.match(text, /7,243/); // big numbers formatted with commas still match the evidence
});

test("an invented number fails the numbers check", () => {
  const r = ok(`Your average blood sugar (HbA1c) went up to 7.9. ${DISCLAIMER}`);
  assert.equal(r.checks.find((c) => c.id === "numbers").pass, false);
});

test("diagnosis words and dose advice fail the words check", () => {
  for (const bad of ["You have diabetes.", "This looks like hypertension.", "You should stop taking Metformin.", "Signs of PCOS."]) {
    assert.equal(ok(`${bad} ${DISCLAIMER}`).checks.find((c) => c.id === "words").pass, false, bad);
  }
});

test("the disclaimer itself does not trip the words check", () => {
  assert.equal(ok(DISCLAIMER).checks.find((c) => c.id === "words").pass, true);
});

test("a missing disclaimer fails", () => {
  assert.equal(ok("Your daily steps went up.").checks.find((c) => c.id === "disclaimer").pass, false);
});

test("medical words outside brackets are flagged, inside brackets are fine", () => {
  assert.deepEqual(readability("Your HbA1c went up.").jargon.map((j) => j.term), ["hba1c"]);
  assert.equal(readability("Your average blood sugar (HbA1c) went up.").jargon.length, 0);
  assert.equal(readability("Although it was hot, you walked.").jargon.length, 0); // "alt" inside a word is not jargon
});

test("long clinical text is graded as hard", () => {
  const hard = "The longitudinal trajectory of glycated haemoglobin demonstrates statistically significant deterioration relative to the individualised baseline, notwithstanding pharmacological intervention with metformin extended-release formulation.";
  const r = readability(hard);
  assert.equal(r.pass, false);
  assert.ok(r.grade > 12, `grade ${r.grade}`);
});
