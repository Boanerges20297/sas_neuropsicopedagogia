"""Security regression: trusted devices vs temporary TOTP sessions."""
import time
import unittest
from unittest.mock import patch

from app import app, bcrypt
import saas_store as store
import saas_mfa_store as mfa


class TrustedDeviceLoginTests(unittest.TestCase):
    def setUp(self):
        self.previous = app.config["TESTING"]
        app.config["TESTING"] = True
        self.client = app.test_client()
        self.account = dict(
            id=764, nome="Admin Synthetic", email="admin-mfa@example.invalid",
            global_role="superadmin", active=True, must_change_password=False,
            mfa_enabled=True, mfa_required=True,
            password_hash=bcrypt.generate_password_hash("ValidTemporary123!").decode(),
        )
        self.user = store.SaaSUser(self.account)
        self.patches = [
            patch.object(store,"user_by_email",return_value=self.account),
            patch.object(store,"get_user",return_value=self.user),
            # MFA tests have no database-backed clinical workspace.
            patch("saas_routes.own_admin_workspace",return_value=None),
            patch("saas_login_recovery.cooldown_remaining",return_value=0),
            patch("saas_login_recovery.clear_failures",return_value=None),
        ]
        for p in self.patches: p.start()
        with self.client.session_transaction() as sess:
            sess["saas_csrf"] = "trusted-test-csrf"

    def tearDown(self):
        for p in reversed(self.patches): p.stop()
        app.config["TESTING"] = self.previous

    def login(self):
        return self.client.post("/saas/entrar", data={
            "csrf_token":"trusted-test-csrf",
            "email":"admin-mfa@example.invalid",
            "senha":"ValidTemporary123!",
        })

    def test_unrecognized_admin_device_requires_second_factor(self):
        with patch.object(mfa,"trusted",return_value=False):
            result = self.login()
        self.assertEqual(result.status_code,302)
        self.assertIn("/saas/entrar/totp",result.location)
        with self.client.session_transaction() as sess:
            self.assertNotIn("saas_auth",sess)
            self.assertNotIn("_user_id",sess)
            self.assertEqual(sess["saas_mfa_pending"],764)

    def test_trusted_admin_device_allows_password_login(self):
        with patch.object(mfa,"trusted",return_value=True) as trusted:
            result = self.login()
        self.assertEqual(result.status_code,302)
        self.assertIn("/saas/painel",result.location)
        trusted.assert_called_once()
        with self.client.session_transaction() as sess:
            self.assertTrue(sess["saas_auth"])
            self.assertTrue(sess["saas_mfa_passed"])
            self.assertNotIn("saas_temporary",sess)

    def test_password_only_old_admin_without_totp_must_enroll(self):
        self.account["mfa_enabled"] = False
        self.user.mfa_enabled = False
        with patch.object(mfa,"trusted") as trusted:
            result = self.login()
            self.assertEqual(result.status_code,302)
            self.assertIn("/saas/painel",result.location)
            protected = self.client.get("/saas/admin/testes")
        trusted.assert_not_called()
        self.assertEqual(protected.status_code,302)
        self.assertIn("/saas/seguranca/totp",protected.location)

    def test_temporary_device_gets_no_trust_token(self):
        with self.client.session_transaction() as sess:
            sess.clear()
            sess["saas_mfa_pending"] = 764
            sess["saas_mfa_is_admin"] = True
            sess["saas_mfa_pending_at"] = time.time()
            sess["saas_mfa_attempts"] = 0
            sess["saas_csrf"] = "totp-confirm-csrf"
        with patch.object(mfa,"verify_login_factor",return_value=(True,True)), \
             patch.object(mfa,"trust_device") as registered:
            result = self.client.post("/saas/entrar/totp", data={
                "csrf_token":"totp-confirm-csrf","code":"123456"})
        self.assertEqual(result.status_code,302)
        registered.assert_not_called()
        self.assertNotIn("neuro_mfa_device=",result.headers.get("Set-Cookie",""))
        with self.client.session_transaction() as sess:
            self.assertTrue(sess["saas_temporary"])
            self.assertTrue(sess["saas_mfa_passed"])

    def test_opt_in_registers_trusted_device_only_after_totp(self):
        with self.client.session_transaction() as sess:
            sess.clear()
            sess["saas_mfa_pending"] = 764
            sess["saas_mfa_is_admin"] = True
            sess["saas_mfa_pending_at"] = time.time()
            sess["saas_mfa_attempts"] = 0
            sess["saas_csrf"] = "totp-confirm-csrf"
        with patch.object(mfa,"verify_login_factor",return_value=(True,True)), \
             patch.object(mfa,"trust_device",return_value="synthetic-token") as register:
            result = self.client.post("/saas/entrar/totp",data={
                "csrf_token":"totp-confirm-csrf","code":"123456","trust_device":"on"})
        self.assertEqual(result.status_code,302)
        register.assert_called_once()
        self.assertIn("neuro_mfa_device=synthetic-token",result.headers.get("Set-Cookie",""))
        with self.client.session_transaction() as sess:
            self.assertTrue(sess["saas_mfa_passed"])
            self.assertNotIn("saas_temporary",sess)

    def test_expired_temporary_device_session_is_revoked(self):
        with self.client.session_transaction() as sess:
            sess["_user_id"] = "saas:764"
            sess["_fresh"] = True
            sess["saas_auth"] = True
            sess["saas_mfa_passed"] = True
            sess["saas_temporary"] = True
            sess["saas_last_seen"] = time.time() - 16 * 60
        result = self.client.get("/saas/painel")
        self.assertEqual(result.status_code,302)
        self.assertIn("/saas/entrar",result.location)
        with self.client.session_transaction() as sess:
            self.assertNotIn("saas_auth",sess)

    def _first_enrollment(self, trust):
        self.user.mfa_enabled = False
        with self.client.session_transaction() as sess:
            sess.clear()
            sess["_user_id"] = "saas:764"
            sess["_fresh"] = True
            sess["saas_auth"] = True
            sess["saas_csrf"] = "first-enrollment-csrf"
        with patch.object(mfa,"finish_enrollment",return_value=["recovery-placeholder"]), \
             patch.object(mfa,"trust_device",return_value="first-setup-token") as trusted, \
             patch.object(mfa,"enabled",return_value=True), \
             patch.object(mfa,"pending_seed",return_value=None), \
             patch.object(mfa,"enrollment_required",return_value=False):
            result = self.client.post("/saas/seguranca/totp",data={
                "csrf_token":"first-enrollment-csrf","action":"confirm",
                "code":"123456","trust_device":"on" if trust else ""})
        return result,trusted

    def test_first_enrollment_can_trust_its_device(self):
        result,registered = self._first_enrollment(True)
        self.assertEqual(result.status_code,200)
        registered.assert_called_once()
        self.assertIn("neuro_mfa_device=first-setup-token",
                      result.headers.get("Set-Cookie",""))
        with self.client.session_transaction() as sess:
            self.assertTrue(sess["saas_mfa_passed"])
            self.assertNotIn("saas_temporary",sess)

    def test_first_enrollment_without_optin_is_temporary(self):
        result,registered = self._first_enrollment(False)
        self.assertEqual(result.status_code,200)
        registered.assert_not_called()
        self.assertNotIn("neuro_mfa_device=",result.headers.get("Set-Cookie",""))
        with self.client.session_transaction() as sess:
            self.assertTrue(sess["saas_mfa_passed"])
            self.assertTrue(sess["saas_temporary"])

    def test_manual_totp_key_offered_only_during_enrollment(self):
        from saas_mfa import new_seed
        seed = new_seed()
        with self.client.session_transaction() as sess:
            sess["_user_id"] = "saas:764"
            sess["_fresh"] = True
            sess["saas_auth"] = True
            sess["saas_csrf"] = "manual-totp-csrf"
        self.user.mfa_enabled = False
        with patch.object(mfa,"enabled",return_value=False), \
             patch.object(mfa,"enrollment_required",return_value=True), \
             patch.object(mfa,"pending_seed",return_value=seed):
            page = self.client.get("/saas/seguranca/totp")
        self.assertEqual(page.status_code,200)
        html = page.get_data(as_text=True)
        self.assertIn(seed,html)
        self.assertIn("totp-manual-key",html)
        self.assertIn("Copiar chave",html)
        self.assertIn("SHA-1",html)
        self.user.mfa_enabled = True
        with self.client.session_transaction() as sess:
            sess["saas_mfa_passed"] = True
        with patch.object(mfa,"enabled",return_value=True), \
             patch.object(mfa,"enrollment_required",return_value=False), \
             patch.object(mfa,"pending_seed",return_value=None):
            active = self.client.get("/saas/seguranca/totp")
        self.assertEqual(active.status_code,200)
        self.assertNotIn(seed,active.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
