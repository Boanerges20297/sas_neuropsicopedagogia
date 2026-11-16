"""Optional NeuroCore feedback from submitted custom instruments; synthetic data only."""
import json
import unittest
from unittest.mock import patch

from app import app
from bta_license_client import LicenseDecision
from neurocore.assessment_feedback import received_test_feedback
from saas.clinical import saas_assessment_flow as assessments
from saas.clinical import saas_clinical_routes as routes
from saas.core import saas_store as store


DEFINITION = {
    "kind": "assessment",
    "neurocore_topic": "tdah",
    "questions": [
        {"key": "q1", "type": "single", "label": "Atenção observada",
         "neurocore_field": "atencao_atividade",
         "options": [
             {"value": "sim", "label": "Sim", "points": 3},
             {"value": "nao", "label": "Não", "points": 0},
         ]},
        {"key": "q2", "type": "text", "label": "Contextos",
         "neurocore_field": "contextos_multiplos"},
        {"key": "q3", "type": "text", "label": "Observações adicionais"},
    ],
}


class ClinicalFeedbackModelTests(unittest.TestCase):
    def test_mapping_is_validated_and_hidden_from_patient_payload(self):
        parsed = assessments.parse_definition(DEFINITION)
        self.assertEqual(parsed["neurocore_topic"], "tdah")
        self.assertEqual(parsed["questions"][0]["neurocore_field"], "atencao_atividade")
        public = assessments.public_definition(parsed)
        self.assertNotIn("neurocore", json.dumps(public))
        self.assertNotIn("points", json.dumps(public))

    def test_unknown_mapping_or_topic_is_rejected(self):
        for topic, field in (("tea", "atencao_atividade"),
                             ("invalid", "atencao_atividade"),
                             (None, "atencao_atividade")):
            altered = json.loads(json.dumps(DEFINITION))
            altered["neurocore_topic"] = topic
            altered["questions"][0]["neurocore_field"] = field
            with self.assertRaises(ValueError):
                assessments.parse_definition(altered)

    def test_optional_feedback_reports_coverage_not_diagnosis(self):
        result = received_test_feedback(
            DEFINITION, {"q1": "sim", "q2": "", "q3": "SENSITIVE_SENTINEL"}, "tdah")
        self.assertEqual(result["mapped_questions"], 2)
        self.assertEqual(result["answered_questions"], 1)
        self.assertEqual(result["unmapped_questions"], 1)
        by_key = {entry["key"]: entry for entry in result["areas"]}
        self.assertEqual(by_key["atencao_atividade"]["status"], "com_respostas")
        self.assertEqual(by_key["contextos_multiplos"]["status"], "sem_resposta")
        self.assertEqual(by_key["impacto_funcional"]["status"], "sem_vinculo")
        self.assertNotIn("SENSITIVE_SENTINEL", json.dumps(result))
        self.assertNotIn("sim", json.dumps(result["areas"][1]["questions"]))

    def test_wrong_topic_rejected_and_older_versions_are_supported(self):
        with self.assertRaises(ValueError):
            received_test_feedback(DEFINITION, {}, "tea")
        old = {"questions": [
            {"key": "q1", "type": "text", "label": "Livre"}]}
        result = received_test_feedback(old, {"q1": "text"}, "tea")
        self.assertFalse(result["has_mapping"])
        self.assertEqual(result["unmapped_questions"], 1)


class ClinicalFeedbackRouteTests(unittest.TestCase):
    def setUp(self):
        self.old_testing = app.config["TESTING"]
        app.config["TESTING"] = True
        self.client = app.test_client()
        self.user = store.SaaSUser({
            "id": 7, "nome": "Profissional Sintético",
            "email": "feedback@example.invalid",
            "global_role": "professional", "active": 1,
            "must_change_password": 0,
        })
        self.item = {
            "id": 55, "status": "submitted", "title": "Teste sintético",
            "version_number": 2, "definition": assessments.parse_definition(DEFINITION)
        }
        self.patches = [
            patch.object(store, "get_user", return_value=self.user),
            patch.object(routes, "licensed_tenant",
                         return_value=({"id": 11, "nome": "Espaço fictício"},
                                       LicenseDecision(status="exempt"))),
            patch.object(routes.nc, "scoped_client",
                         return_value={"id": 16, "nome": "Paciente sintético"}),
            patch.object(routes.assessments, "scoped_assessment",
                         return_value=self.item),
            patch.object(routes.assessments, "read_answers",
                         return_value={"q1": "sim", "q2": "SENSITIVE_SENTINEL"}),
            patch.object(routes.nc_learning, "list_feedback", return_value={}),
        ]
        for p in self.patches:
            p.start()
        with self.client.session_transaction() as session:
            session["_user_id"] = "saas:7"
            session["_fresh"] = True
            session["saas_auth"] = True
            session["saas_csrf"] = "feedback-test"

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        app.config["TESTING"] = self.old_testing

    def test_received_form_has_optional_feedback_without_running_it(self):
        response = self.client.get("/saas/pacientes/16/instrumentos/55")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Solicitar feedback documental", response.get_data(as_text=True))

    def test_professional_can_request_documentary_feedback(self):
        response = self.client.get("/saas/pacientes/16/instrumentos/55/neurocore")
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("Atenção observada", body)
        self.assertIn("Há respostas", body)
        self.assertIn("não aplica automaticamente os critérios diagnósticos", body)
        self.assertNotIn("SENSITIVE_SENTINEL", body)
        self.assertEqual(response.headers["Cache-Control"], "private, no-store")

    def test_pending_test_refuses_feedback(self):
        self.item["status"] = "pending"
        with patch.object(routes.assessments, "read_answers") as read:
            response = self.client.get("/saas/pacientes/16/instrumentos/55/neurocore")
            self.assertEqual(response.status_code, 409)
            read.assert_not_called()

    def test_foreign_assessment_cannot_be_reviewed(self):
        with patch.object(routes.assessments, "scoped_assessment", return_value=None):
            response = self.client.get("/saas/pacientes/16/instrumentos/55/neurocore")
        self.assertEqual(response.status_code, 404)

    def test_wrong_topic_is_not_accepted(self):
        response = self.client.get("/saas/pacientes/16/instrumentos/55/neurocore?topic=tea")
        self.assertEqual(response.status_code, 400)

    def test_patient_profile_cannot_see_feedback(self):
        self.user.role = "patient"
        response = self.client.get("/saas/pacientes/16/instrumentos/55/neurocore")
        self.assertEqual(response.status_code, 403)


if __name__ == "__main__":
    unittest.main()
