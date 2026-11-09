"""Checks for the AI safety rules in vitalens/explain.py. Run from the repo root:  python -m unittest tests.test_explain -v"""
import unittest

from vitalens import explain as ex

EV = {"patient": "PCTEST", "window": "x", "areas": [{
    "id": "metabolic", "area": "Blood sugar and weight", "status": "worsening", "above_target": [],
    "items": [{"kind": "lab", "name": "HbA1c", "measure": "average blood sugar (HbA1c)", "from": 5.7, "to": 6.5, "unit": "%", "dir": "worse"}]}]}
OK_TEXT = "Your average blood sugar (HbA1c) went up from 5.7% to 6.5%. " + ex.DISCLAIMER


class SafetyChecks(unittest.TestCase):
    def test_good_text_passes(self):
        self.assertTrue(ex.safety_check(OK_TEXT, EV)["pass"])

    def test_changed_number_fails(self):
        bad = OK_TEXT.replace("6.5%", "6.8%")
        r = ex.safety_check(bad, EV)
        self.assertFalse(r["pass"])
        self.assertIn("6.8", r["checks"][0]["detail"])

    def test_invented_number_fails(self):
        self.assertFalse(ex.safety_check(OK_TEXT + " Aim for 4.2.", EV)["checks"][0]["pass"])

    def test_diagnosis_words_fail(self):
        for phrase in ["This means you have diabetes.", "Your prediabetes is worse.", "You may have PCOS.", "This is hypertension."]:
            self.assertFalse(ex.safety_check(OK_TEXT + " " + phrase, EV)["checks"][1]["pass"], phrase)

    def test_dose_advice_fails(self):
        for phrase in ["You should stop taking it.", "Please increase your dose.", "Skip a dose today."]:
            self.assertFalse(ex.safety_check(OK_TEXT + " " + phrase, EV)["checks"][1]["pass"], phrase)

    def test_missing_disclaimer_fails(self):
        self.assertFalse(ex.safety_check("Your average blood sugar (HbA1c) went up from 5.7% to 6.5%.", EV)["checks"][2]["pass"])

    def test_disclaimer_alone_is_not_flagged_as_diagnosis(self):
        self.assertTrue(ex.safety_check(OK_TEXT, EV)["checks"][1]["pass"])


class Rounding(unittest.TestCase):
    def test_half_up_like_javascript(self):
        self.assertEqual(ex._half_up(104.5), 105)
        self.assertEqual(ex._half_up(6.46, 1), 6.5)


class RealPatients(unittest.TestCase):
    def test_first_three_patients_rule_based_pass(self):
        for pid in ("PC0989", "PC0006", "PC0560"):
            out = ex.explain_patient(pid, use_llm=False)
            self.assertTrue(out["safety"]["pass"], pid)

    def test_all_900_rule_based_pass(self):
        bad = []
        for n in list(range(1, 201)) + list(range(301, 1001)):
            try:
                out = ex.explain_patient(f"PC{n:04d}", use_llm=False)
            except KeyError:
                continue
            if not out["safety"]["pass"]:
                bad.append(out["patient"])
        self.assertEqual(bad, [])


if __name__ == "__main__":
    unittest.main()
