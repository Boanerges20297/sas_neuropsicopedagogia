"""Synthetic-only SaaS account and professional validation regression tests."""
import os
import unittest
from unittest.mock import patch

from app import app, bcrypt
import saas_store as store
from saas_profile_data import validate_cpf, validate_area, validate_birth_date, validate_phone, prepare_cpf, masked_cpf


class ProfessionalDetailsTests(unittest.TestCase):
    def test_cpf_validation_and_encryption(self):
        with patch.dict(os.environ, {"SECRET_KEY": "synthetic-development-only-long-unique-secret-12345"}):
            self.assertEqual(validate_cpf("123.456.789-09"), "12345678909")
            for bad in ("111.111.111-11", "12345678900", "", "01234"):
                with self.assertRaises(ValueError):
                    validate_cpf(bad)
            digest, secret = prepare_cpf("12345678909")
            self.assertEqual(len(digest), 64)
            self.assertNotIn(b"12345678909", secret)
            self.assertEqual(masked_cpf(secret), "***.***.789-09")

    def test_area_birth_date_and_phone(self):
        for area in ("psicologia", "neuropsicopedagogia", "psiquiatria", "psicopedagogia"):
            self.assertEqual(validate_area(area), area)
        with self.assertRaises(ValueError):
            validate_area("outro")
        self.assertEqual(validate_birth_date("1994-02-12").isoformat(), "1994-02-12")
        with self.assertRaises(ValueError):
            validate_birth_date("2999-01-01")
        self.assertEqual(validate_phone("(85) 98888-8888"), "85988888888")
        with self.assertRaises(ValueError):
            validate_phone("1234")


class SaaSAccountFlowTests(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()
        self.record = dict(id=9876, nome="Superadmin de teste",
                           email="synthetic-admin@example.invalid",
                           password_hash=bcrypt.generate_password_hash("TemporaryAccess123!").decode(),
                           global_role="superadmin", active=1, must_change_password=1)
        self.get_user = patch.object(store, "get_user", side_effect=lambda uid: store.SaaSUser(self.record))
        self.get_user.start()
        self.lookup = patch.object(store, "user_by_email", side_effect=lambda email: self.record if email==self.record["email"] else None)
        self.lookup.start()
        self.profile_data = patch.object(store, "get_account_profile",return_value=dict(
            id=9876,nome="Superadmin de teste",email="synthetic-admin@example.invalid",
            cpf_masked="Não informado",practice_area=None,birth_date=None,
            phone_display="",global_role="superadmin",must_change_password=1))
        self.profile_data.start()
        self.recovery_check=patch("saas_login_recovery.cooldown_remaining",return_value=0)
        self.recovery_clear=patch("saas_login_recovery.clear_failures",return_value=None)
        self.recovery_check.start()
        self.recovery_clear.start()
        with self.client.session_transaction() as s:
            s["saas_csrf"]="test-csrf-code"
    def tearDown(self):
        self.recovery_clear.stop()
        self.recovery_check.stop()
        self.profile_data.stop()
        self.lookup.stop()
        self.get_user.stop()

    def do_login(self):
        return self.client.post("/saas/entrar",data=dict(
            csrf_token="test-csrf-code",email=self.record["email"],
            senha="TemporaryAccess123!"))

    def current_csrf(self):
        with self.client.session_transaction() as sess:
            return sess["saas_csrf"]

    def test_login_requires_profile_first(self):
        logged=self.do_login()
        self.assertEqual(logged.status_code,302)
        self.assertIn("/saas/perfil",logged.location)
        denied=self.client.get("/saas/painel")
        self.assertEqual(denied.status_code,302)
        self.assertIn("/saas/perfil",denied.location)
        page=self.client.get("/saas/perfil")
        self.assertEqual(page.status_code,200)
        self.assertIn("Definir nova senha",page.get_data(as_text=True))

    def test_forced_password_change_validation(self):
        self.do_login()
        called=[]
        with patch.object(store,"change_account_password",side_effect=lambda uid,hash_value: called.append((uid,hash_value))):
            wrong=self.client.post("/saas/perfil/senha",data=dict(
                csrf_token=self.current_csrf(),senha_atual="wrong",
                nova_senha="DifferentPassword1234!",confirmar_senha="DifferentPassword1234!"))
            self.assertEqual(wrong.status_code,302)
            self.assertEqual(called,[])
            short=self.client.post("/saas/perfil/senha",data=dict(
                csrf_token=self.current_csrf(),senha_atual="TemporaryAccess123!",
                nova_senha="short",confirmar_senha="short"))
            self.assertEqual(short.status_code,302)
            self.assertEqual(called,[])
            valid=self.client.post("/saas/perfil/senha",data=dict(
                csrf_token=self.current_csrf(),senha_atual="TemporaryAccess123!",
                nova_senha="DifferentPassword1234!",confirmar_senha="DifferentPassword1234!"))
            self.assertEqual(valid.status_code,302)
            self.assertIn("/saas/painel",valid.location)
            self.assertEqual(called[0][0],9876)
            self.assertTrue(bcrypt.check_password_hash(called[0][1],"DifferentPassword1234!"))

    def test_csrf_required_and_profile_edit_blocked_during_rotation(self):
        self.do_login()
        bad=self.client.post("/saas/perfil/senha",data=dict(
            senha_atual="TemporaryAccess123!",nova_senha="DifferentPassword1234!",
            confirmar_senha="DifferentPassword1234!"))
        self.assertEqual(bad.status_code,400)
        with patch.object(store,"update_account_profile") as update:
            blocked=self.client.post("/saas/perfil",data=dict(
                csrf_token=self.current_csrf(),nome="Alterado",
                email="other@example.invalid",senha_atual="TemporaryAccess123!"))
            self.assertEqual(blocked.status_code,302)
            update.assert_not_called()


if __name__=="__main__":
    unittest.main()
