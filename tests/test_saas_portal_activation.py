"""Account activation is per client; admin/superadmin approve across tenants."""
import unittest
from datetime import date
from unittest.mock import patch

from app import app
from bta_license_client import LicenseDecision
import saas_store as store
import saas_portal_activation as activation
import saas_portal_activation_routes as activation_routes


class FakeCursor:
    def __init__(self, rows, login_status="pending"):
        self.rows = list(rows)
        self.calls = []
        self.login_status = login_status
        self.is_login_request = False
    def execute(self, sql, args=()):
        self.calls.append((sql, args))
        self.is_login_request = "FROM care_portal_login_requests" in sql
    def fetchone(self):
        if self.is_login_request:
            self.is_login_request = False
            return {"user_id":104, "status":self.login_status}
        return self.rows.pop(0) if self.rows else None


class Tx:
    def __init__(self, cursor):
        self.cursor = cursor
    def __enter__(self):
        return self.cursor
    def __exit__(self, typ, value, traceback):
        return False


def client(owner=11, tenant=201, dob=date(2015, 1, 1)):
    return {"id": 301, "tenant_id": tenant, "professional_user_id": owner,
            "birth_date": dob, "status": "active", "tenant_status": "active",
            "professional_membership": "active", "membership_role": "owner"}


def account(role="patient", active=0):
    return {"id": 104, "global_role": role, "active": active}


class ActivationRulesTests(unittest.TestCase):
    def execute(self, rows, *, actor=11, target=104, login_status="pending"):
        cursor = FakeCursor(rows, login_status=login_status)
        with patch.object(store, "transaction", return_value=Tx(cursor)), \
             patch.object(store, "audit") as audit:
            result = activation.activate_client_account(actor, 301, target)
        return result, cursor, audit

    def test_rejects_invalid_ids_without_query(self):
        with patch.object(store, "transaction") as tx:
            for bad in ((True,301,104), (11,0,104), (11,301,"104")):
                with self.assertRaises(ValueError):
                    activation.activate_client_account(*bad)
            tx.assert_not_called()

    def test_professional_must_own_patient(self):
        rows = [account("professional", 1), client(owner=22)]
        with self.assertRaises(PermissionError):
            self.execute(rows)
        rows = [account("professional", 1), client(owner=11),
                account("professional", 1)]
        with self.assertRaises(ValueError):
            self.execute(rows)

    def test_admin_and_superadmin_can_activate_across_tenants(self):
        for role in ("admin", "superadmin"):
            with self.subTest(role=role):
                rows = [account(role, 1), client(owner=22, tenant=202),
                        account(), {"representation_mode": "guardian",
                                    "guardian_contact_id": 601},
                        {"id": 710}, None]
                result, cur, audit = self.execute(rows, actor=33)
                self.assertTrue(result)
                self.assertTrue(any("INSERT INTO care_portal_client_activations"
                                    in sql for sql, _ in cur.calls))
                self.assertTrue(any("UPDATE users SET active=1" in sql
                                    for sql, _ in cur.calls))
                audit.assert_called_once()
                self.assertEqual(audit.call_args.args[2], 202)

    def test_owner_can_activate_only_verified_guardian(self):
        rows = [account("professional",1), client(), account(),
                {"representation_mode":"guardian","guardian_contact_id":601},
                {"id":710}, None]
        result, cursor, _ = self.execute(rows)
        self.assertTrue(result)
        identity_sql = cursor.calls[5][0]
        for required in ("c.contact_role='legal_guardian'",
                         "c.verification_status='verified'",
                         "i.verified_by=i.professional_user_id",
                         "i.contact_id=%s"):
            self.assertIn(required, identity_sql)
        self.assertEqual(cursor.calls[5][1][-1], 601)

    def test_not_verified_never_activates(self):
        rows = [account("professional",1), client(), account(),
                {"representation_mode":"guardian","guardian_contact_id":601},
                None]
        with self.assertRaises(ValueError):
            self.execute(rows)

    def test_adult_self_is_one_existing_account(self):
        rows = [account("professional",1),
                client(dob=date(1990,1,1)), account(),
                {"representation_mode":"self","guardian_contact_id":None},
                {"id":711}, None]
        result, cursor, _ = self.execute(rows)
        self.assertTrue(result)
        self.assertIn("care_portal_self_links",cursor.calls[5][0])
        self.assertTrue(any("UPDATE users SET active=1" in sql
                            for sql,_ in cursor.calls))
        self.assertFalse(any("INSERT INTO users" in sql for sql,_ in cursor.calls))

    def test_minor_has_no_self_login_and_adult_no_guardian(self):
        for born, mode, guardian in (
                (date(2012,1,1),"self",None),
                (date(1990,1,1),"guardian",601)):
            with self.subTest(mode=mode):
                rows = [account("professional",1),client(dob=born),account(),
                        {"representation_mode":mode,"guardian_contact_id":guardian}]
                with self.assertRaises(ValueError):
                    self.execute(rows)

    def test_revoke_needs_reverification_and_active_is_idempotent(self):
        for status in ("revoked","active"):
            rows = [account("professional",1),client(),account(),
                    {"representation_mode":"guardian","guardian_contact_id":601},
                    {"id":710},{"id":1000,"status":status}]
            if status == "revoked":
                with self.assertRaises(ValueError):
                    self.execute(rows)
            else:
                result, cur, audit = self.execute(rows)
                self.assertFalse(result)
                self.assertFalse(any("UPDATE users SET active=1" in sql
                                     for sql,_ in cur.calls))
                audit.assert_not_called()

    def test_suspended_login_cannot_be_reopened_by_clinician(self):
        rows = [account("professional",1), client(), account()]
        with self.assertRaises(ValueError):
            self.execute(rows, login_status="suspended")

    def test_mismatched_disabled_login_is_not_reopened(self):
        rows = [account("professional",1), client(), account()]
        with self.assertRaises(ValueError):
            self.execute(rows, login_status="active")

    def test_client_separation_even_shared_guardian_login(self):
        schema = open_activation_sql()
        self.assertIn("UNIQUE KEY uq_portal_client_activation (tenant_id,client_id,user_id)", schema)
        self.assertIn("CREATE TABLE IF NOT EXISTS care_portal_login_requests", schema)
        self.assertIn("ENUM('pending','active','suspended')", schema)
        for sql in ( __import__("saas_portal_policy").SELECT_ALLOWED,
                     __import__("saas_portal_policy").SELECT_SELF_ALLOWED):
            self.assertIn("care_portal_client_activations",sql)
            self.assertIn("a.status='active'",sql)
            self.assertIn("a.client_id=g.client_id",sql)


def open_activation_sql():
    from pathlib import Path
    return (Path(__file__).resolve().parents[1] / "scripts" /
            "mysql_care_client_activation_migration.sql").read_text(encoding="utf-8")


class ActivationRouteTests(unittest.TestCase):
    def setUp(self):
        self.prior_testing = app.config.get("TESTING")
        app.config["TESTING"] = True
        self.browser = app.test_client()
        self.role = "professional"
        self.user = store.SaaSUser(dict(
            id=11,nome="Synthetic",email="synthetic@example.invalid",
            global_role="professional",active=True,must_change_password=False))
        self.patch_user = patch.object(store, "get_user", side_effect=lambda uid: self.user)
        self.patch_user.start()
        with self.browser.session_transaction() as s:
            s["_user_id"] = "saas:11"
            s["_fresh"] = True
            s["saas_auth"] = True
            s["saas_csrf"] = "activation-test-csrf"

    def tearDown(self):
        self.patch_user.stop()
        app.config["TESTING"] = self.prior_testing

    def url(self):
        return "/saas/clientes/301/contas/104/ativar"

    def test_csrf_forbidden_and_license_required_for_professional(self):
        with patch.object(activation_routes,"activate_client_account") as act:
            self.assertEqual(self.browser.post(self.url()).status_code,400)
            act.assert_not_called()
            with patch.object(activation_routes,"licensed_tenant",
                              return_value=({"id":201},LicenseDecision(status="unlicensed"))):
                self.assertEqual(self.browser.post(self.url(),data={
                    "csrf_token":"activation-test-csrf"}).status_code,403)
                act.assert_not_called()

    def test_professional_and_admin_use_same_server_side_rule(self):
        with patch.object(activation_routes,"activate_client_account",
                          return_value=True) as act, \
             patch.object(activation_routes,"licensed_tenant",
                          return_value=({"id":201},LicenseDecision(status="exempt"))) as licensed:
            result = self.browser.post(self.url(),data={"csrf_token":"activation-test-csrf"})
            self.assertEqual(result.status_code,302)
            act.assert_called_once_with(11,301,104)
            licensed.assert_called_once()
        self.user = store.SaaSUser(dict(
            id=33,nome="Admin",email="admin@example.invalid",
            global_role="superadmin",active=True,must_change_password=False))
        with self.browser.session_transaction() as s:
            s["_user_id"] = "saas:33"
        with patch.object(activation_routes,"activate_client_account",
                          return_value=True) as act, \
             patch.object(activation_routes,"licensed_tenant") as licensed:
            result = self.browser.post(self.url(),data={"csrf_token":"activation-test-csrf"})
            self.assertEqual(result.status_code,302)
            act.assert_called_once_with(33,301,104)
            licensed.assert_not_called()


if __name__ == "__main__":
    unittest.main()
