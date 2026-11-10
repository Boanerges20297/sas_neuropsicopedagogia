"""Synthetic booking security contracts: ownership, conflict and portal access."""
from datetime import datetime, timezone, timedelta
from unittest import TestCase
from unittest.mock import patch
from pathlib import Path
from app import app
from flask_login import login_user

import saas_store as store
import saas_care_store as care
import saas_slot_booking as booking
import saas_slot_routes as routes

NOW = datetime(2026, 11, 10, 12, tzinfo=timezone.utc)
START = datetime(2026, 11, 12, 12)
END = datetime(2026, 11, 12, 13)


class Cursor:
    def __init__(self, rows=()):
        self.rows = list(rows)
        self.calls = []
        self.lastrowid = 990

    def execute(self, sql, args=()):
        self.calls.append((sql, args))

    def fetchone(self):
        return self.rows.pop(0) if self.rows else None


class Tx:
    def __init__(self, cur):
        self.cur = cur

    def __enter__(self):
        return self.cur

    def __exit__(self, *args):
        return False


class SlotsContracts(TestCase):
    def _publish(self, **overrides):
        params = dict(
            start_date="2026-11-12", end_date="2026-11-12",
            weekdays=["3"], open_time="09:00", close_time="10:00",
            duration=60, gap=0, service_type="initial", modality="remote",
            now=NOW)
        params.update(overrides)
        return booking.publish_slots(7, 11, **params)

    def test_publish_serializes_and_audits_without_double_booking(self):
        cur = Cursor([{"user_id": 7}, None, None])
        with patch.object(store, "transaction", return_value=Tx(cur)), \
             patch.object(store, "audit") as audit:
            self.assertEqual(self._publish(), 1)
        sqls = [s for s, _ in cur.calls]
        self.assertIn("FOR UPDATE", sqls[0])
        self.assertIn("care_schedule_slots", sqls[1])
        self.assertIn("care_appointments", sqls[2])
        self.assertIn("INSERT INTO care_schedule_slots", sqls[3])
        self.assertEqual(cur.calls[3][1][0:4], (11, 7, START, END))
        audit.assert_called_once()

    def test_overlap_or_unauthorized_member_cannot_publish(self):
        cur = Cursor([{"user_id": 7}, {"id": 42}])
        with patch.object(store, "transaction", return_value=Tx(cur)):
            with self.assertRaisesRegex(ValueError, "publicado"):
                self._publish()
        self.assertFalse(any("INSERT INTO care_schedule_slots" in sql
                             for sql, _ in cur.calls))
        cur = Cursor([None])
        with patch.object(store, "transaction", return_value=Tx(cur)):
            with self.assertRaises(PermissionError):
                self._publish()
        self.assertEqual(len(cur.calls), 1)

    def test_publish_bounded_and_validates_weekdays(self):
        for invalid in (
            {"weekdays": []}, {"weekdays": ["8"]},
            {"end_date": "2027-01-01"}, {"duration": 17},
            {"open_time": "09:07"}, {"close_time": "08:00"},
        ):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                self._publish(**invalid)

    def test_patient_request_is_scoped_and_locks_slot(self):
        row = dict(id=51, tenant_id=11, professional_user_id=7, status="open",
                   starts_at_utc=START, ends_at_utc=END)
        cur = Cursor([
            {"user_id": 7}, {"id": 81, "global_role": "patient", "active": 1},
            {"id": 21}, {"allowed": 1}, row, None])
        with patch.object(store, "transaction", return_value=Tx(cur)), \
             patch.object(store, "audit") as audit:
            self.assertEqual(booking.patient_slot_action(
                81, 11, 21, 7, 51, "request"), "request")
        self.assertIn("FOR UPDATE", cur.calls[0][0])
        self.assertIn("SELECT * FROM care_schedule_slots", cur.calls[4][0])
        self.assertIn("status='pending'", cur.calls[-1][0])
        self.assertEqual(cur.calls[-1][1], (81, 21, 51))
        audit.assert_called_once()

    def test_patient_cannot_request_without_verified_consent(self):
        cur = Cursor([
            {"user_id": 7}, {"id": 81, "global_role": "patient", "active": 1},
            {"id": 21}, None, None])
        with patch.object(store, "transaction", return_value=Tx(cur)):
            with self.assertRaises(PermissionError):
                booking.patient_slot_action(81, 11, 21, 7, 51, "request")
        self.assertFalse(any("UPDATE care_schedule_slots" in sql for sql, _ in cur.calls))
        self.assertIn("care_portal_self_grants", cur.calls[-1][0])

    def test_patient_cannot_request_slot_held_by_another(self):
        cur = Cursor([
            {"user_id": 7}, {"id": 81, "global_role": "patient", "active": 1},
            {"id": 21}, {"allowed": 1},
            {"id": 51, "status": "pending", "starts_at_utc": START}])
        with patch.object(store, "transaction", return_value=Tx(cur)):
            with self.assertRaisesRegex(ValueError, "disponível"):
                booking.patient_slot_action(81, 11, 21, 7, 51, "request")
        self.assertFalse(any("UPDATE care_schedule_slots" in sql for sql, _ in cur.calls))

    def test_professional_accepts_with_active_grant_and_atomically_books(self):
        cur = Cursor([
            {"user_id": 7},
            dict(id=51, status="pending", pending_user_id=81,
                 pending_client_id=21, starts_at_utc=START, ends_at_utc=END,
                 service_type="initial", modality="remote"),
            {"id": 21}, None, {"allowed": 1}])
        with patch.object(store, "transaction", return_value=Tx(cur)), \
             patch.object(store, "audit") as audit:
            self.assertEqual(booking.change_slot(7, 11, 51, action="accept"),
                             "accept")
        self.assertIn("INSERT INTO care_appointments", cur.calls[-2][0])
        self.assertIn("status='booked'", cur.calls[-1][0])
        audit.assert_called_once()

    def test_professional_cannot_accept_revoked_access(self):
        cur = Cursor([
            {"user_id": 7},
            dict(id=51, status="pending", pending_user_id=81,
                 pending_client_id=21, starts_at_utc=START, ends_at_utc=END,
                 service_type="initial", modality="remote"),
            {"id": 21}, None, None, None])
        with patch.object(store, "transaction", return_value=Tx(cur)):
            with self.assertRaises(PermissionError):
                booking.change_slot(7, 11, 51, action="accept")
        self.assertFalse(any("INSERT INTO care_appointments" in q
                             for q, _ in cur.calls))

    def test_close_slot_preserves_row_and_audits(self):
        cur = Cursor([{"user_id": 7}, {"id": 51, "status": "open"}])
        with patch.object(store, "transaction", return_value=Tx(cur)), \
             patch.object(store, "audit") as audit:
            self.assertEqual(booking.change_slot(7, 11, 51, action="close"), "close")
        self.assertIn("status='closed'", cur.calls[-1][0])
        self.assertNotIn("DELETE FROM", cur.calls[-1][0])
        audit.assert_called_once()

    def test_only_requesting_patient_can_withdraw(self):
        cur = Cursor([
            {"user_id": 7}, {"id": 81, "global_role": "patient", "active": 1},
            {"id": 21}, {"allowed": 1},
            {"id": 51, "status": "pending", "pending_user_id": 999,
             "pending_client_id": 21}])
        with patch.object(store, "transaction", return_value=Tx(cur)):
            with self.assertRaises(PermissionError):
                booking.patient_slot_action(81, 11, 21, 7, 51, "withdraw")
        self.assertFalse(any("UPDATE care_schedule_slots" in sql for sql, _ in cur.calls))

    def test_no_hard_deletes_of_slots_or_appointments(self):
        schema = (Path(__file__).resolve().parents[1] / "scripts" /
                  "mysql_care_workflow_migration.sql").read_text(encoding="utf-8")
        self.assertIn("CREATE TABLE IF NOT EXISTS care_schedule_slots", schema)
        self.assertIn("FOREIGN KEY(pending_client_id,tenant_id)", schema)
        self.assertIn("chk_schedule_slot_state", schema)
        self.assertNotIn("DROP TABLE", schema.upper())
        src = (Path(__file__).resolve().parents[1] / "saas_slot_booking.py").read_text(
            encoding="utf-8")
        self.assertNotIn("DELETE FROM care_schedule_slots", src)
        docker = (Path(__file__).resolve().parents[1] / "Dockerfile").read_text(
            encoding="utf-8")
        self.assertIn("saas_slot_booking.py saas_slot_routes.py", docker)


class PatientCalendarHttpTests(TestCase):
    def setUp(self):
        self.prev = app.config["TESTING"]
        app.config["TESTING"] = True
        self.client = app.test_client()
        self.user = store.SaaSUser({
            "id": 81, "nome": "Responsável Sintético",
            "email": "example@example.invalid",
            "global_role": "patient", "active": True,
            "must_change_password": False})
        self.patches = [
            patch.object(store, "get_user", return_value=self.user),
            patch.object(routes.slots, "eligible_patients", return_value=[]),
        ]
        for p in self.patches:
            p.start()
        with self.client.session_transaction() as session:
            session["_user_id"] = "saas:81"
            session["_fresh"] = True
            session["saas_auth"] = True
            session["saas_csrf"] = "patient-test-csrf"

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        app.config["TESTING"] = self.prev

    def test_empty_portal_is_private_and_explains_pending_link(self):
        resp = self.client.get("/saas/minha-agenda")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.headers["Cache-Control"], "private, no-store")
        self.assertIn("aguardando liberação", resp.get_data(as_text=True))
        self.assertEqual(self.client.get("/saas/painel").status_code, 302)

    def test_patient_post_requires_csrf_and_real_grant(self):
        url = "/saas/minha-agenda/11/21/51/acao"
        with patch.object(routes.slots, "patient_slot_action") as action:
            self.assertEqual(self.client.post(url, data={"csrf_token": "bad"}).status_code,
                             400)
            self.assertEqual(self.client.post(
                url, data={"csrf_token":"patient-test-csrf","action":"request"}).status_code,
                404)
            action.assert_not_called()

    def test_verified_patient_sees_only_own_slots(self):
        linked = {"tenant_id": 11, "client_id": 21, "professional_user_id": 7,
                  "client_name": "Paciente Fictício", "clinician_name": "Profissional",
                  "tenant_name": "Consultório"}
        slot = {"id": 51, "local_start": "12/11/2026 09:00", "minutes": 60,
                "service_type": "initial", "modality": "remote"}
        with patch.object(routes.slots, "eligible_patients", return_value=[linked]), \
             patch.object(routes.slots, "available_for_client", return_value=[slot]) as available, \
             patch.object(routes.slots, "patient_requests", return_value=[]):
            resp = self.client.get("/saas/minha-agenda?client_id=21")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Solicitar este horário", resp.get_data(as_text=True))
        self.assertEqual(resp.headers["Cache-Control"], "private, no-store")
        available.assert_called_once_with(81, 11, 21, 7)

    def test_portal_submit_only_for_own_linked_patient(self):
        linked = {"tenant_id": 11, "client_id": 21, "professional_user_id": 7,
                  "client_name": "Paciente Fictício", "clinician_name": "Profissional",
                  "tenant_name": "Consultório"}
        with patch.object(routes.slots, "eligible_patients", return_value=[linked]), \
             patch.object(routes.slots, "patient_slot_action", return_value="request") as act:
            response = self.client.post(
                "/saas/minha-agenda/11/21/51/acao",
                data={"csrf_token":"patient-test-csrf","action":"request"})
            self.assertEqual(response.status_code, 302)
            act.assert_called_once_with(81, 11, 21, 7, 51, "request")
            self.assertEqual(self.client.post(
                "/saas/minha-agenda/12/21/51/acao",
                data={"csrf_token":"patient-test-csrf","action":"request"}).status_code,404)
