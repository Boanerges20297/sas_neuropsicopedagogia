"""Synthetic tests: shared login failure counter and email recovery fail-closed."""
from contextlib import contextmanager
from datetime import datetime, timezone
import os
import unittest
from unittest.mock import patch

from app import app
import saas_login_recovery as recovery
import saas_email_otp_transport as transport
import saas_store as store


class CounterCursor:
    def __init__(self):
        self.record = None
        self.row = None
    def execute(self, sql, args=()):
        if "SELECT failures,started_at,cooldown_until" in sql:
            self.row = self.record
        elif "INSERT INTO saas_login_attempt_limits" in sql:
            self.record = {
                "failures": args[1], "started_at": args[2],
                "cooldown_until": args[3]}
        else:
            raise AssertionError("Unexpected SQL")
    def fetchone(self):
        return self.row


@contextmanager
def tx(cursor):
    yield cursor


class RecoverySecurityTests(unittest.TestCase):
    def test_five_failed_passwords_are_shared_and_temporary(self):
        cursor=CounterCursor()
        with patch.dict(os.environ, {"SECRET_KEY":"synthetic-unit-test-secret-12345678901234567890"}), \
             patch.object(store, "transaction", side_effect=lambda: tx(cursor)):
            for i in range(1,5):
                self.assertFalse(recovery.note_wrong_password("USER@example.invalid"))
                self.assertEqual(cursor.record["failures"], i)
            self.assertTrue(recovery.note_wrong_password("user@example.invalid"))
            self.assertEqual(cursor.record["failures"],5)
            self.assertGreater(cursor.record["cooldown_until"],datetime.now(timezone.utc).replace(tzinfo=None))
            self.assertTrue(recovery.note_wrong_password("user@example.invalid"))
            self.assertEqual(cursor.record["failures"],5)

    def test_four_digit_codes_cannot_be_recovered_from_database_digest(self):
        with patch.dict(os.environ, {"SECRET_KEY":"synthetic-unit-test-secret-12345678901234567890"}):
            for _ in range(100):
                code=recovery.random_code()
                self.assertEqual(len(code),4)
                self.assertTrue(code.isascii() and code.isdigit())
                digest=recovery._digest(7,b"0123456789abcdef",code)
                self.assertEqual(len(digest),32)
                self.assertNotEqual(digest,recovery._digest(8,b"0123456789abcdef",code))
                self.assertNotEqual(digest,recovery._digest(7,b"0123456789abcdeg",code))

    def test_email_otp_is_disabled_without_owner_configuration(self):
        with patch.dict(os.environ, {"NEURO_EMAIL_OTP_ENABLED":"false"}):
            with patch.object(store,"transaction") as txn:
                self.assertFalse(recovery.request_reset("test@example.invalid"))
                self.assertFalse(recovery.reset_with_code(
                    "test@example.invalid","1234","synthetic-hash-here-123456789"))
                txn.assert_not_called()
            self.assertFalse(transport.is_ready())

    def test_reset_pages_refuse_to_send_until_smtp_ready(self):
        previous=app.config["TESTING"]
        app.config["TESTING"]=True
        try:
            browser=app.test_client()
            with patch.object(transport,"is_ready",return_value=False):
                page=browser.get("/saas/recuperar-senha")
                self.assertEqual(page.status_code,200)
                self.assertIn("ainda não habilitado",page.get_data(as_text=True))
                with browser.session_transaction() as sess:
                    token=sess["saas_csrf"]
                response=browser.post("/saas/recuperar-senha",
                                      data={"csrf_token":token,"email":"test@example.invalid"})
                self.assertEqual(response.status_code,200)
                self.assertEqual(browser.post(
                    "/saas/recuperar-senha",
                    data={"email":"test@example.invalid"}).status_code,400)
                self.assertEqual(browser.post(
                    "/saas/recuperar-senha/confirmar",
                    data={"csrf_token":token,"email":"test@example.invalid",
                          "code":"1234","senha":"Ab1234!x",
                          "confirmar_senha":"Ab1234!x"}).status_code,503)
        finally:
            app.config["TESTING"]=previous

    def test_fifth_login_failure_redirects_to_explicit_recovery(self):
        previous=app.config["TESTING"]
        app.config["TESTING"]=True
        try:
            browser=app.test_client()
            with browser.session_transaction() as sess:
                sess["saas_csrf"]="csrf-test"
            with patch.object(store,"user_by_email",return_value=None), \
                 patch.object(recovery,"cooldown_remaining",return_value=0), \
                 patch.object(recovery,"note_wrong_password",return_value=True) as note:
                response=browser.post("/saas/entrar",data={
                    "csrf_token":"csrf-test","email":"unknown@example.invalid",
                    "senha":"wrong"})
            self.assertEqual(response.status_code,302)
            self.assertIn("/saas/recuperar-senha",response.location)
            note.assert_called_once_with("unknown@example.invalid")
        finally:
            app.config["TESTING"]=previous


if __name__=="__main__":
    unittest.main()
