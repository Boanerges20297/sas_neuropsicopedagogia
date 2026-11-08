"""SMTP web setup security: never expose app password and never bypass MFA."""
from contextlib import contextmanager
import os
import unittest
from unittest.mock import patch

from app import app, bcrypt
import saas_store as store
import saas_smtp_settings as settings
import saas_email_otp_transport as transport


class MockCursor:
    def __init__(self):
        self.calls=[]
    def execute(self,sql,args=()):
        self.calls.append((sql,args))


@contextmanager
def fake_tx(cur):
    yield cur


class SecretTests(unittest.TestCase):
    def test_google_app_password_validation_and_cryptography(self):
        with patch.dict(os.environ,{"SECRET_KEY":"synthetic-secret-for-smtp-unit-tests-123456789"}):
            self.assertEqual(settings._normalise_app_password("abcd efgh ijkl mnop"),"abcdefghijklmnop")
            for invalid in ("short","abc def 1234","",None):
                with self.assertRaises(ValueError):
                    settings._normalise_app_password(invalid)
            payload=settings._cipher().encrypt(b"abcdefghijklmnop")
            self.assertNotIn(b"abcdefghijklmnop",payload)
            self.assertEqual(settings._cipher().decrypt(payload),b"abcdefghijklmnop")

    def test_save_stores_only_encrypted_credentials_and_stays_disabled(self):
        cur=MockCursor()
        with patch.dict(os.environ,{"SECRET_KEY":"synthetic-secret-for-smtp-unit-tests-123456789"}), \
             patch.object(store,"transaction",side_effect=lambda:fake_tx(cur)), \
             patch.object(store,"audit") as audit:
            settings.save_password(9,"abcd efgh ijkl mnop")
        self.assertEqual(len(cur.calls),1)
        sql,args=cur.calls[0]
        self.assertIn("enabled=0",sql)
        self.assertEqual(args[0],settings.SENDER)
        self.assertNotIn(b"abcdefghijklmnop",args[1])
        self.assertEqual(args[2],9)
        audit.assert_called_once()

    def test_unconfigured_transport_fails_closed_without_database(self):
        with patch.dict(os.environ,{"NEURO_SMTP_WEB_CONFIG_ENABLED":"true"}), \
             patch.object(settings,"active_transport",side_effect=RuntimeError("synthetic")):
            self.assertFalse(transport.is_ready())
            with self.assertRaises(transport.EmailOtpUnavailable):
                transport.send_code("test@example.invalid","1234")


class SmtpAdminRouteTests(unittest.TestCase):
    def setUp(self):
        self.previous=app.config["TESTING"]
        app.config["TESTING"]=True
        self.client=app.test_client()
        self.identity=store.SaaSUser({
            "id":945, "nome":"Superadmin sintético",
            "email":"admin@example.invalid",
            "global_role":"superadmin","active":True,
            "must_change_password":False,
            "mfa_enabled":True,
        })
        self.loader=patch.object(store,"get_user",return_value=self.identity)
        self.workspace=patch("saas_routes.own_admin_workspace",return_value=None)
        self.loader.start()
        self.workspace.start()
        self.feature_flag=patch.dict(os.environ, {"NEURO_SMTP_WEB_CONFIG_ENABLED":"true"})
        self.fresh_login=patch("saas_smtp_admin_routes.login_fresh", return_value=True)
        self.feature_flag.start()
        self.fresh_login.start()
        with self.client.session_transaction() as session:
            session["_user_id"]="saas:945"
            session["_fresh"]=True
            session["saas_auth"]=True
            session["saas_mfa_passed"]=True
            session["saas_csrf"]="synthetic-csrf"

    def tearDown(self):
        self.fresh_login.stop()
        self.feature_flag.stop()
        self.workspace.stop()
        self.loader.stop()
        app.config["TESTING"]=self.previous

    def test_only_superadmin_with_mfa_can_view(self):
        with patch.object(settings,"status",return_value={
             "configured":False,"enabled":False,"verified":False,
             "sender":settings.SENDER}):
            response=self.client.get("/saas/admin/seguranca/email")
            self.assertEqual(response.status_code,200)
            body=response.get_data(as_text=True)
            self.assertIn("Configuração do e-mail",body)
            self.assertNotIn('value="abcdefghijklmnop"',body)
            self.assertIn("no-store",response.headers["Cache-Control"])
            self.identity.role="admin"
            self.assertEqual(self.client.get("/saas/admin/seguranca/email").status_code,403)
            self.identity.role="superadmin"
            self.identity.mfa_enabled=False
            enrollment=self.client.get("/saas/admin/seguranca/email")
            self.assertEqual(enrollment.status_code,302)
            self.assertIn("/saas/seguranca/totp",enrollment.location)

    def test_csrf_required_and_reauthentication(self):
        with patch.object(settings,"save_password") as save, \
             patch.object(settings,"status",return_value={
                 "configured":False,"enabled":False,"verified":False,
                 "sender":settings.SENDER}):
            response=self.client.post("/saas/admin/seguranca/email",data={
                "action":"save","app_password":"abcdefghijklmnop",
                "current_password":"synthetic"})
            self.assertEqual(response.status_code,400)
            save.assert_not_called()

    def test_app_password_accepted_only_after_password_reauth(self):
        passphrase="SafePassword1234!"
        user={"id":945,"active":True,
              "password_hash":bcrypt.generate_password_hash(passphrase).decode()}
        with patch("saas_login_recovery.cooldown_remaining",return_value=0), \
             patch.object(store,"user_by_email",return_value=user), \
             patch.object(settings,"save_password") as save:
            response=self.client.post("/saas/admin/seguranca/email",data={
                "csrf_token":"synthetic-csrf",
                "action":"save","app_password":"abcdefghijklmnop",
                "current_password":passphrase})
            self.assertEqual(response.status_code,302)
            self.assertIn("/saas/admin/seguranca/email",response.location)
            save.assert_called_once_with(945,"abcdefghijklmnop")


if __name__=="__main__":
    unittest.main()
