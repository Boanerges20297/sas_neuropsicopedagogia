"""Synthetic contract tests: clinical privacy, versions and portal fail-closed."""
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4
import unittest
import os

import saas_clinical_flow as clinical
import saas_assessment_flow as assessments

ROOT = Path(__file__).resolve().parents[1]


class Cursor:
    def __init__(self, rows=None):
        self.rows = list(rows or [])
        self.calls = []
        self.lastrowid = 951
    def execute(self, statement, args=()):
        self.calls.append((statement, args))
    def fetchone(self):
        return self.rows.pop(0) if self.rows else None


@contextmanager
def tx(cursor):
    yield cursor


class ClinicalContracts(unittest.TestCase):
    def test_sanitizer_removes_executable_markup_and_attributes(self):
        original = ('<p onclick="x()">Olá <strong id="a">mundo</strong></p>'
                    '<script>alert(1)</script><img src=x onerror=alert(2)>'
                    '<svg onload=alert(3)>x</svg>')
        clean = clinical.sanitize_note(original)
        self.assertIn("<strong>mundo</strong>", clean)
        self.assertNotIn("onclick", clean)
        self.assertNotIn("onerror", clean)
        self.assertNotIn("<script", clean)
        self.assertNotIn("<svg", clean)
        self.assertNotIn("alert", clean)
        with self.assertRaises(ValueError):
            clinical.sanitize_note("X"*30001)

    def test_clinical_encryption_is_not_plaintext_and_is_domain_separated(self):
        with patch.dict(os.environ, {"SECRET_KEY": "unit-only-"+ "a"*60}):
            encrypted = clinical.encrypt_text("<p>Dados sintéticos</p>", "encounter-note")
            self.assertNotIn(b"Dados", encrypted)
            self.assertEqual(
                clinical.decrypt_text(encrypted, "encounter-note"),
                "<p>Dados sintéticos</p>")
            with self.assertRaises(Exception):
                clinical.decrypt_text(encrypted, "assessment-answer")

    def test_filter_boundaries(self):
        self.assertEqual(clinical._range("day", "2026-11-09")[3], "2026-11-09")
        self.assertEqual(clinical._range("month", "2026-11")[3], "2026-11")
        self.assertEqual(clinical._range("year", "2026")[3], "2026")
        for period, anchor in (("week","2026"), ("month","2026-15"),
                               ("day","2026-02-30"), ("year","2001")):
            with self.assertRaises(ValueError):
                clinical._range(period, anchor)

    def test_start_scopes_and_is_idempotent(self):
        rid = str(uuid4())
        cur = Cursor([{"id": 23}, None])
        with patch.object(clinical.store, "transaction", lambda: tx(cur)), \
             patch.object(clinical.store, "audit"):
            self.assertEqual(clinical.start_encounter(7, 11, 23, rid), 951)
        self.assertIn("FOR UPDATE", cur.calls[0][0])
        self.assertIn("INSERT INTO care_encounters", cur.calls[2][0])
        cur2 = Cursor([{"id": 23}, {"client_id": 23, "encounter_id": 123}])
        with patch.object(clinical.store, "transaction", lambda: tx(cur2)), \
             patch.object(clinical.store, "audit") as audit:
            self.assertEqual(clinical.start_encounter(7, 11, 23, rid), 123)
            audit.assert_not_called()
        cur3 = Cursor([None])
        with patch.object(clinical.store, "transaction", lambda: tx(cur3)):
            with self.assertRaises(PermissionError):
                clinical.start_encounter(7, 11, 999, rid)

    def test_note_conflict_preserves_previous_revision(self):
        cur = Cursor([{"id": 23}, {"id": 67, "status": "draft"},
                      {"revision": 4}])
        with patch.object(clinical.store, "transaction", lambda: tx(cur)), \
             patch.object(clinical.store, "audit"), \
             patch.dict(os.environ, {"SECRET_KEY": "test-only-"+"x"*64}):
            with self.assertRaisesRegex(ValueError, "outra aba"):
                clinical.save_note(7, 11, 23, 67, "<p>Texto</p>", 2)
        self.assertFalse(any("INSERT INTO care_encounter_notes" in q
                             for q, _ in cur.calls))

    def test_diagnosis_requires_professional_confirmation(self):
        with self.assertRaises(ValueError):
            clinical.record_diagnosis(7, 11, 23, 67, "x")
        with self.assertRaises(ValueError):
            clinical.record_diagnosis(7, 11, 23, 67, "Hipótese", certainty="automatic")
        with patch.object(clinical.store, "one",
                          side_effect=[{"total": 3, "unique_clients": 2},
                                       {"total": 4, "answered": 1}]), \
             patch.object(clinical.store, "all_rows",
                          side_effect=[[{"label": "Diagnóstico sintético", "quantity": 1}],
                                       [{"bucket": "09/11", "quantity": 3}]]):
            data = clinical.professional_dashboard(7, 11, "month", "2026-11")
        self.assertEqual(data["tests_answered"], 1)
        self.assertEqual(data["diagnoses"][0]["quantity"], 1)

    def test_dashboard_timeline_sql_uses_pymysql_escaping_in_every_period(self):
        # A DATE_FORMAT('%d/%m') without escaping raises ProgrammingError
        # during Cursor.mogrify, before MySQL even sees the query.
        from pymysql.connections import Connection
        from pymysql.cursors import Cursor
        cursor = Cursor(Connection(host="localhost", user="synthetic",
                                   defer_connect=True))
        expected = {
            ("day", "2026-11-10"): "%H:00",
            ("month", "2026-11"): "%d/%m",
            ("year", "2026"): "%m/%Y",
        }
        for (period, anchor), date_format in expected.items():
            with self.subTest(period=period):
                compiled = []

                def check_sql(sql, args):
                    rendered = cursor.mogrify(sql, args)
                    compiled.append(rendered)
                    return []

                with patch.object(clinical.store, "one", side_effect=[
                    {"total": 0, "unique_clients": 0},
                    {"total": 0, "answered": 0},
                ]), patch.object(clinical.store, "all_rows", side_effect=check_sql):
                    data = clinical.professional_dashboard(7, 11, period, anchor)
                self.assertEqual(data["total"], 0)
                self.assertEqual(len(compiled), 2)
                self.assertIn("DATE_FORMAT(", compiled[1])
                self.assertIn("'" + date_format + "'", compiled[1])
                self.assertIn("e.tenant_id=11", compiled[1])
                self.assertIn("e.professional_user_id=7", compiled[1])

    def test_diagnostic_hypotheses_follow_patient_across_encounters(self):
        with patch.object(clinical, "scoped_encounter", return_value=None), \
             patch.object(clinical.store, "all_rows") as rows:
            with self.assertRaises(PermissionError):
                clinical.list_diagnoses(7, 11, 23, 67)
            rows.assert_not_called()
        prior = [{"id": 88, "encounter_id": 61, "certainty": "hypothesis"}]
        with patch.object(clinical, "scoped_encounter", return_value={"id": 67}), \
             patch.object(clinical.store, "all_rows", return_value=prior) as rows:
            self.assertEqual(clinical.list_diagnoses(7, 11, 23, 67), prior)
        sql, args = rows.call_args.args
        for filter_clause in ("d.tenant_id=%s", "d.client_id=%s",
                              "d.professional_user_id=%s",
                              "e.professional_user_id=d.professional_user_id"):
            self.assertIn(filter_clause, sql)
        self.assertNotIn("AND d.encounter_id=%s", sql)
        self.assertEqual(args, (11, 23, 7))

    def test_read_scope_includes_owner_tenant_and_active_membership(self):
        with patch.object(clinical.store, "one", return_value=None) as query:
            self.assertIsNone(clinical.scoped_encounter(7, 11, 23, 99))
        sql, args = query.call_args.args
        for text in ("e.tenant_id=%s", "e.client_id=%s",
                     "e.professional_user_id=%s", "m.status='active'",
                     "c.status='active'"):
            self.assertIn(text, sql)
        self.assertEqual(args, (99, 11, 23, 7, 7))


class QuestionnaireContracts(unittest.TestCase):
    def setUp(self):
        self.definition = {"kind": "anamnesis", "questions": [
            {"key": "development", "type": "single", "label": "Desenvolvimento",
             "options": [{"value": "typical", "label": "Típico"},
                         {"value": "unknown", "label": "Não informado"}],
             "required": True},
            {"key": "school", "type": "text", "label": "Vida escolar"},
            {"key": "behaviors", "type": "multiple", "label": "Comportamentos",
             "options": [{"value": "a", "label": "A"},
                         {"value": "b", "label": "B"}]}
        ]}

    def test_schema_is_strict_and_versioned(self):
        form = assessments.parse_definition(self.definition)
        self.assertEqual(form["kind"], "anamnesis")
        with self.assertRaises(ValueError):
            assessments.parse_definition({})
        with self.assertRaises(ValueError):
            assessments.parse_definition({"questions": []})
        with self.assertRaises(ValueError):
            assessments.parse_definition({"questions": [
                {"key": "a", "type": "html", "label": "HTML"}]})

    def test_answers_validate_required_and_fixed_options(self):
        questions = assessments.parse_definition(self.definition)["questions"]
        valid = {"development": "typical", "school": "Relato fictício",
                 "behaviors": ["a", "b"]}
        self.assertEqual(assessments._validate_answers(
            questions, valid, True), valid)
        with self.assertRaisesRegex(ValueError, "obrigatória"):
            assessments._validate_answers(questions, {"school": "x"}, True)
        with self.assertRaisesRegex(ValueError, "Opção inválida"):
            assessments._validate_answers(
                questions, {"development": "<script>"}, True)
        with self.assertRaises(ValueError):
            assessments._validate_answers(
                questions, {"development": "typical", "unlisted": "hidden"}, False)

    def test_patient_portal_does_not_receive_a_public_route(self):
        from app import app
        paths = {rule.rule for rule in app.url_map.iter_rules()}
        self.assertIn("/saas/pacientes/<int:client_id>/instrumentos/<int:assessment_id>", paths)
        self.assertNotIn("/saas/portal/instrumentos/<int:assessment_id>", paths)
        sql = (ROOT / "scripts/mysql_care_encounters_assessments_migration.sql").read_text(
            encoding="utf-8")
        self.assertIn("ciphertext LONGBLOB", sql)
        self.assertIn("care_assessment_workflows", sql)
        self.assertNotIn("DROP TABLE", sql.upper())

    def test_existing_responses_schema_is_not_used(self):
        source = (ROOT / "saas_assessment_flow.py").read_text(encoding="utf-8")
        self.assertIn("care_assessment_private_answers", source)
        self.assertNotIn("INSERT INTO assessment_responses", source)
        self.assertIn("mode", source)
        docker = (ROOT / "Dockerfile").read_text(encoding="utf-8")
        for fname in ("saas_clinical_flow.py", "saas_assessment_flow.py",
                      "saas_clinical_routes.py"):
            self.assertIn(fname, docker)
