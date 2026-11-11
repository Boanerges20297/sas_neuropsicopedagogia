"""Synthetic session-binding pentest: no real accounts or cookies."""
import os
import time
import unittest
from unittest.mock import patch

from app import app
import saas_store as store
import saas_mfa_store as factors


class SessionBindingTests(unittest.TestCase):
    def setUp(self):
        self.prior = app.config["TESTING"]
        app.config["TESTING"] = True
        self.user_id = 77601
        self.old_user = self.user("bcrypt-synthetic-hash-v1")
        self.new_user = self.user("bcrypt-synthetic-hash-v2")

    def tearDown(self):
        app.config["TESTING"] = self.prior

    def user(self, credential):
        return store.SaaSUser({
            "id": self.user_id,
            "nome": "Conta Sintética",
            "email": "synthetic@example.invalid",
            "global_role": "professional",
            "active": 1,
            "password_hash": credential,
            "must_change_password": 0,
            "mfa_required": True,
            "mfa_enabled": True,
        })

    def signed_session(self, stamp, user=None):
        client = app.test_client()
        with client.session_transaction() as sess:
            sess["_user_id"] = "saas:" + str((user or self.old_user).id)
            sess["_fresh"] = True
            sess["saas_auth"] = True
            sess["saas_auth_proof"] = stamp
            sess["saas_mfa_passed"] = True
        return client

    def test_session_proof_is_bound_to_id_and_password_hash(self):
        self.assertIsNotNone(self.old_user.auth_stamp)
        self.assertNotEqual(self.old_user.auth_stamp, self.new_user.auth_stamp)
        self.assertNotEqual(
            self.old_user.auth_stamp,
            store.session_auth_proof(self.user_id + 1, "bcrypt-synthetic-hash-v1"))
        self.assertNotIn("bcrypt-synthetic", self.old_user.auth_stamp)

    def test_valid_session_survives_but_old_credential_cookie_is_invalidated(self):
        with patch.object(store, "get_user", return_value=self.old_user):
            ok = self.signed_session(self.old_user.auth_stamp).get(
                "/saas/recuperar-senha")
        self.assertEqual(ok.status_code, 302)
        self.assertIn("/saas/perfil", ok.location)
        client = self.signed_session(self.old_user.auth_stamp)
        with patch.object(store, "get_user", return_value=self.new_user):
            denied = client.get("/saas/recuperar-senha")
        self.assertEqual(denied.status_code, 302)
        self.assertIn("/saas/entrar", denied.location)
        with client.session_transaction() as sess:
            self.assertNotIn("_user_id", sess)
            self.assertNotIn("saas_auth", sess)

    def test_other_account_proof_does_not_authorize_this_identity(self):
        forged = store.session_auth_proof(
            self.user_id + 1, "bcrypt-synthetic-hash-v1")
        client = self.signed_session(forged)
        with patch.object(store, "get_user", return_value=self.old_user):
            blocked = client.get("/saas/recuperar-senha")
        self.assertEqual(blocked.status_code, 302)
        self.assertIn("/saas/entrar", blocked.location)

    def test_mfa_challenge_started_before_password_reset_cannot_complete(self):
        client = app.test_client()
        with client.session_transaction() as sess:
            sess["saas_mfa_pending"] = self.user_id
            sess["saas_mfa_pending_proof"] = self.old_user.auth_stamp
            sess["saas_mfa_pending_at"] = time.time()
            sess["saas_mfa_attempts"] = 0
            sess["saas_csrf"] = "synthetic-csrf"
        with patch.object(store, "get_user", return_value=self.new_user), \
             patch.object(factors, "verify_login_factor", return_value=(True, True)):
            result = client.post("/saas/entrar/totp", data={
                "csrf_token": "synthetic-csrf", "code": "123456"})
        self.assertEqual(result.status_code, 403)
        with client.session_transaction() as sess:
            self.assertNotIn("_user_id", sess)
            self.assertNotIn("saas_auth", sess)
            self.assertNotIn("saas_mfa_pending", sess)


if __name__ == "__main__":
    unittest.main()
