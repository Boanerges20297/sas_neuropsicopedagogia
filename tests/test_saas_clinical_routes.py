"""Synthetic HTTP checks of clinical routes: authenticated scope and CSRF."""
import unittest
from unittest.mock import patch
from uuid import uuid4

from app import app
import saas_store
import saas_clinical_routes as routes
from bta_license_client import LicenseDecision


class ClinicalHTTPTests(unittest.TestCase):
    def setUp(self):
        self.old_testing = app.config["TESTING"]
        app.config["TESTING"] = True
        self.client = app.test_client()
        self.user = saas_store.SaaSUser({
            "id": 7, "nome": "Profissional Sintético",
            "email": "synthetic@example.invalid", "global_role": "professional",
            "active": 1, "must_change_password": 0})
        self.patches = [
            patch.object(saas_store, "get_user", return_value=self.user),
            patch.object(routes, "licensed_tenant", return_value=(
                {"id": 11, "nome": "Consultório Sintético"},
                LicenseDecision(status="exempt"))),
            patch.object(routes.nc, "scoped_client", return_value={
                "id": 21, "nome": "Paciente Sintético", "status": "active"}),
        ]
        for p in self.patches: p.start()
        with self.client.session_transaction() as session:
            session["_user_id"] = "saas:7"
            session["_fresh"] = True
            session["saas_auth"] = True
            session["saas_csrf"] = "clinical-csrf-test"

    def tearDown(self):
        for p in reversed(self.patches): p.stop()
        app.config["TESTING"] = self.old_testing

    def test_dashboard_renders_filters_and_own_metrics(self):
        stats = {"period": "month", "anchor": "2026-11",
                 "total": 3, "unique_clients": 2, "tests": 1, "tests_answered": 1,
                 "timeline": [{"bucket": "09/11", "quantity": 3}],
                 "diagnoses": []}
        with patch.object(routes.clinical, "professional_dashboard", return_value=stats), \
             patch.object(routes.clinical, "list_encounters", return_value=[]), \
             patch.object(routes.store, "list_clients", return_value=[]):
            result = self.client.get("/saas/atendimentos?period=month&anchor=2026-11")
        self.assertEqual(result.status_code, 200)
        text = result.get_data(as_text=True)
        self.assertIn("Novo atendimento", text)
        self.assertIn("Instrumentos indicados", text)
        self.assertIn('name="csrf_token" value="clinical-csrf-test"', text)

    def test_invalid_dashboard_period_does_not_contact_statistics(self):
        with patch.object(routes.clinical, "professional_dashboard", side_effect=ValueError) as mock:
            result = self.client.get("/saas/atendimentos?period=anything")
        self.assertEqual(result.status_code, 400)
        mock.assert_called_once()

    def test_start_requires_csrf_and_owned_patient(self):
        payload = {"client_id": "21", "request_id": str(uuid4())}
        with patch.object(routes.clinical, "start_encounter", return_value=67) as create:
            self.assertEqual(self.client.post(
                "/saas/atendimentos/iniciar", data=payload).status_code, 400)
            create.assert_not_called()
            result = self.client.post("/saas/atendimentos/iniciar",
                data={**payload, "csrf_token": "clinical-csrf-test"})
            self.assertEqual(result.status_code, 302)
            self.assertIn("/saas/pacientes/21/atendimentos/67", result.location)
            create.assert_called_once_with(7, 11, 21, payload["request_id"])

    def test_foreign_patient_gets_404_before_write(self):
        with patch.object(routes.nc, "scoped_client", return_value=None), \
             patch.object(routes.clinical, "start_encounter") as start:
            result = self.client.post("/saas/atendimentos/iniciar", data={
                "csrf_token": "clinical-csrf-test",
                "client_id": "999", "request_id": str(uuid4())})
            self.assertEqual(result.status_code, 404)
            start.assert_not_called()
            self.assertEqual(self.client.get(
                "/saas/pacientes/999/instrumentos").status_code, 404)

    def test_professional_questionnaire_submission_follows_same_definition(self):
        item = {"id": 55, "title": "Instrumento sintético",
                "version_number": 1, "status": "in_progress",
                "mode": "professional", "revision": 2, "encounter_id": None,
                "definition": {"kind": "anamnesis", "questions": [
                    {"key": "q1", "label": "Histórico escolar", "type": "single",
                     "required": True, "help": "",
                     "options": [{"value": "yes", "label": "Sim"},
                                 {"value": "no", "label": "Não"}]}
                ]}}
        with patch.object(routes.assessments, "scoped_assessment", return_value=item), \
             patch.object(routes.assessments, "read_answers", return_value={}), \
             patch.object(routes.assessments, "save_answers", return_value=3) as save:
            result = self.client.get("/saas/pacientes/21/instrumentos/55")
            self.assertEqual(result.status_code, 200)
            self.assertIn("Histórico escolar", result.get_data(as_text=True))
            self.assertEqual(result.headers.get("Cache-Control"), "private, no-store")
            result = self.client.post("/saas/pacientes/21/instrumentos/55",
                data={"csrf_token": "clinical-csrf-test",
                      "revision": "2", "answer_q1": "yes", "action": "submit"})
            self.assertEqual(result.status_code, 302)
            self.assertEqual(save.call_args.args[:4], (7,11,21,55))
            self.assertEqual(save.call_args.args[4], {"q1": "yes"})
            self.assertEqual(save.call_args.kwargs, {"submit": True})


if __name__ == "__main__":
    unittest.main()
