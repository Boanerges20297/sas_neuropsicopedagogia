"""Contract and HTTP checks: clinical patient discharge and assessment cleanup."""
from contextlib import contextmanager
from datetime import date
from unittest.mock import patch
import unittest

from app import app
from bta_license_client import LicenseDecision
import saas_store as store
import saas_patient_management as patients
import saas_patient_management_routes as routes
import saas_assessment_management as assessments


class Cursor:
    def __init__(self, answers=()):
        self.answers = list(answers)
        self.calls = []

    def execute(self, sql, args=()):
        self.calls.append((sql, args))

    def fetchone(self):
        return self.answers.pop(0) if self.answers else None


@contextmanager
def tx(cur):
    yield cur


class ClinicalManagementContracts(unittest.TestCase):
    def test_discharge_preserves_patient_and_records(self):
        cur = Cursor([{"id": 14, "status": "active"}])
        with patch.object(store, "transaction", return_value=tx(cur)), \
             patch.object(store, "audit") as audit:
            result = patients.change_status(7, 11, 14, "alta")
        self.assertEqual(result, "inactive")
        statements = " ".join(query for query, _ in cur.calls)
        self.assertIn("UPDATE clients SET status", statements)
        self.assertNotIn("DELETE FROM clients", statements)
        self.assertNotIn("DELETE FROM care_", statements)
        self.assertIn("c.professional_user_id=%s", statements)
        self.assertIn("m.user_id=%s", statements)
        audit.assert_called_once()

    def test_closure_and_reactivation_allowed_but_bad_transition_refused(self):
        for before, action, expected in (
            ("active", "encerrar", "archived"),
            ("inactive", "reativar", "active"),
            ("archived", "reativar", "active"),
        ):
            cur = Cursor([{"id": 14, "status": before}])
            with patch.object(store, "transaction", return_value=tx(cur)), \
                 patch.object(store, "audit"):
                self.assertEqual(patients.change_status(7, 11, 14, action), expected)
        cur = Cursor([{"id": 14, "status": "archived"}])
        with patch.object(store, "transaction", return_value=tx(cur)):
            with self.assertRaises(ValueError):
                patients.change_status(7, 11, 14, "alta")
        self.assertFalse(any("UPDATE clients" in q for q, _ in cur.calls))

    def test_patient_update_respects_minor_guardian_relation(self):
        cur = Cursor([{"id": 14, "status": "active"},
                      {"representation_mode": "guardian"}])
        with patch.object(store, "transaction", return_value=tx(cur)), \
             patch.object(store, "audit") as audit:
            result = patients.update_identity(
                7, 11, 14, name="  Criança Exemplo  ", birth_date="2017-04-10")
        self.assertEqual(result, 14)
        statement = next((args for q, args in cur.calls if q.startswith("UPDATE clients")), ())
        self.assertEqual(statement[:2], ("Criança Exemplo", date(2017, 4, 10)))
        audit.assert_called_once()
        with self.assertRaises(ValueError):
            patients.update_identity(7, 11, 14, name="", birth_date="2017-04-10")

    def test_reset_removes_only_one_assessment_answers(self):
        cur = Cursor([{"id": 91, "status": "submitted", "mode": "professional"}])
        with patch.object(store, "transaction", return_value=tx(cur)), \
             patch.object(assessments.care, "_lock_owned_client"), \
             patch.object(store, "audit") as audit:
            self.assertEqual(assessments.manage_application(7, 11, 14, 91, "reset"),
                             "reset")
        sqls = [q for q, _ in cur.calls]
        self.assertTrue(any("DELETE FROM care_assessment_private_answers" in q for q in sqls))
        self.assertTrue(any("DELETE FROM assessment_responses" in q for q in sqls))
        self.assertTrue(any("SET revision=revision+1" in q for q in sqls))
        self.assertTrue(any("status='pending'" in q for q in sqls))
        self.assertFalse(any("DELETE FROM tests" in q or "DELETE FROM clients" in q
                             for q in sqls))
        self.assertTrue(all(args[:2] == (91, 11) for q, args in cur.calls
                            if q.startswith("DELETE")))
        audit.assert_called_once()

    def test_cancel_has_no_data_deletion(self):
        cur = Cursor([{"id": 91, "status": "in_progress", "mode": "portal"}])
        with patch.object(store, "transaction", return_value=tx(cur)), \
             patch.object(assessments.care, "_lock_owned_client"), \
             patch.object(store, "audit"):
            self.assertEqual(assessments.manage_application(7, 11, 14, 91, "cancel"),
                             "cancel")
        self.assertTrue(any("status='cancelled'" in q for q, _ in cur.calls))
        self.assertFalse(any("DELETE" in q for q, _ in cur.calls))

    def test_portal_cannot_be_silently_reset(self):
        cur = Cursor([{"id": 91, "status": "submitted", "mode": "portal"}])
        with patch.object(store, "transaction", return_value=tx(cur)), \
             patch.object(assessments.care, "_lock_owned_client"):
            with self.assertRaises(ValueError):
                assessments.manage_application(7, 11, 14, 91, "reset")
        self.assertFalse(any("DELETE" in q for q, _ in cur.calls))


class PatientManagementHttp(unittest.TestCase):
    def setUp(self):
        self.prior = app.config["TESTING"]
        app.config["TESTING"] = True
        self.client = app.test_client()
        self.actor = store.SaaSUser({
            "id": 7, "nome": "Profissional fictício", "email": "fake@example.invalid",
            "global_role": "professional", "active": 1, "must_change_password": 0,
        })
        self.patches = [
            patch.object(store, "get_user", return_value=self.actor),
            patch.object(routes, "licensed_tenant", return_value=(
                {"id": 11, "nome": "Espaço de testes"},
                LicenseDecision(status="exempt"))),
            patch.object(routes.management, "own_client", return_value={
                "id": 14, "nome": "Paciente de teste", "status": "active",
                "birth_date": date(2017, 4, 10), "email": None,
            }),
        ]
        for p in self.patches:
            p.start()
        with self.client.session_transaction() as s:
            s["_user_id"] = "saas:7"
            s["_fresh"] = True
            s["saas_auth"] = True
            s["saas_csrf"] = "manage-test-csrf"

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        app.config["TESTING"] = self.prior

    def test_management_page_and_csrf(self):
        page = self.client.get("/saas/pacientes/14/gerenciar")
        self.assertEqual(page.status_code, 200)
        self.assertIn("Dar alta", page.get_data(as_text=True))
        self.assertIn("Encerrar acompanhamento", page.get_data(as_text=True))
        self.assertEqual(page.headers.get("Cache-Control"), "private, no-store")
        with patch.object(routes.management, "change_status", return_value="inactive") as change:
            without = self.client.post(
                "/saas/pacientes/14/gerenciar/situacao", data={"action": "alta"})
            self.assertEqual(without.status_code, 400)
            change.assert_not_called()
            ok = self.client.post(
                "/saas/pacientes/14/gerenciar/situacao",
                data={"csrf_token": "manage-test-csrf", "action": "alta"})
            self.assertEqual(ok.status_code, 302)
            change.assert_called_once_with(7, 11, 14, "alta")

    def test_foreign_patient_is_404(self):
        with patch.object(routes.management, "own_client", return_value=None):
            self.assertEqual(self.client.get("/saas/pacientes/99/gerenciar").status_code, 404)
            self.assertEqual(self.client.post(
                "/saas/pacientes/99/instrumentos/66/gerenciar",
                data={"csrf_token": "manage-test-csrf", "operation": "reset"}).status_code,
                404)

    def test_assessment_action_requires_csrf_and_ownership(self):
        with patch.object(assessments, "manage_application", return_value="reset") as reset:
            self.assertEqual(self.client.post(
                "/saas/pacientes/14/instrumentos/91/gerenciar",
                data={"operation": "reset"}).status_code, 400)
            reset.assert_not_called()
            response = self.client.post(
                "/saas/pacientes/14/instrumentos/91/gerenciar",
                data={"csrf_token": "manage-test-csrf", "operation": "reset"})
            self.assertEqual(response.status_code, 302)
            reset.assert_called_once_with(7, 11, 14, 91, "reset")


if __name__ == "__main__":
    unittest.main()
