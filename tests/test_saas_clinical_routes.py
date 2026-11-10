"""Synthetic HTTP checks of clinical routes: authenticated scope and CSRF."""
import unittest
from datetime import datetime
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

    def test_encounter_displays_longitudinal_hypothesis_not_auto_diagnosis(self):
        opened = datetime(2026, 11, 9, 10, 30)
        visit = {"id": 67, "status": "draft", "opened_at": opened}
        history = [{"id": 88, "label": "Hipótese sintética",
                    "code": None, "certainty": "hypothesis",
                    "encounter_id": 60, "recorded_at": opened}]
        sessions = [{"id": 67, "opened_at": opened}, {"id": 60, "opened_at": opened}]
        with patch.object(routes.clinical, "scoped_encounter", return_value=visit), \
             patch.object(routes.clinical, "latest_note",
                          return_value={"html": "", "revision": 0, "created_at": None}), \
             patch.object(routes.clinical, "list_diagnoses",
                          return_value=history) as records, \
             patch.object(routes.clinical, "list_encounters",
                          return_value=sessions) as encounter_list, \
             patch.object(routes.intake, "scoped_summary", return_value=None), \
             patch.object(routes.assessments, "list_for_patient", return_value=[]):
            response = self.client.get("/saas/pacientes/21/atendimentos/67")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Registrar hipótese diagnóstica", html)
        self.assertIn('name="certainty" value="hypothesis"', html)
        self.assertIn("Histórico de hipóteses e decisões", html)
        self.assertIn("/saas/pacientes/21/atendimentos/60", html)
        self.assertIn("Histórico de atendimentos", html)
        self.assertEqual(response.headers.get("Cache-Control"), "private, no-store")
        records.assert_called_once_with(7, 11, 21, 67)
        encounter_list.assert_called_once_with(7, 11, client_id=21, limit=20)

    def test_contextual_clinical_workspace_and_pending_choices(self):
        from datetime import datetime
        date_value = datetime(2026, 11, 10, 10, 30)
        hypothesis = {"id": 8, "label": "Hipótese sintética", "code": None,
                      "certainty": "hypothesis", "encounter_id": 67,
                      "recorded_at": date_value}
        confirmed = {"id": 9, "label": "Hipótese já reavaliada", "code": None,
                     "certainty": "confirmed", "encounter_id": 67,
                     "recorded_at": date_value}
        with patch.object(routes.clinical, "scoped_encounter", return_value={
                "id": 67, "status": "draft", "opened_at": date_value}), \
             patch.object(routes.clinical, "latest_note", return_value={
                 "html": "", "revision": 0, "created_at": None}), \
             patch.object(routes.clinical, "list_diagnoses",
                          return_value=[confirmed, hypothesis]), \
             patch.object(routes.clinical, "list_encounters", return_value=[]), \
             patch.object(routes.intake, "scoped_summary", return_value=None), \
             patch.object(routes.assessments, "list_for_patient", return_value=[]):
            result = self.client.get("/saas/pacientes/21/atendimentos/67")
        self.assertEqual(result.status_code, 200)
        html = result.get_data(as_text=True)
        self.assertIn('data-clinic-tab="sessao"', html)
        self.assertIn('data-clinic-tab="instrumentos"', html)
        self.assertIn('name="hypothesis_id"', html)
        self.assertIn('<option value="8">', html)
        self.assertNotIn('<option value="9">', html)
        self.assertIn("saas-encounter.js", html)
        self.assertIn("saas-encounter.css", html)

    def test_note_json_save_returns_revision_or_conflict_without_redirect(self):
        uri = "/saas/pacientes/21/atendimentos/67/nota"
        payload = {"csrf_token": "clinical-csrf-test", "html": "<p>Teste</p>",
                   "revision": "4"}
        with patch.object(routes.clinical, "save_note", return_value=5) as save:
            result = self.client.post(uri, data=payload,
                                      headers={"Accept": "application/json"})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json, {"ok": True, "revision": 5})
        self.assertEqual(result.headers.get("Cache-Control"), "private, no-store")
        save.assert_called_once_with(7, 11, 21, 67, "<p>Teste</p>", "4")
        with patch.object(routes.clinical, "save_note",
                          side_effect=ValueError("Este atendimento mudou em outra aba.")):
            conflict = self.client.post(uri, data=payload,
                                        headers={"Accept": "application/json"})
        self.assertEqual(conflict.status_code, 409)
        self.assertFalse(conflict.json["ok"])

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
