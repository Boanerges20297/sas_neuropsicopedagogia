"""Feedback-derived NeuroCore policy contracts, using synthetic data only."""
import unittest
from copy import deepcopy
from unittest.mock import patch

from neurocore.feedback_learning import (
    annotate_report, candidate_policy, select_signal, MIN_CASES_FOR_CANDIDATE,
)
from neurocore.indicator_engine import identify_indicators
from neurocore import feedback_store as learning_store


class FeedbackPolicyTests(unittest.TestCase):
    def setUp(self):
        self.report = identify_indicators("tdah", record={
            "intake_text": "Dificuldade de concentração relatada.",
            "notes": [],
        })
        annotate_report(self.report)

    def test_only_server_generated_signal_is_selectable(self):
        signal = self.report["active_domains"][0]["signals"][0]
        self.assertEqual(len(signal["feedback_key"]), 64)
        self.assertEqual(len(signal["feature_key"]), 64)
        self.assertIs(select_signal(self.report, "atencao_atividade",
                                    signal["feedback_key"]), signal)
        with self.assertRaises(ValueError):
            select_signal(self.report, "atencao_atividade", "forged")
        with self.assertRaises(ValueError):
            select_signal(self.report, "wrong", signal["feedback_key"])

    def test_key_is_stable_and_does_not_reveal_chart_text(self):
        original = deepcopy(self.report)
        annotate_report(self.report)
        self.assertEqual(self.report, original)
        key = self.report["active_domains"][0]["signals"][0]["feedback_key"]
        self.assertNotIn("concentração", key)
        self.assertNotIn("Dificuldade", key)

    def test_candidate_uses_reviewed_cases_and_does_not_activate(self):
        rows = [{"feature_key": "a", "client_id": i, "verdict": "confirmado"}
                for i in range(MIN_CASES_FOR_CANDIDATE)]
        rows += [{"feature_key": "a", "client_id": 1, "verdict": "descartado"}]
        candidate = candidate_policy(rows)[0]
        self.assertEqual(candidate["cases"], MIN_CASES_FOR_CANDIDATE)
        self.assertTrue(candidate["ready_for_review"])
        self.assertFalse(candidate["active"])
        self.assertGreater(candidate["candidate_weight"], 0.5)

    def test_negative_feedback_lowers_candidate_not_diagnosis(self):
        rows = [{"feature_key": "b", "client_id": i, "verdict": "descartado"}
                for i in range(8)]
        candidate = candidate_policy(rows)[0]
        self.assertLess(candidate["candidate_weight"], .5)
        self.assertNotIn("diagnosis", candidate)
        self.assertNotIn("probability", candidate)

    def test_inconclusive_is_neutral_and_no_early_activation(self):
        rows = [{"feature_key": "x", "client_id": i, "verdict": "inconclusivo"}
                for i in range(8)]
        candidate = candidate_policy(rows)[0]
        self.assertEqual(candidate["candidate_weight"], .5)
        self.assertFalse(candidate["ready_for_review"])
        self.assertFalse(candidate["active"])

    def test_wrong_verdict_rejected_before_database(self):
        with self.assertRaises(ValueError):
            learning_store.save_feedback(
                7, 11, 16, "tdah", {}, "diagnostico",
                "indicadores-exploratorios-0.1")


class _Cursor:
    def __init__(self, owned=True):
        self.owned = owned
        self.calls = []

    def execute(self, sql, args=()):
        self.calls.append((sql, args))

    def fetchone(self):
        return {"id": 16} if self.owned else None


class _Transaction:
    def __init__(self, cursor):
        self.cursor = cursor

    def __enter__(self):
        return self.cursor

    def __exit__(self, kind, value, tb):
        return False


class FeedbackStoreTests(unittest.TestCase):
    def setUp(self):
        report = identify_indicators("tdah", record={
            "intake_text": "Dificuldade de concentração CLINICAL_PRIVATE_SENTINEL",
            "notes": [],
        })
        self.signal = annotate_report(report)["active_domains"][0]["signals"][0]

    def test_valid_feedback_is_scoped_and_contains_no_clinical_excerpt(self):
        cursor = _Cursor()
        with patch.object(learning_store.store, "transaction",
                          return_value=_Transaction(cursor)), \
             patch.object(learning_store.store, "audit") as audit:
            learning_store.save_feedback(
                7, 11, 16, "tdah", self.signal, "confirmado",
                "indicadores-exploratorios-0.1", assessment_id=55)
        combined = repr(cursor.calls)
        self.assertIn("c.professional_user_id=%s", combined)
        self.assertIn("m.status='active'", combined)
        self.assertIn("ON DUPLICATE KEY UPDATE", combined)
        self.assertNotIn("CLINICAL_PRIVATE_SENTINEL", combined)
        self.assertEqual(cursor.calls[1][1][:3], (11, 16, 7))
        audit.assert_called_once()

    def test_foreign_patient_is_denied_before_insert_or_audit(self):
        cursor = _Cursor(owned=False)
        with patch.object(learning_store.store, "transaction",
                          return_value=_Transaction(cursor)), \
             patch.object(learning_store.store, "audit") as audit:
            with self.assertRaises(PermissionError):
                learning_store.save_feedback(
                    7, 11, 999, "tdah", self.signal, "descartado",
                    "indicadores-exploratorios-0.1")
        self.assertEqual(len(cursor.calls), 1)
        audit.assert_not_called()


if __name__ == "__main__":
    unittest.main()
