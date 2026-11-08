"""Email ownership verification regression tests (synthetic only)."""
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from app import app, bcrypt
import saas_store as store
import saas_email_verification as verify


class EmailCodeUnitTests(unittest.TestCase):
    def test_digest_binds_owner_address_purpose_and_nonce(self):
        with patch.dict(os.environ,{"SECRET_KEY":"synthetic-secret-key-at-least-forty-eight-characters"}):
            nonce=b"x"*16
            good=verify._digest(7,"one@example.invalid","registration",nonce,"001234")
            self.assertEqual(len(good),32)
            self.assertEqual(good,verify._digest(7,"one@example.invalid",
                                                  "registration",nonce,"001234"))
            self.assertNotEqual(good,verify._digest(8,"one@example.invalid",
                                                     "registration",nonce,"001234"))
            self.assertNotEqual(good,verify._digest(7,"two@example.invalid",
                                                     "registration",nonce,"001234"))
            self.assertNotEqual(good,verify._digest(7,"one@example.invalid",
                                                     "change",nonce,"001234"))
            self.assertNotEqual(good,verify._digest(7,"one@example.invalid",
                                                     "registration",b"y"*16,"001234"))

    def test_rejects_invalid_code_before_database_lookup(self):
        with patch.object(store,"transaction") as tx:
            self.assertFalse(verify.confirm_code("test@example.invalid","1234"))
            self.assertFalse(verify.confirm_code("test@example.invalid","1234567"))
            self.assertFalse(verify.confirm_code("test@example.invalid","ab1234"))
            tx.assert_not_called()

    def test_bootstrap_requires_no_activity_or_mfa(self):
        base=dict(global_role="admin",active=1,bootstrapped=1,acted=0,
                  mfa_enabled=0,has_clients=0,has_assessments=0,
                  has_encounters=0,has_intakes=0)
        self.assertTrue(verify._bootstrap_allowed(base))
        for key in ("acted","mfa_enabled","has_clients",
                    "has_assessments","has_encounters","has_intakes"):
            with self.subTest(key=key):
                self.assertFalse(verify._bootstrap_allowed({**base,key:1}))
        for role in ("professional","patient","superadmin"):
            with self.subTest(role=role):
                self.assertFalse(verify._bootstrap_allowed({**base,"global_role":role}))
        self.assertFalse(verify._bootstrap_allowed({**base,"active":0}))
        self.assertFalse(verify._bootstrap_allowed({**base,"bootstrapped":0}))

    def test_schema_is_additive_without_marking_legacy_verified(self):
        sql=(Path(__file__).resolve().parents[1]/
             "scripts/mysql_saas_email_verification_migration.sql").read_text()
        self.assertIn("CREATE TABLE IF NOT EXISTS saas_email_verifications",sql)
        self.assertIn("CREATE TABLE IF NOT EXISTS saas_email_challenges",sql)
        self.assertNotIn("UPDATE users",sql)
        self.assertNotIn("UPDATE saas_email_verifications SET verified_at",sql)
        self.assertIn("nonce BINARY(16)",sql)
        self.assertIn("digest BINARY(32)",sql)


class EmailRouteUnitTests(unittest.TestCase):
    def setUp(self):
        self.old=app.config["TESTING"]
        app.config["TESTING"]=True
        self.client=app.test_client()
        with self.client.session_transaction() as session:
            session["saas_csrf"]="email-synthetic-csrf"

    def tearDown(self):
        app.config["TESTING"]=self.old

    def test_registration_sends_email_code_then_waits_for_proof(self):
        password="Ab1234!xy"
        with patch.object(store,"register_professional",return_value=100) as register, \
             patch.object(verify,"request_registration_code",return_value=True) as sender:
            response=self.client.post("/saas/cadastro",data=dict(
                csrf_token="email-synthetic-csrf",nome="Teste Sintetico",
                email="verify@example.invalid",profession="psicologia",
                cpf="123.456.789-09",birth_date="1992-04-11",
                phone="85999999999",senha=password,confirmar_senha=password))
        self.assertEqual(response.status_code,302)
        self.assertEqual(response.location,"/saas/verificar-email")
        register.assert_called_once()
        sender.assert_called_once_with("verify@example.invalid")
        with self.client.session_transaction() as session:
            self.assertEqual(session["saas_verify_email"],"verify@example.invalid")

    def test_correct_password_does_not_bypass_email_verification(self):
        password="Ab1234!xy"
        account=dict(id=50,nome="Fake User",email="verify@example.invalid",
                     password_hash=bcrypt.generate_password_hash(password).decode(),
                     global_role="professional",active=1,
                     must_change_password=0,email_verification_pending=1)
        with patch.object(store,"user_by_email",return_value=account), \
             patch("saas_login_recovery.cooldown_remaining",return_value=0), \
             patch("saas_login_recovery.clear_failures"):
            response=self.client.post("/saas/entrar",data={
                "csrf_token":"email-synthetic-csrf",
                "email":"verify@example.invalid","senha":password})
        self.assertEqual(response.status_code,302)
        self.assertEqual(response.location,"/saas/verificar-email")
        with self.client.session_transaction() as session:
            self.assertNotIn("_user_id",session)

    def test_public_confirmation_form_does_not_leak_code(self):
        with patch.object(verify,"confirm_code",return_value=False) as checker:
            response=self.client.post("/saas/verificar-email",data={
                "csrf_token":"email-synthetic-csrf",
                "email":"test@example.invalid","code":"123456"})
        self.assertEqual(response.status_code,200)
        checker.assert_called_once_with("test@example.invalid","123456",
                                        authenticated_user_id=None)
        self.assertIn("Confirmar e-mail",response.get_data(as_text=True))

    def test_repeated_verification_replies_without_enumerating_accounts(self):
        with patch.object(verify,"request_registration_code",return_value=False):
            result=self.client.post("/saas/verificar-email/reenviar",
              data={"csrf_token":"email-synthetic-csrf",
                    "email":"missing@example.invalid"})
        self.assertEqual(result.status_code,302)
        self.assertEqual(result.location,"/saas/verificar-email")


class ConfirmationTransactionTests(unittest.TestCase):
    def test_registration_confirmation_consumes_code_once(self):
        from contextlib import contextmanager
        from datetime import datetime,timedelta,timezone

        class Cursor:
            def __init__(self,code):
                self.challenge={
                    "user_id":50,"purpose":"registration","nonce":b"x"*16,
                    "digest":verify._digest(50,"owner@example.invalid",
                                            "registration",b"x"*16,code),
                    "expires_at":datetime.now(timezone.utc).replace(
                        tzinfo=None)+timedelta(minutes=9),
                    "attempts_left":5,"requested_by":None,
                    "old_email":"owner@example.invalid",
                    "global_role":"professional","active":0}
                self.operations=[]
                self.row=None
            def execute(self,sql,args=()):
                self.operations.append((sql,args))
                if "FROM saas_email_challenges c" in sql:
                    self.row=self.challenge.copy() if self.challenge else None
                else:
                    self.row=None
                if "attempts_left=attempts_left-1" in sql:
                    self.challenge["attempts_left"]-=1
                if "DELETE FROM saas_email_challenges" in sql:
                    self.challenge=None
            def fetchone(self):
                return self.row

        @contextmanager
        def tx(cursor):
            yield cursor

        with patch.dict(os.environ,{"SECRET_KEY":
                                     "synthetic-secret-key-at-least-forty-eight-characters"}):
            cursor=Cursor("024681")
            with (patch.object(store,"transaction",side_effect=lambda:tx(cursor)),
                  patch.object(store,"audit") as audit):
                self.assertFalse(verify.confirm_code("owner@example.invalid","024680"))
                self.assertEqual(cursor.challenge["attempts_left"],4)
                self.assertEqual(verify.confirm_code(
                    "owner@example.invalid","024681"),"registration")
                self.assertFalse(verify.confirm_code("owner@example.invalid","024681"))
                self.assertTrue(any("UPDATE saas_email_verifications" in sql
                                    for sql,_ in cursor.operations))
                audit.assert_called_once()

    def test_new_address_confirmation_requires_same_logged_in_owner(self):
        from contextlib import contextmanager
        from datetime import datetime,timedelta,timezone
        class Cursor:
            def __init__(self):
                self.row=None
                self.operations=[]
            def execute(self,sql,args=()):
                self.operations.append(sql)
                self.row=(dict(
                    user_id=50,purpose="change",nonce=b"n"*16,
                    digest=verify._digest(50,"new@example.invalid","change",
                                          b"n"*16,"567890"),
                    expires_at=datetime.now(timezone.utc).replace(
                        tzinfo=None)+timedelta(minutes=8),
                    attempts_left=5,requested_by=50,
                    old_email="old@example.invalid",
                    global_role="professional",active=1)
                    if "FROM saas_email_challenges c" in sql else None)
            def fetchone(self):
                return self.row
        @contextmanager
        def tx(cursor):
            yield cursor
        with patch.dict(os.environ,{"SECRET_KEY":
                                     "synthetic-secret-key-at-least-forty-eight-characters"}):
            cursor=Cursor()
            with (patch.object(store,"transaction",side_effect=lambda:tx(cursor)),
                  patch.object(store,"audit")):
                self.assertFalse(verify.confirm_code(
                    "new@example.invalid","567890",authenticated_user_id=99))
                self.assertFalse(any("UPDATE users SET email" in sql
                                     for sql in cursor.operations))
                self.assertEqual(verify.confirm_code(
                    "new@example.invalid","567890",
                    authenticated_user_id=50),"change")
                self.assertTrue(any("UPDATE users SET email" in sql
                                    for sql in cursor.operations))


    def test_bootstrap_confirmation_revokes_legacy_password(self):
        from contextlib import contextmanager
        from datetime import datetime,timedelta,timezone
        email="newadmin@example.invalid"
        code="102938"
        eligibility=dict(global_role="admin",active=1,bootstrapped=1,acted=0,
                         mfa_enabled=0,has_clients=0,has_assessments=0,
                         has_encounters=0,has_intakes=0)
        class Cursor:
            def __init__(self):
                self.row=None
                self.updates=[]
            def execute(self,sql,args=()):
                if "FROM saas_email_challenges c" in sql:
                    self.row=dict(user_id=50,purpose="bootstrap_admin",
                        nonce=b"q"*16,
                        digest=verify._digest(50,email,"bootstrap_admin",
                                              b"q"*16,code),
                        expires_at=datetime.now(timezone.utc).replace(
                            tzinfo=None)+timedelta(minutes=5),
                        attempts_left=5,requested_by=9,old_email="unknown@example.invalid",
                        global_role="admin",active=1)
                elif "SELECT active,global_role FROM users" in sql:
                    self.row=dict(active=1,global_role="superadmin")
                else:
                    self.row=None
                if "UPDATE users SET email" in sql:
                    self.updates.append((sql,args))
            def fetchone(self):
                return self.row
        @contextmanager
        def tx(cursor):
            yield cursor
        from app import bcrypt
        with patch.dict(os.environ,{"SECRET_KEY":
                                     "synthetic-secret-key-at-least-forty-eight-characters"}):
            cursor=Cursor()
            with (patch.object(store,"transaction",side_effect=lambda:tx(cursor)),
                  patch.object(store,"audit"),
                  patch.object(verify,"_bootstrap_record",return_value=eligibility)):
                self.assertEqual(verify.confirm_code(email,code),"bootstrap_admin")
                self.assertEqual(len(cursor.updates),1)
                sql,args=cursor.updates[0]
                self.assertIn("password_hash",sql)
                self.assertIn("must_change_password=1",sql)
                self.assertEqual(args[0],email)
                self.assertEqual(args[2],50)
                self.assertFalse(bcrypt.check_password_hash(
                    args[1],"LegacyPassword1234!"))


if __name__=="__main__":
    unittest.main()
