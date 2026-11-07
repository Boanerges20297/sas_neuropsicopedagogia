"""One account holder, one clinical patient profile; synthetic data only."""
from datetime import date
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch
import os

from app import app
from bta_license_client import LicenseDecision
import saas_patient_intake as intake
import saas_patient_intake_routes as routes
import saas_store as store


class FakeCursor:
    def __init__(self, rows, ids=(310, 610)):
        self.rows = list(rows)
        self.ids = iter(ids)
        self.calls = []
        self.lastrowid = None

    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        if "INSERT INTO clients" in sql or "INSERT INTO care_client_contacts" in sql:
            self.lastrowid = next(self.ids)

    def fetchone(self):
        return self.rows.pop(0) if self.rows else None


class Transaction:
    def __init__(self, cursor):
        self.cursor = cursor

    def __enter__(self):
        return self.cursor

    def __exit__(self, typ, exc, tb):
        return False


class PatientIntakeModelTests(TestCase):
    def test_no_duplicate_birth_date_or_login_table(self):
        schema = (Path(__file__).resolve().parents[1] / 'scripts' /
                  'mysql_care_patient_intake_migration.sql').read_text(encoding='utf-8')
        self.assertIn('CREATE TABLE IF NOT EXISTS care_patient_intakes', schema)
        self.assertNotIn('birth_date DATE', schema)
        self.assertNotIn('CREATE TABLE IF NOT EXISTS users', schema)
        self.assertIn('FOREIGN KEY (guardian_contact_id,tenant_id,client_id,professional_user_id)', schema)


    def test_age_derived_from_birth_date_not_saved_stale(self):
        self.assertEqual(intake.age_years(date(2014, 11, 8), date(2026, 11, 7)), 11)
        self.assertEqual(intake.age_years(date(2014, 11, 8), date(2026, 11, 8)), 12)

    def test_adult_self_validates(self):
        values = intake.validate_intake(
            "self", "Paciente Adulto", "1994-01-20", "Dificuldade de concentração")
        self.assertEqual(values["mode"], "self")
        self.assertEqual(values["guardian_name"], "")
        self.assertEqual(values["report"], "Dificuldade de concentração")

    def test_minor_requires_guardian_and_age(self):
        values = intake.validate_intake(
            "guardian", "Menor Fictício", "2015-02-20",
            "Dificuldade de interação", "Responsável Fictício", "guard@example.invalid")
        self.assertEqual(values["mode"], "guardian")
        self.assertEqual(values["guardian_name"], "Responsável Fictício")
        for args in (
            ("self", "Menor", "2015-02-20", "", "", ""),
            ("guardian", "Adulto", "1991-02-20", "", "Responsável", ""),
            ("guardian", "Menor", "2015-02-20", "", "", ""),
            ("guardian", "Menor", "2015-02-20", "", "Pai", "invalido"),
            ("invalido", "Menor", "2015-02-20", "", "Pai", ""),
            ("guardian", "Menor", "2029-01-01", "", "Pai", ""),
            ("guardian", "Menor", "2015-02-20", "x"*2001, "Pai", ""),
        ):
            with self.subTest(args=args), self.assertRaises(ValueError):
                intake.validate_intake(*args)

    def test_clinical_report_uses_purpose_separated_encryption(self):
        with patch.dict(os.environ, {"SECRET_KEY": "SyntheticSecretKeyForTestsOnlyMinimumLength1234"}):
            fernet = intake._cipher()
            original = "Relato inicial — sinais observados pela família."
            cipher = fernet.encrypt(original.encode("utf-8"))
            self.assertNotIn(original.encode("utf-8"), cipher)
            self.assertEqual(fernet.decrypt(cipher).decode("utf-8"), original)
        with patch.dict(os.environ, {"SECRET_KEY": "tiny"}), self.assertRaises(RuntimeError):
            intake._cipher()

    def test_minor_one_patient_one_contact_no_login_account_created(self):
        cursor = FakeCursor([{"allowed": 1}])
        with patch.dict(os.environ, {"SECRET_KEY": "SyntheticSecretKeyForTestsOnlyMinimumLength1234"}), \
             patch.object(intake.store, "transaction", return_value=Transaction(cursor)), \
             patch.object(intake.store, "audit") as audit:
            cid = intake.register_intake(
                7, 11, mode="guardian", name="Menor", birth_date="2015-11-01",
                initial_report="Relato familiar", guardian_name="Pai",
                guardian_email="pai@example.invalid",
            )
        self.assertEqual(cid, 310)
        sqls = [sql for sql, _ in cursor.calls]
        self.assertEqual(sum("INSERT INTO clients" in s for s in sqls), 1)
        self.assertEqual(sum("INSERT INTO care_client_contacts" in s for s in sqls), 1)
        self.assertEqual(sum("INSERT INTO care_patient_intakes" in s for s in sqls), 1)
        self.assertFalse(any("INSERT INTO users" in s for s in sqls))
        self.assertEqual(cursor.calls[-1][1][-1], 610)
        self.assertNotEqual(cursor.calls[-1][1][-2], b"Relato familiar")
        audit.assert_called_once()

    def test_adult_no_guardian_contact_no_user_account_created(self):
        cursor = FakeCursor([{"allowed": 1}])
        with patch.object(intake.store, "transaction", return_value=Transaction(cursor)), \
             patch.object(intake.store, "audit"):
            cid = intake.register_intake(
                7, 11, mode="self", name="Adulto",
                birth_date="1992-03-01", email="adult@example.invalid")
        self.assertEqual(cid, 310)
        self.assertFalse(any("INSERT INTO care_client_contacts" in sql for sql, _ in cursor.calls))
        self.assertFalse(any("INSERT INTO users" in sql for sql, _ in cursor.calls))
        self.assertEqual(cursor.calls[-1][1][-1], None)

    def test_no_unauthorized_tenant_writes(self):
        cursor = FakeCursor([None])
        with patch.object(intake.store, "transaction", return_value=Transaction(cursor)):
            with self.assertRaises(PermissionError):
                intake.register_intake(
                    7, 11, mode="guardian", name="Menor",
                    birth_date="2015-01-01", guardian_name="Pai")
        self.assertEqual(len(cursor.calls), 1)

    def test_initial_summary_checks_professional_ownership_first(self):
        with patch("saas_neurocore_store.scoped_client", return_value=None), \
             patch.object(intake.store, "one") as read:
            self.assertIsNone(intake.scoped_summary(7, 11, 999))
            read.assert_not_called()


class PatientIntakeRouteTests(TestCase):
    def setUp(self):
        self.previous = app.config["TESTING"]
        app.config["TESTING"] = True
        self.browser = app.test_client()
        user = store.SaaSUser({
            "id": 7, "nome": "Profissional", "email": "prof@example.invalid",
            "global_role": "professional", "active": True,
            "must_change_password": False,
        })
        self.patches = [
            patch.object(store, "get_user", return_value=user),
            patch("saas_routes.licensed_tenant", return_value=(
                {"id": 11, "nome": "Consultório"},
                LicenseDecision(status="exempt"))),
            patch.object(routes, "licensed_tenant", return_value=(
                {"id": 11, "nome": "Consultório"},
                LicenseDecision(status="exempt"))),
            patch.object(store, "list_clients", return_value=[]),
            patch.object(routes.nc, "scoped_client",
                         return_value={"id": 21, "nome": "Paciente Sintético"}),
            patch.object(routes.intake, "scoped_summary", return_value=None),
        ]
        for p in self.patches:
            p.start()
        with self.browser.session_transaction() as session:
            session["_user_id"] = "saas:7"
            session["_fresh"] = True
            session["saas_auth"] = True
            session["saas_csrf"] = "intake-csrf"

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        app.config["TESTING"] = self.previous

    def test_new_form_contains_both_paths_and_report(self):
        page = self.browser.get("/saas/pacientes")
        self.assertEqual(page.status_code, 200)
        html = page.get_data(as_text=True)
        self.assertIn('value="guardian"', html)
        self.assertIn('value="self"', html)
        self.assertIn('name="birth_date"', html)
        self.assertIn('name="initial_report"', html)

    def test_post_one_minor_not_two_accounts(self):
        with patch.object(intake, "register_intake", return_value=310) as create:
            response = self.browser.post("/saas/pacientes", data={
                "csrf_token": "intake-csrf", "representation_mode": "guardian",
                "nome": "Menor", "birth_date": "2017-05-07",
                "initial_report": "Relato informado", "guardian_name": "Mãe",
                "guardian_email": "mae@example.invalid"
            })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(create.call_args.args, (7, 11))
        self.assertEqual(create.call_args.kwargs["mode"], "guardian")
        self.assertEqual(create.call_args.kwargs["guardian_name"], "Mãe")

    def test_form_csrf_blocks_writes(self):
        with patch.object(intake, "register_intake") as create:
            resp = self.browser.post("/saas/pacientes", data={"csrf_token": "wrong"})
            self.assertEqual(resp.status_code, 400)
            create.assert_not_called()

    def test_clinical_notes_are_only_in_professional_route(self):
        res = self.browser.get("/saas/pacientes/21/dados-iniciais")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.headers["Cache-Control"], "private, no-store")
        with patch.object(routes.intake, "scoped_summary", return_value={
            "representation_mode": "guardian", "birth_date": date(2015, 1, 1),
            "age": 11, "guardian_name": "<script>",
            "initial_report": "<img src=x onerror=alert(1)>",
        }):
            page = self.browser.get("/saas/pacientes/21/dados-iniciais")
            self.assertEqual(page.status_code, 200)
            self.assertIn("&lt;script&gt;", page.get_data(as_text=True))
            self.assertNotIn("<img src=x onerror=", page.get_data(as_text=True))
        with patch.object(routes.nc, "scoped_client", return_value=None):
            self.assertEqual(
                self.browser.get("/saas/pacientes/21/dados-iniciais").status_code, 404)
        with patch.object(routes, "licensed_tenant", return_value=(
                {"id": 11}, LicenseDecision(status="unlicensed"))):
            self.assertEqual(
                self.browser.get("/saas/pacientes/21/dados-iniciais").status_code, 403)
