"""Explicit chart-reading permission and privacy; synthetic fixtures only."""
import unittest
import re
from unittest.mock import patch

from app import app
from saas.core import saas_store as store
from saas.clinical import saas_assessment_flow as assessments
from saas.neurocore import saas_neurocore_routes as core_routes
from saas.clinical import saas_clinical_routes as clinical_routes
from neurocore import record_context
from bta_license_client import LicenseDecision


class OwnedRecordContextTests(unittest.TestCase):
    def test_foreign_patient_never_reaches_chart_services(self):
        with patch.object(record_context.patients, "scoped_client", return_value=None), \
             patch.object(record_context.clinical, "list_encounters") as visits:
            with self.assertRaises(PermissionError):
                record_context.read_owned_record(7, 11, 999)
            visits.assert_not_called()

    def test_reads_bounded_context_and_removes_html_markup(self):
        with patch.object(record_context.patients, "scoped_client",
                          return_value={"id": 16}), \
             patch.object(record_context.intake, "scoped_summary",
                          return_value={"initial_report": "Relato inicial sintético"}), \
             patch.object(record_context.clinical, "list_encounters",
                          return_value=[{"id": 88, "opened_at": "2026-11-01"}]) as visits, \
             patch.object(record_context.clinical, "latest_note",
                          return_value={"html": "<p>Observação <strong>clínica</strong></p>"}) as note, \
             patch.object(record_context.clinical, "list_diagnoses",
                          return_value=[{"label": "Hipótese registrada",
                                         "certainty": "hypothesis"}]) as diagnoses:
            context = record_context.read_owned_record(7, 11, 16)
        visits.assert_called_once_with(7, 11, client_id=16, limit=10)
        note.assert_called_once_with(7, 11, 16, 88)
        diagnoses.assert_called_once_with(7, 11, 16, 88)
        self.assertIn("Relato inicial", context["intake_text"])
        self.assertEqual(context["notes"][0]["text"], "Observação clínica")
        self.assertNotIn("<", context["notes"][0]["text"])
        self.assertEqual(context["prior_records"][0]["certainty"], "hypothesis")


class AuthorizedRecordRequestTests(unittest.TestCase):
    def setUp(self):
        self.old_testing = app.config["TESTING"]
        app.config["TESTING"] = True
        self.client = app.test_client()
        self.user = store.SaaSUser({
            "id": 7, "nome": "Profissional Sintético",
            "email": "record@example.invalid", "global_role": "professional",
            "active": 1, "must_change_password": 0})
        self.item = {
            "id": 55, "status": "submitted", "title": "Teste",
            "version_number": 1,
            "definition": {"kind": "assessment", "neurocore_topic": "tdah",
                           "questions": [{
                               "key": "q1", "label": "Observação", "type": "text",
                               "neurocore_field": "atencao_atividade"}]},
        }
        self.record = {
            "intake_text": "CUIDADO_PRIVADO_EXEMPLO", "visits_count": 1,
            "notes": [{"encounter_id": 88, "opened_at": "hoje",
                       "text": "Texto clínico fictício", "truncated": False}],
            "prior_records": [], "limit_notice": "Limite sintético",
        }
        self.patches = [
            patch.object(store, "get_user", return_value=self.user),
            patch.object(core_routes, "licensed_tenant",
                         return_value=({"id": 11, "nome": "Tenant"},
                                       LicenseDecision(status="exempt"))),
            patch.object(core_routes.nc_store, "scoped_client",
                         return_value={"id": 16, "nome": "Paciente de teste"}),
            patch.object(core_routes.nc_store, "get_review", return_value=None),
            patch.object(clinical_routes, "licensed_tenant",
                         return_value=({"id": 11, "nome": "Tenant"},
                                       LicenseDecision(status="exempt"))),
            patch.object(clinical_routes.nc, "scoped_client",
                         return_value={"id": 16, "nome": "Paciente de teste"}),
            patch.object(clinical_routes.assessments, "scoped_assessment",
                         return_value=self.item),
            patch.object(clinical_routes.assessments, "read_answers",
                         return_value={"q1": "Texto sintético"}),
            patch.object(core_routes.nc_learning, "list_feedback", return_value={}),
        ]
        for p in self.patches:
            p.start()
        with self.client.session_transaction() as session:
            session["_user_id"] = "saas:7"
            session["_fresh"] = True
            session["saas_auth"] = True
            session["saas_csrf"] = "record-csrf"

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        app.config["TESTING"] = self.old_testing

    def test_existing_neurocore_view_does_not_read_chart_until_requested(self):
        with patch.object(core_routes, "read_owned_record") as read:
            response = self.client.get("/saas/pacientes/16/neurocore/tdah")
            read.assert_not_called()
        self.assertEqual(response.status_code, 200)
        self.assertIn("Ler prontuário", response.get_data(as_text=True))
        self.assertNotIn("CUIDADO_PRIVADO_EXEMPLO", response.get_data(as_text=True))

    def test_post_requires_csrf_for_both_entry_points(self):
        for route in ("/saas/pacientes/16/neurocore/tdah",
                      "/saas/pacientes/16/instrumentos/55/neurocore"):
            response = self.client.post(route, data={"action": "read_record"})
            self.assertEqual(response.status_code, 400)

    def test_professional_explicitly_requests_chart_from_neurocore(self):
        with patch.object(core_routes, "read_owned_record",
                          return_value=self.record) as read:
            response = self.client.post("/saas/pacientes/16/neurocore/tdah",
                            data={"csrf_token": "record-csrf",
                                  "action": "read_record"})
        self.assertEqual(response.status_code, 200)
        read.assert_called_once_with(7, 11, 16)
        self.assertIn("CUIDADO_PRIVADO_EXEMPLO", response.get_data(as_text=True))
        self.assertEqual(response.headers["Cache-Control"], "private, no-store")

    def test_professional_can_request_chart_alongside_received_test(self):
        with patch.object(clinical_routes, "read_owned_record",
                          return_value=self.record) as read:
            response = self.client.post(
                "/saas/pacientes/16/instrumentos/55/neurocore",
                data={"csrf_token": "record-csrf", "action": "read_record",
                      "topic": "tdah"})
        self.assertEqual(response.status_code, 200)
        read.assert_called_once_with(7, 11, 16)
        self.assertIn("CUIDADO_PRIVADO_EXEMPLO", response.get_data(as_text=True))
        self.assertEqual(response.headers["Cache-Control"], "private, no-store")

    def test_signal_convergence_is_rendered_only_in_professional_review(self):
        self.item["definition"] = assessments.parse_definition({
            "neurocore_topic": "tdah",
            "questions": [
                {"key": "q1", "label": "Dificuldade de concentração",
                 "type": "yes_no", "neurocore_field": "atencao_atividade",
                 "options": [
                     {"value": "yes", "label": "Sim",
                      "neurocore_indicator": True},
                     {"value": "no", "label": "Não"},
                 ]},
            ],
        })
        chart = dict(self.record)
        chart["intake_text"] = "Dificuldade de concentração relatada."
        with patch.object(clinical_routes, "read_owned_record",
                          return_value=chart), \
             patch.object(clinical_routes.assessments, "read_answers",
                          return_value={"q1": "yes"}):
            response = self.client.post(
                "/saas/pacientes/16/instrumentos/55/neurocore",
                data={"csrf_token": "record-csrf", "action": "read_record",
                      "topic": "tdah"})
        self.assertEqual(response.status_code, 200)
        page = response.get_data(as_text=True)
        self.assertIn("Convergência documental", page)
        self.assertIn("Teste personalizado", page)
        self.assertIn("Anamnese", page)
        self.assertNotIn("probabilidade diagnóstica", page)

    def test_professional_can_confirm_chart_indicator_without_repeated_reward(self):
        chart = dict(self.record)
        chart["intake_text"] = "Dificuldade de concentração relatada."
        with patch.object(core_routes, "read_owned_record", return_value=chart), \
             patch.object(core_routes.nc_learning, "save_feedback") as saved:
            response = self.client.post(
                "/saas/pacientes/16/neurocore/tdah",
                data={"csrf_token": "record-csrf", "action": "read_record"})
            self.assertEqual(response.status_code, 200)
            keys = re.findall(r'name="signal_key" value="([0-9a-f]{64})"',
                              response.get_data(as_text=True))
            self.assertTrue(keys)
            data = {"csrf_token": "record-csrf",
                    "action": "feedback_indicator",
                    "domain_key": "atencao_atividade",
                    "signal_key": keys[0],
                    "verdict": "confirmado"}
            response = self.client.post("/saas/pacientes/16/neurocore/tdah",
                                        data=data)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(saved.call_count, 1)
            self.assertEqual(saved.call_args.args[0:4], (7, 11, 16, "tdah"))
            self.assertEqual(saved.call_args.args[5], "confirmado")
            data["signal_key"] = "0" * 64
            self.assertEqual(self.client.post(
                "/saas/pacientes/16/neurocore/tdah", data=data).status_code, 400)
            self.assertEqual(saved.call_count, 1)

    def test_received_test_feedback_requires_recomputed_indicator(self):
        self.item["definition"] = assessments.parse_definition({
            "neurocore_topic": "tdah",
            "questions": [{
                "key": "q1", "label": "Observação profissional", "type": "yes_no",
                "neurocore_field": "atencao_atividade",
                "options": [
                    {"value": "yes", "label": "Sim", "neurocore_indicator": True},
                    {"value": "no", "label": "Não"},
                ],
            }],
        })
        with patch.object(clinical_routes.assessments, "read_answers",
                          return_value={"q1": "yes"}), \
             patch.object(clinical_routes.nc_learning, "save_feedback") as saved, \
             patch.object(clinical_routes, "read_owned_record") as chart:
            page = self.client.get(
                "/saas/pacientes/16/instrumentos/55/neurocore")
            self.assertEqual(page.status_code, 200)
            self.assertIn("Confirmar", page.get_data(as_text=True))
            key = re.findall(r'name="signal_key" value="([0-9a-f]{64})"',
                             page.get_data(as_text=True))[0]
            response = self.client.post(
                "/saas/pacientes/16/instrumentos/55/neurocore",
                data={"csrf_token": "record-csrf",
                      "action": "feedback_indicator", "topic": "tdah",
                      "with_record": "0", "domain_key": "atencao_atividade",
                      "signal_key": key, "verdict": "inconclusivo"})
            self.assertEqual(response.status_code, 200)
            chart.assert_not_called()
            self.assertEqual(saved.call_args.kwargs["assessment_id"], 55)
            self.assertEqual(saved.call_args.args[5], "inconclusivo")

    def test_patient_role_cannot_read_from_neurocore(self):
        self.user.role = "patient"
        for route in ("/saas/pacientes/16/neurocore/tdah",
                      "/saas/pacientes/16/instrumentos/55/neurocore"):
            response = self.client.post(route,
                data={"csrf_token": "record-csrf", "action": "read_record",
                      "topic": "tdah"})
            self.assertEqual(response.status_code, 403)


if __name__ == "__main__":
    unittest.main()
