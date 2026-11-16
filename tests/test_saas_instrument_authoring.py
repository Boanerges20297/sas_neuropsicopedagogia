"""Instrument authoring, tenant isolation, approval and private scoring regression checks."""
import json
import math
import unittest
from contextlib import contextmanager
from unittest.mock import patch

from app import app
from saas.core import saas_store as store
from saas.clinical import saas_test_governance as governance
from saas.clinical import saas_assessment_flow as assessments
from bta_license_client import LicenseDecision


DEFINITION = {
    "kind": "assessment",
    "questions": [
        {"key": "sleep", "type": "single", "label": "Sono", "required": True,
         "options": [{"value": "yes", "label": "Sim", "points": 2},
                     {"value": "no", "label": "Não", "points": 0}]},
        {"key": "habits", "type": "multiple", "label": "Hábitos", "required": False,
         "options": [{"value": "a", "label": "Primeiro", "points": 1},
                     {"value": "b", "label": "Segundo", "points": 2}]},
        {"key": "observations", "type": "text", "label": "Observações",
         "required": False}
    ]
}


class RecordingCursor:
    def __init__(self, authorized=True, owns=True, already_pending=False):
        self.authorized = authorized
        self.owns = owns
        self.already_pending = already_pending
        self.sql = []
        self.lastrowid = 101
        self.row = None

    def execute(self, sql, args=()):
        self.sql.append((sql, args))
        if "SELECT u.id FROM users u" in sql:
            self.row = {"id": 7} if self.authorized else None
        elif "SELECT id,title,description FROM tests" in sql:
            self.row = {"id": 17, "title": "Avaliação de exemplo",
                        "description": "Descrição sintética"} if self.owns else None
        elif "SELECT id,version_number,definition_json FROM test_versions" in sql:
            self.row = {"id": 23, "version_number": 2,
                        "definition_json": json.dumps(DEFINITION)}
        elif "tenant_id IS NULL AND created_by" in sql:
            self.row = {"id": 66} if self.already_pending else None
        elif "SELECT id FROM tests WHERE id=" in sql:
            self.row = {"id": 17} if self.owns else None
        elif "SELECT COALESCE(MAX(version_number)" in sql:
            self.row = {"latest": 2}
        else:
            self.row = None

    def fetchone(self):
        return self.row


@contextmanager
def transaction(cursor):
    yield cursor


class ScoringBoundaryTests(unittest.TestCase):
    def test_scoring_remains_professional_and_patient_definition_has_no_points(self):
        definition = assessments.parse_definition(DEFINITION)
        score = assessments.professional_score(definition, {
            "sleep": "yes", "habits": ["a", "b"], "observations": "texto"})
        self.assertEqual(score, {"total": 5.0, "counted": 2, "scoreable": 2})
        public = assessments.public_definition(definition)
        self.assertNotIn("points", json.dumps(public))
        self.assertEqual(public["questions"][0]["options"][0]["label"], "Sim")

    def test_unanswered_has_no_score_not_a_false_zero(self):
        score = assessments.professional_score(DEFINITION, {})
        self.assertIsNone(score["total"])
        self.assertEqual(score["counted"], 0)

    def test_rejects_invalid_points_and_keeps_yes_no_normalized(self):
        for points in (True, "five", float("inf"), -101, 101):
            altered = json.loads(json.dumps(DEFINITION))
            altered["questions"][0]["options"][0]["points"] = points
            with self.assertRaises(ValueError):
                assessments.parse_definition(altered)
        q = {"questions": [{"key": "x", "type": "yes_no", "label": "Sintético",
                            "options": [{"value": "yes", "label": "Irrelevante",
                                         "points": 3}, {"value": "no",
                                                       "label": "Outro", "points": 0}]}]}
        norm = assessments.parse_definition(q)
        self.assertEqual(norm["questions"][0]["options"][0]["points"], 3.0)
        self.assertEqual(norm["questions"][0]["options"][0]["label"], "Sim")


class PrivateInstrumentServiceTests(unittest.TestCase):
    def _run(self, cursor, method, *args):
        with patch.object(store, "transaction", return_value=transaction(cursor)), \
             patch.object(store, "audit") as audit:
            result = method(*args)
        return result, cursor.sql, audit

    def test_private_creation_is_approved_only_within_owned_tenant(self):
        result, statements, audit = self._run(
            RecordingCursor(), governance.create_private_instrument,
            7, 11, "Avaliação de exemplo", "Descrição sintética", DEFINITION)
        self.assertEqual(result, 101)
        inserts = [(q, p) for q, p in statements if "INSERT INTO tests" in q]
        self.assertEqual(len(inserts), 1)
        self.assertIn("'private','approved'", inserts[0][0])
        self.assertEqual(inserts[0][1][0], 11)
        self.assertFalse(any("assessments" in q or "care_" in q for q, _ in statements))
        audit.assert_called_once()

    def test_inactive_or_foreign_membership_never_creates_test(self):
        cursor = RecordingCursor(authorized=False)
        with self.assertRaises(PermissionError):
            self._run(cursor, governance.create_private_instrument,
                      7, 999, "Teste privado", "", DEFINITION)
        self.assertFalse(any("INSERT INTO tests" in q for q, _ in cursor.sql))

    def test_revision_creates_new_version_without_touching_prior_answers(self):
        version, statements, audit = self._run(
            RecordingCursor(), governance.revise_private_instrument,
            7, 11, 17, "Teste revisado", "", DEFINITION)
        self.assertEqual(version, 3)
        self.assertTrue(any("INSERT INTO test_versions" in q for q, _ in statements))
        self.assertFalse(any("DELETE" in q or "assessments" in q for q, _ in statements))
        audit.assert_called_once()

    def test_submission_creates_global_pending_clone_and_keeps_private_test(self):
        result, statements, audit = self._run(
            RecordingCursor(), governance.submit_private_for_review, 7, 11, 17)
        self.assertEqual(result, 101)
        new_tests = [(q, p) for q, p in statements if "INSERT INTO tests" in q]
        self.assertEqual(len(new_tests), 1)
        self.assertIn("NULL", new_tests[0][0])
        self.assertIn("'global','pending'", new_tests[0][0])
        self.assertFalse(any("UPDATE tests SET" in q for q, _ in statements))
        self.assertFalse(any("assessments" in q for q, _ in statements))
        audit.assert_called_once()

    def test_duplicate_publication_request_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "pendente"):
            self._run(RecordingCursor(already_pending=True),
                      governance.submit_private_for_review, 7, 11, 17)

    def test_other_professional_cannot_submit_someone_elses_test(self):
        with self.assertRaises(PermissionError):
            self._run(RecordingCursor(owns=False),
                      governance.submit_private_for_review, 7, 11, 17)


class InstrumentEditorHTTPTests(unittest.TestCase):
    def setUp(self):
        self.old = app.config["TESTING"]
        app.config["TESTING"] = True
        self.client = app.test_client()
        self.user = store.SaaSUser({
            "id": 7, "nome": "Profissional de exemplo",
            "email": "test-author@example.invalid",
            "global_role": "professional", "active": 1,
            "must_change_password": 0})
        self.patches = [
            patch.object(store, "get_user", return_value=self.user),
            patch("saas.core.saas_routes.store.own_tenant",
                  return_value={"id": 11, "nome": "Espaço de teste"}),
            patch("saas.core.saas_routes.licensed_tenant",
                  return_value=({"id": 11, "nome": "Espaço de teste"},
                                LicenseDecision(status="exempt"))),
        ]
        for p in self.patches:
            p.start()
        with self.client.session_transaction() as session:
            session["_user_id"] = "saas:7"
            session["_fresh"] = True
            session["saas_auth"] = True
            session["saas_csrf"] = "test-author-csrf"

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        app.config["TESTING"] = self.old

    def test_editor_is_interactive_and_private(self):
        response = self.client.get("/saas/testes/criar")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Adicionar pergunta", response.get_data(as_text=True))
        self.assertIn("Pontos (opcional)", response.get_data(as_text=True))
        self.assertEqual(response.headers["Cache-Control"], "private, no-store")

    def test_post_requires_csrf_and_calls_scoped_creator(self):
        data = {"title": "Teste privado", "description": "",
                "definition_json": json.dumps(DEFINITION)}
        with patch.object(governance, "create_private_instrument", return_value=33) as create:
            bad = self.client.post("/saas/testes/criar", data=data)
            self.assertEqual(bad.status_code, 400)
            create.assert_not_called()
            okay = self.client.post("/saas/testes/criar",
                                    data={**data, "csrf_token": "test-author-csrf"})
            self.assertEqual(okay.status_code, 302)
            create.assert_called_once()

    def test_patient_cannot_open_editor_or_clinical_score(self):
        self.user.role = "patient"
        self.assertEqual(self.client.get("/saas/testes/criar").status_code, 403)
        self.assertEqual(
            self.client.get("/saas/pacientes/21/instrumentos/55").status_code, 403)

    def test_share_requires_explicit_rights_declaration(self):
        with patch.object(governance, "submit_private_for_review", return_value=33) as submit:
            no_rights = self.client.post("/saas/testes/17/compartilhar",
                                         data={"csrf_token": "test-author-csrf"})
            self.assertEqual(no_rights.status_code, 302)
            submit.assert_not_called()
            confirmed = self.client.post("/saas/testes/17/compartilhar",
                    data={"csrf_token": "test-author-csrf", "rights_confirm": "yes"})
            self.assertEqual(confirmed.status_code, 302)
            submit.assert_called_once_with(7, 11, 17)


if __name__ == "__main__":
    unittest.main()
