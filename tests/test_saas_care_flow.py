"""Professional-client scheduling contracts with synthetic identities only."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4
import unittest

from app import app
from bta_license_client import LicenseDecision
import saas_store
import saas_care_store as care
import saas_care_routes as routes

ROOT = Path(__file__).resolve().parents[1]


class MemoryCursor:
    def __init__(self, rows, *, lastrowid=301):
        self.rows = list(rows)
        self.calls = []
        self.lastrowid = lastrowid

    def execute(self, sql, params=()):
        self.calls.append((sql, params))

    def fetchone(self):
        return self.rows.pop(0) if self.rows else None


class FakeTransaction:
    def __init__(self, cur):
        self.cur = cur

    def __enter__(self):
        return self.cur

    def __exit__(self, exc_type, exc, tb):
        return False


class SchedulingContracts(unittest.TestCase):
    def setUp(self):
        self.request_id = str(uuid4())
        self.now = datetime(2026, 11, 7, 12, tzinfo=timezone.utc)

    def test_local_time_converts_to_utc(self):
        start, end = care.parse_start("2026-11-08T09:15", 45, now=self.now)
        self.assertEqual(start, datetime(2026, 11, 8, 12, 15))
        self.assertEqual(end, datetime(2026, 11, 8, 13, 0))

    def test_strict_intervals_and_idempotency_identifier(self):
        for raw_time, minutes in (
            ("2026-11-08T09:10", 60), ("2026-11-08T09:00", 7),
            ("2020-11-08T09:00", 60), ("2029-11-08T09:00", 60),
            ("invalid", 30),
        ):
            with self.subTest(raw_time=raw_time, minutes=minutes):
                with self.assertRaises(ValueError):
                    care.parse_start(raw_time, minutes, now=self.now)
        self.assertEqual(care.normalize_request_id(self.request_id), self.request_id)
        for bad in ("nope", "0"*36, "a"*200):
            with self.assertRaises(ValueError):
                care.normalize_request_id(bad)

    def test_create_is_transactional_scoped_and_overlap_checked(self):
        cur = MemoryCursor([{"id": 21}, None, None])
        with patch.object(care.store, "transaction",
                          return_value=FakeTransaction(cur)), \
             patch.object(care.store, "audit") as audit:
            appointment_id = care.create_appointment(
                7, 11, 21, local_start="2026-11-08T09:00", duration="60",
                service_type="initial", modality="in_person",
                request_id=self.request_id, now=self.now,
            )
        self.assertEqual(appointment_id, 301)
        self.assertEqual(len(cur.calls), 6)
        self.assertIn("FOR UPDATE", cur.calls[0][0])
        self.assertIn("c.professional_user_id=%s", cur.calls[0][0])
        self.assertIn("status IN ('scheduled','confirmed')", cur.calls[2][0])
        self.assertIn("status='pending'", cur.calls[3][0])
        self.assertIn("INSERT INTO care_appointments", cur.calls[4][0])
        self.assertIn("UPDATE care_schedule_slots", cur.calls[5][0])
        self.assertEqual(cur.calls[4][1][0:4], (11, 21, 7, self.request_id))
        audit.assert_called_once()

    def test_duplicate_post_returns_original_without_new_insert(self):
        cur = MemoryCursor([{"id": 21}, {"id": 391, "client_id": 21}])
        with patch.object(care.store, "transaction",
                          return_value=FakeTransaction(cur)), \
             patch.object(care.store, "audit") as audit:
            result = care.create_appointment(
                7, 11, 21, local_start="2026-11-08T09:00", duration=60,
                service_type="initial", modality="in_person",
                request_id=self.request_id, now=self.now,
            )
        self.assertEqual(result, 391)
        self.assertEqual(len(cur.calls), 2)
        audit.assert_not_called()

    def test_request_uuid_cannot_be_reused_for_different_client(self):
        cur = MemoryCursor([{"id": 21}, {"id": 391, "client_id": 22}])
        with patch.object(care.store, "transaction",
                          return_value=FakeTransaction(cur)):
            with self.assertRaisesRegex(ValueError, "outro cliente"):
                care.create_appointment(
                    7, 11, 21, local_start="2026-11-08T09:00", duration=60,
                    service_type="initial", modality="in_person",
                    request_id=self.request_id, now=self.now,
                )
        self.assertEqual(len(cur.calls), 2)

    def test_overlap_denied_without_insert(self):
        cur = MemoryCursor([{"id": 21}, None, {"id": 88}])
        with patch.object(care.store, "transaction",
                          return_value=FakeTransaction(cur)):
            with self.assertRaisesRegex(ValueError, "já possui"):
                care.create_appointment(
                    7, 11, 21, local_start="2026-11-08T09:00", duration=60,
                    service_type="assessment", modality="remote",
                    request_id=self.request_id, now=self.now,
                )
        self.assertEqual(len(cur.calls), 3)

    def test_client_from_other_tenant_denied(self):
        cur = MemoryCursor([None])
        with patch.object(care.store, "transaction",
                          return_value=FakeTransaction(cur)):
            with self.assertRaises(PermissionError):
                care.create_appointment(
                    7, 11, 999, local_start="2026-11-08T09:00", duration=60,
                    service_type="initial", modality="in_person",
                    request_id=self.request_id, now=self.now,
                )
        self.assertEqual(len(cur.calls), 1)

    def test_completion_opens_one_encounter_and_audits(self):
        old_time = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=2)
        cur = MemoryCursor([{"id": 21},
                            {"id": 82, "status": "confirmed",
                             "starts_at_utc": old_time}])
        with patch.object(care.store, "transaction",
                          return_value=FakeTransaction(cur)), \
             patch.object(care.store, "audit") as audit:
            self.assertEqual(
                care.transition_appointment(7, 11, 21, 82, "completed"), "completed")
        self.assertIn("INSERT INTO care_encounters", cur.calls[3][0])
        self.assertEqual(cur.calls[3][1], (11, 82, 21, 7))
        audit.assert_called_once()

    def test_invalid_transitions_and_future_completion_denied(self):
        for previous, target, delta in (
            ("cancelled", "completed", -2),
            ("completed", "cancelled", -2),
            ("scheduled", "no_show", 24),
            ("scheduled", "completed", 24),
        ):
            with self.subTest(previous=previous, target=target):
                when = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=delta)
                cur = MemoryCursor([{"id": 21}, {"id": 82, "status": previous,
                                                "starts_at_utc": when}])
                with patch.object(care.store, "transaction",
                                  return_value=FakeTransaction(cur)):
                    with self.assertRaises(ValueError):
                        care.transition_appointment(7, 11, 21, 82, target)
                self.assertEqual(len(cur.calls), 2)

    def test_cannot_read_other_clients_appointments(self):
        with patch("saas_neurocore_store.scoped_client", return_value=None), \
             patch.object(care.store, "all_rows") as rows:
            with self.assertRaises(PermissionError):
                care.list_client_appointments(7, 11, 999)
            rows.assert_not_called()

    def test_calendar_query_has_tenant_owner_and_active_membership(self):
        with patch.object(care.store, "all_rows", return_value=[]) as rows:
            self.assertEqual(care.list_calendar(7, 11), [])
        sql, params = rows.call_args.args
        for part in ("a.tenant_id=%s", "a.professional_user_id=%s",
                     "c.professional_user_id=%s", "m.status='active'"):
            self.assertIn(part, sql)
        self.assertEqual(params, (7, 11, 7, 7, 30))


class CareRouteTests(unittest.TestCase):
    def setUp(self):
        self.was_testing = app.config["TESTING"]
        app.config["TESTING"] = True
        self.client = app.test_client()
        self.user = saas_store.SaaSUser({
            "id": 7, "nome": "Profissional Sintético", "email": "p@example.invalid",
            "global_role": "professional", "active": 1, "must_change_password": 0,
        })
        self.mocks = [
            patch.object(saas_store, "get_user", return_value=self.user),
            patch.object(routes, "licensed_tenant", return_value=(
                {"id": 11, "nome": "Consultório Teste"},
                LicenseDecision(status="exempt"))),
            patch.object(routes.nc, "scoped_client",
                         return_value={"id": 21, "nome": "Cliente Fictício"}),
            patch.object(routes.care, "list_calendar", return_value=[]),
            patch("saas_slot_booking.list_slots", return_value=[]),
            patch.object(saas_store, "list_clients", return_value=[]),
            patch.object(routes.care, "list_client_appointments", return_value=[]),
        ]
        for mock in self.mocks:
            mock.start()
        with self.client.session_transaction() as session:
            session["_user_id"] = "saas:7"
            session["_fresh"] = True
            session["saas_auth"] = True
            session["saas_csrf"] = "csrf-care-test"

    def tearDown(self):
        for mock in reversed(self.mocks):
            mock.stop()
        app.config["TESTING"] = self.was_testing

    def test_agenda_and_patient_page_render(self):
        self.assertEqual(self.client.get("/saas/agenda").status_code, 200)
        r = self.client.get("/saas/pacientes/21/agenda")
        self.assertEqual(r.status_code, 200)
        html = r.get_data(as_text=True)
        self.assertIn("Agenda de Cliente Fictício", html)
        self.assertIn("datetime-local", html)
        self.assertIn('name="csrf_token" value="csrf-care-test"', html)

    def test_post_create_uses_client_scope_and_csrf(self):
        payload = {"csrf_token": "csrf-care-test", "request_id": str(uuid4()),
                   "local_start": "2026-11-08T09:00", "duration": "60",
                   "service_type": "initial", "modality": "remote"}
        with patch.object(routes.care, "create_appointment", return_value=27) as create:
            response = self.client.post("/saas/pacientes/21/agenda", data=payload)
        self.assertEqual(response.status_code, 302)
        args = create.call_args
        self.assertEqual(args.args, (7, 11, 21))
        self.assertEqual(args.kwargs["service_type"], "initial")
        self.assertEqual(args.kwargs["request_id"], payload["request_id"])

    def test_csrf_unauthorized_and_foreign_client_denied(self):
        with patch.object(routes.care, "create_appointment") as create:
            self.assertEqual(self.client.post("/saas/pacientes/21/agenda",
                                              data={"csrf_token": "invalid"}).status_code, 400)
            create.assert_not_called()
        with patch.object(routes.nc, "scoped_client", return_value=None):
            self.assertEqual(self.client.get("/saas/pacientes/21/agenda").status_code, 404)
            self.assertEqual(self.client.post(
                "/saas/pacientes/21/agenda",
                data={"csrf_token": "csrf-care-test"}).status_code, 404)
        with patch.object(routes, "licensed_tenant", return_value=(
                {"id": 11}, LicenseDecision(status="unlicensed"))):
            self.assertEqual(self.client.get("/saas/agenda").status_code, 403)
            self.assertEqual(self.client.get("/saas/pacientes/21/agenda").status_code, 403)

    def test_transition_requires_post_and_csrf(self):
        with patch.object(routes.care, "transition_appointment",
                          return_value="confirmed") as transition:
            self.assertIn(self.client.get(
                "/saas/pacientes/21/agenda/85/acao").status_code, (403, 405))
            self.assertEqual(self.client.post(
                "/saas/pacientes/21/agenda/85/acao",
                data={"csrf_token": "bad", "target": "confirmed"}).status_code, 400)
            transition.assert_not_called()
            r = self.client.post("/saas/pacientes/21/agenda/85/acao",
                data={"csrf_token": "csrf-care-test", "target": "confirmed"})
            self.assertEqual(r.status_code, 302)
            transition.assert_called_once_with(7, 11, 21, 85, "confirmed")


class MigrationAndRuntimeContracts(unittest.TestCase):
    def test_migration_only_adds_scoped_tables(self):
        schema = (ROOT / "scripts/mysql_care_workflow_migration.sql").read_text(
            encoding="utf-8")
        for table in ("care_client_contacts", "care_appointments", "care_encounters"):
            self.assertIn("CREATE TABLE IF NOT EXISTS " + table, schema)
        for clause in ("FOREIGN KEY(client_id,tenant_id)",
                       "FOREIGN KEY(tenant_id,professional_user_id)",
                       "UNIQUE KEY uq_care_request", "chk_care_interval"):
            self.assertIn(clause, schema)
        for prohibited in ("DROP TABLE", "TRUNCATE", "DELETE FROM users"):
            self.assertNotIn(prohibited, schema)

    def test_docker_contains_care_modules_and_no_sklearn(self):
        docker = (ROOT / "Dockerfile").read_text(encoding="utf-8")
        self.assertIn("saas_care_routes.py", docker)
        self.assertIn("saas_care_store.py", docker)
        self.assertNotIn("scikit-learn", (ROOT / "requirements.production.txt").read_text())

    def test_deploy_backup_before_both_migrations_and_web(self):
        script = (ROOT / "infra/host/deploy-neuro-diagnosis-saas.sh").read_text(
            encoding="utf-8")
        backup = script.index("NEURO_BACKUP_INVALID")
        care_migration = script.index("mysql_care_workflow_migration.sql")
        web = script.index('up -d --no-deps --force-recreate --no-build web', care_migration)
        self.assertLess(backup, care_migration)
        self.assertLess(care_migration, web)


if __name__ == "__main__":
    unittest.main()
