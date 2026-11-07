"""First-access MFA, authenticator QR, and unconfigured email OTP regression."""
import base64
import os
import unittest
from unittest.mock import patch

from app import app, bcrypt
import saas_store as store
import saas_mfa as otp
import saas_mfa_store as factors
import saas_email_otp_transport as email_transport


class CryptoTests(unittest.TestCase):
    def test_rfc6238_counter_and_no_reuse(self):
        seed=base64.b32encode(b"12345678901234567890").decode().rstrip("=")
        self.assertEqual(otp.totp(seed, 1), "287082")
        self.assertEqual(otp.matching_step(seed,"287082",at=59),1)
        self.assertIsNone(otp.matching_step(seed,"287082",at=59,last_used=1))
        self.assertIsNone(otp.matching_step(seed,"287082",at=90000))
        self.assertIsNone(otp.matching_step(seed,"a87082",at=59))

    def test_secret_is_bound_to_user_and_qr_is_local(self):
        seed=otp.new_seed()
        with patch.dict(os.environ,{"SECRET_KEY":"synthetic-testing-key-at-least-32-characters"}):
            encrypted=otp.seal_seed(33,seed)
            self.assertNotIn(seed.encode(),encrypted)
            self.assertEqual(otp.open_seed(33,encrypted),seed)
            with self.assertRaises(ValueError):
                otp.open_seed(34,encrypted)
        uri=otp.provisioning_uri(seed,"test@example.invalid")
        self.assertIn("algorithm=SHA1",uri)
        self.assertIn("digits=6",uri)
        image=otp.provisioning_qr_data_uri(seed,"test@example.invalid")
        self.assertTrue(image.startswith("data:image/png;base64,"))
        self.assertTrue(base64.b64decode(image.split(",",1)[1]).startswith(b"\x89PNG"))

    def test_recovery_values_unique_and_email_transport_disabled(self):
        codes=otp.recovery_codes()
        self.assertEqual(len(set(codes)),8)
        self.assertTrue(all(len(c)==20 and otp.recovery_digest(c) for c in codes))
        with patch.dict(os.environ,{"NEURO_EMAIL_OTP_ENABLED":"false"}):
            self.assertFalse(email_transport.is_ready())
            with self.assertRaises(email_transport.EmailOtpUnavailable):
                email_transport.send_code("test@example.invalid","1234")


class FirstAccessFlowTests(unittest.TestCase):
    def setUp(self):
        self.old=app.config["TESTING"]
        app.config["TESTING"]=True
        self.client=app.test_client()
        self.user=store.SaaSUser({
            "id":37,"nome":"Teste","email":"mfa@example.invalid",
            "global_role":"professional","active":True,
            "must_change_password":False
        })
        self.get_user=patch.object(store,"get_user",return_value=self.user)
        self.get_user.start()
        with self.client.session_transaction() as s:
            s["_user_id"]="saas:37"
            s["_fresh"]=True
            s["saas_auth"]=True
            s["saas_csrf"]="mfa-flow-csrf"

    def tearDown(self):
        self.get_user.stop()
        app.config["TESTING"]=self.old

    def test_new_account_cannot_bypass_enrollment(self):
        self.user.mfa_required=True
        self.user.mfa_enabled=False
        with patch.object(factors,"enrollment_required",return_value=True):
            response=self.client.get("/saas/painel")
            self.assertEqual(response.status_code,302)
            self.assertIn("/saas/seguranca/totp",response.location)
            self.assertEqual(self.client.get("/saas/perfil").status_code,302)

    def test_setup_requires_csrf_and_offers_app_choice(self):
        seed=otp.new_seed()
        with patch.object(factors,"enrollment_required",return_value=True), \
             patch.object(factors,"enabled",return_value=False), \
             patch.object(factors,"pending_seed",return_value=seed):
            page=self.client.get("/saas/seguranca/totp")
            self.assertEqual(page.status_code,200)
            body=page.get_data(as_text=True)
            self.assertIn("Primeiro acesso: escolha seu autenticador",body)
            self.assertIn("Google Authenticator",body)
            self.assertIn("2FAS",body)
            self.assertIn("data:image/png;base64",body)
            self.assertEqual(page.headers["Cache-Control"],"private, no-store")
            self.assertEqual(self.client.post(
                "/saas/seguranca/totp",data={"action":"confirm","code":"123456"}
            ).status_code,400)

    def test_correct_password_does_not_bypass_enabled_totp(self):
        # Browser starts unauthenticated, with valid password but no trusted cookie.
        with self.client.session_transaction() as s:
            s.clear()
            s["saas_csrf"]="login-csrf"
        account={"id":37,"nome":"Teste","email":"mfa@example.invalid",
                 "global_role":"professional","active":1,
                 "must_change_password":0,"mfa_enabled":True,
                 "password_hash":bcrypt.generate_password_hash("Valid1234!").decode()}
        with patch.object(store,"user_by_email",return_value=account), \
             patch.object(factors,"enabled",return_value=True), \
             patch.object(factors,"trusted",return_value=False):
            r=self.client.post("/saas/entrar",data={
                "csrf_token":"login-csrf","email":"mfa@example.invalid",
                "senha":"Valid1234!"})
        self.assertEqual(r.status_code,302)
        self.assertIn("/saas/entrar/totp",r.location)
        with self.client.session_transaction() as s:
            self.assertNotIn("saas_auth",s)
            self.assertNotIn("_user_id",s)
            self.assertEqual(s["saas_mfa_pending"],37)

    def test_challenge_succeeds_only_after_valid_factor(self):
        with self.client.session_transaction() as s:
            s.clear()
            s["saas_mfa_pending"]=37
            s["saas_mfa_pending_at"]=__import__("time").time()
            s["saas_mfa_attempts"]=0
            s["saas_csrf"]="confirm-csrf"
        with patch.object(factors,"verify_login_factor",return_value=(False,False)):
            wrong=self.client.post("/saas/entrar/totp",data={
                "csrf_token":"confirm-csrf","code":"123456"})
            self.assertEqual(wrong.status_code,200)
            with self.client.session_transaction() as s:
                self.assertNotIn("saas_auth",s)
        with patch.object(factors,"verify_login_factor",return_value=(True,True)):
            ok=self.client.post("/saas/entrar/totp",data={
                "csrf_token":"confirm-csrf","code":"123456"})
        self.assertEqual(ok.status_code,302)
        self.assertIn("/saas/painel",ok.location)
        with self.client.session_transaction() as s:
            self.assertTrue(s["saas_auth"])

    def test_before_first_login_account_provision_marks_mfa_required(self):
        from pathlib import Path
        root=Path(__file__).resolve().parents[1]
        for path in ("saas_account_provision.py","saas_store.py"):
            self.assertIn(
                "INSERT INTO saas_mfa_factors(user_id,required) VALUES(%s,1)",
                (root / path).read_text(encoding="utf-8"))


if __name__=="__main__":
    unittest.main()
