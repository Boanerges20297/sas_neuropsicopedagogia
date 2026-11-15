"""Regression contracts for compact, touch-friendly SaaS and clinical buttons."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


class SaaSButtonProportionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.shared = (ROOT / "static" / "saas.css").read_text(encoding="utf-8")
        cls.clinical = (ROOT / "static" / "saas-clinical.css").read_text(encoding="utf-8")

    def test_stylesheets_have_balanced_braces(self):
        for css in (self.shared, self.clinical):
            self.assertEqual(css.count("{"), css.count("}"))

    def test_primary_controls_keep_44px_touch_target(self):
        for name, css, selector in (
            ("shared button", self.shared, ".saas-btn"),
            ("clinical button", self.clinical, ".clinic-button"),
        ):
            with self.subTest(name=name):
                rule = re.search(re.escape(selector) + r"\{([^}]*)\}", css)
                self.assertIsNotNone(rule)
                self.assertIn("min-height:44px", rule.group(1))

    def test_desktop_grid_forms_do_not_stretch_primary_actions(self):
        self.assertIn("@media(min-width:621px)", self.shared)
        self.assertIn(".saas-profile-panel form>.saas-btn", self.shared)
        self.assertIn(".saas-form-card form>.saas-btn", self.shared)
        self.assertIn("justify-self:start", self.shared)

    def test_clinical_test_buttons_are_not_forced_to_expand(self):
        self.assertIn(".clinic-inline>.clinic-button{flex:0 1 auto;min-width:0}", self.clinical)
        self.assertIn(".clinic-form>.clinic-button{align-self:flex-start", self.clinical)
        self.assertIn(".clinic-filter>.clinic-button{min-width:0}", self.clinical)
        html = (ROOT / "templates" / "saas_clinical_questionnaire.html").read_text(encoding="utf-8")
        self.assertIn('class="clinic-inline"', html)


if __name__ == "__main__":
    unittest.main()
