r"""Opt-in MySQL integration: two professionals must never see each other's records.

Run only against an empty/disposable STI homologation database:
    $env:NEURO_INTEGRATION_ALLOW='1'
    .\.venv\Scripts\python.exe -m unittest discover -s tests -p test_saas_isolation_mysql.py -v
Creates synthetic accounts and removes them in a finally block.
No real BTA calls and no real clinical data.
"""
import os
import secrets
import unittest
from uuid import uuid4
from unittest.mock import patch

import pymysql
from app import app, bcrypt
import saas_store as store
from bta_license_client import LicenseDecision


def valid_synthetic_cpf():
    digits = str(secrets.randbelow(900000000) + 100000000)
    for length in (9, 10):
        check = sum(int(digits[i]) * (length + 1 - i) for i in range(length)) * 10 % 11
        digits += str(0 if check == 10 else check)
    return digits


@unittest.skipUnless(os.getenv("NEURO_INTEGRATION_ALLOW") == "1",
                     "MySQL integration requires explicit opt-in")
class MySQLTenantIsolationTests(unittest.TestCase):
    def test_two_professionals_clients_tests_and_assessment_fk(self):
        tag = uuid4().hex[:16]
        admin_email = f"admin-{tag}@example.invalid"
        a_email = f"alpha-{tag}@example.invalid"
        b_email = f"beta-{tag}@example.invalid"
        emails = (admin_email, a_email, b_email)
        test_ids = []
        app.config["TESTING"] = True
        try:
            with store.transaction() as cur:
                cur.execute(
                    "INSERT INTO users (nome,email,password_hash,global_role,active) "
                    "VALUES (%s,%s,%s,'admin',1)",
                    ("Admin sintético", admin_email,
                     bcrypt.generate_password_hash("SyntheticOnly123!").decode()),
                )
                admin_id = cur.lastrowid
            a = store.register_professional(
                "Profissional Alpha", a_email,
                bcrypt.generate_password_hash("SyntheticOnly123!").decode(),
                "psicologia", "", valid_synthetic_cpf(), "1992-05-01", "85999998888",
            )
            b = store.register_professional(
                "Profissional Beta", b_email,
                bcrypt.generate_password_hash("SyntheticOnly123!").decode(),
                "neuropsicopedagogia", "", valid_synthetic_cpf(), "1990-06-02", "85999997777",
            )
            self.assertIsNone(store.get_user(a))
            self.assertIsNone(store.own_tenant(a))
            self.assertIsNone(store.get_user(b))
            store.approve_professional(admin_id, a, "Aprovação sintética Alpha", True)
            store.approve_professional(admin_id, b, "Aprovação sintética Beta", True)
            ta = store.own_tenant(a)["id"]
            tb = store.own_tenant(b)["id"]
            self.assertNotEqual(ta, tb)

            alpha_name = "Cliente Alpha PRIVADO " + tag
            beta_name = "Cliente Beta PRIVADO " + tag
            ca = store.create_client(a, ta, alpha_name, a_email)
            cb = store.create_client(b, tb, beta_name, b_email)
            self.assertEqual([x["id"] for x in store.list_clients(a, ta)], [ca])
            self.assertEqual([x["id"] for x in store.list_clients(b, tb)], [cb])
            self.assertFalse(store.list_clients(a, tb))
            self.assertFalse(store.list_clients(b, ta))
            with self.assertRaises(PermissionError):
                store.create_client(a, tb, "Intruso")
            with self.assertRaises(PermissionError):
                store.create_client(b, ta, "Intruso")

            with store.transaction() as cur:
                for tenant_id, visibility, owner, title in (
                    (None, "global", admin_id, "GLOBAL_" + tag),
                    (ta, "private", a, "PRIV_ALPHA_" + tag),
                    (tb, "private", b, "PRIV_BETA_" + tag),
                ):
                    cur.execute(
                        "INSERT INTO tests(tenant_id,title,created_by,visibility,status) "
                        "VALUES(%s,%s,%s,%s,'approved')",
                        (tenant_id, title, owner, visibility),
                    )
                    test_ids.append(cur.lastrowid)
                cur.execute(
                    "INSERT INTO test_versions(test_id,version_number,definition_json,"
                    "status,created_by) VALUES(%s,1,'{}','approved',%s)",
                    (test_ids[0], admin_id),
                )
                version_id = cur.lastrowid

            titles_a = {x["title"] for x in store.list_visible_tests(a, ta)}
            titles_b = {x["title"] for x in store.list_visible_tests(b, tb)}
            self.assertEqual(titles_a, {"GLOBAL_" + tag, "PRIV_ALPHA_" + tag})
            self.assertEqual(titles_b, {"GLOBAL_" + tag, "PRIV_BETA_" + tag})
            self.assertFalse(store.list_visible_tests(a, tb))
            self.assertFalse(store.list_visible_tests(b, ta))

            with self.assertRaises(pymysql.err.IntegrityError):
                with store.transaction() as cur:
                    cur.execute(
                        "INSERT INTO assessments(tenant_id,client_id,test_version_id,"
                        "responsible_user_id) VALUES (%s,%s,%s,%s)",
                        (tb, ca, version_id, b),
                    )
            with patch("saas_routes.resolve_tenant_license",
                       return_value=LicenseDecision(status="licensed", state="active")):
                for pid, own_name, foreign_name, own_test, foreign_test in (
                    (a, alpha_name, beta_name, "PRIV_ALPHA_" + tag, "PRIV_BETA_" + tag),
                    (b, beta_name, alpha_name, "PRIV_BETA_" + tag, "PRIV_ALPHA_" + tag),
                ):
                    with app.test_client() as client:
                        with client.session_transaction() as session:
                            session["_user_id"] = f"saas:{pid}"
                            session["_fresh"] = True
                            session["saas_auth"] = True
                        page = client.get("/saas/pacientes")
                        self.assertEqual(page.status_code, 200)
                        html = page.get_data(as_text=True)
                        self.assertIn(own_name, html)
                        self.assertNotIn(foreign_name, html)
                        tests = client.get("/saas/testes")
                        self.assertEqual(tests.status_code, 200)
                        self.assertIn(own_test, tests.get_data(as_text=True))
                        self.assertNotIn(foreign_test, tests.get_data(as_text=True))
        finally:
            # Only synthetic identities generated by this test are targeted.
            with store.transaction() as cur:
                cur.execute(
                    "SELECT id FROM users WHERE email IN (%s,%s,%s)", emails
                )
                user_ids = [row["id"] for row in cur.fetchall()]
                if user_ids:
                    placeholders = ",".join(["%s"] * len(user_ids))
                    cur.execute(
                        f"SELECT id FROM tenants WHERE owner_user_id IN ({placeholders})",
                        tuple(user_ids),
                    )
                    tenants = [row["id"] for row in cur.fetchall()]
                    if test_ids:
                        marks = ",".join(["%s"] * len(test_ids))
                        cur.execute(f"DELETE FROM test_versions WHERE test_id IN ({marks})",
                                    tuple(test_ids))
                        cur.execute(f"DELETE FROM tests WHERE id IN ({marks})",
                                    tuple(test_ids))
                    if tenants:
                        marks = ",".join(["%s"] * len(tenants))
                        params = tuple(tenants)
                        cur.execute(f"DELETE FROM assessment_invitations WHERE tenant_id IN ({marks})", params)
                        cur.execute(f"DELETE FROM assessment_responses WHERE tenant_id IN ({marks})", params)
                        cur.execute(f"DELETE FROM assessments WHERE tenant_id IN ({marks})", params)
                        cur.execute(f"DELETE FROM clients WHERE tenant_id IN ({marks})", params)
                        cur.execute(f"DELETE FROM review_requests WHERE tenant_id IN ({marks})", params)
                        cur.execute(f"DELETE FROM audit_events WHERE tenant_id IN ({marks})", params)
                        cur.execute(f"DELETE FROM tenant_members WHERE tenant_id IN ({marks})", params)
                    cur.execute(f"DELETE FROM audit_events WHERE actor_id IN ({placeholders})",
                                tuple(user_ids))
                    cur.execute(f"DELETE FROM professional_details WHERE user_id IN ({placeholders})",
                                tuple(user_ids))
                    cur.execute(f"DELETE FROM professional_profiles WHERE user_id IN ({placeholders})",
                                tuple(user_ids))
                    if tenants:
                        marks = ",".join(["%s"] * len(tenants))
                        cur.execute(f"DELETE FROM tenants WHERE id IN ({marks})", tuple(tenants))
                    cur.execute(f"DELETE FROM users WHERE id IN ({placeholders})",
                                tuple(user_ids))
            remaining = store.one(
                "SELECT COUNT(*) n FROM users WHERE email IN (%s,%s,%s)", emails
            )["n"]
            self.assertEqual(remaining, 0)


if __name__ == "__main__":
    unittest.main()
