"""Regression: distinct recovery-code entry, root navigation and SMTP guidance."""
import unittest
from unittest.mock import patch

import app as app_module
from app import app
import saas_store as store
import saas_email_otp_transport as transport
import saas_login_recovery as recovery


class RecoveryEntryTests(unittest.TestCase):
    def setUp(self):
        self.previous_testing=app.config["TESTING"]
        app.config["TESTING"]=True
        self.browser=app.test_client()

    def tearDown(self):
        app.config["TESTING"]=self.previous_testing

    def test_login_has_two_distinct_paths(self):
        html=self.browser.get("/saas/entrar").get_data(as_text=True)
        self.assertIn('href="/saas/recuperar-senha"',html)
        self.assertIn('href="/saas/recuperar-senha/confirmar"',html)
        self.assertIn("Informar código e definir nova senha",html)

    def test_received_code_page_does_not_request_another_otp(self):
        with (patch.object(transport,"is_ready",return_value=True),
              patch.object(recovery,"request_reset") as send):
            page=self.browser.get("/saas/recuperar-senha/confirmar")
            self.assertEqual(page.status_code,200)
            html=page.get_data(as_text=True)
            self.assertIn('name="code"',html)
            self.assertIn('name="email"',html)
            self.assertIn('name="senha"',html)
            self.assertIn("Já recebi um código",html)
            send.assert_not_called()

    def test_request_page_offers_entry_for_existing_code(self):
        with patch.object(transport,"is_ready",return_value=True):
            page=self.browser.get("/saas/recuperar-senha")
        self.assertEqual(page.status_code,200)
        self.assertIn('href="/saas/recuperar-senha/confirmar"',
                      page.get_data(as_text=True))

    def test_mail_has_non_secret_direct_link(self):
        with (patch.object(transport,"_configuration",
                           return_value={"from":"noreply@example.invalid"}) as cfg,
              patch.object(transport,"_send") as send):
            transport.send_code("recipient@example.invalid","1234")
        cfg.assert_called_once()
        send.assert_called_once()
        body=send.call_args.args[2]
        self.assertIn("https://neuro-diagnosis.tech/saas/recuperar-senha/confirmar",body)
        self.assertIn("1234",body)
        self.assertNotIn("confirmar?code=",body)
        self.assertIn("nao",body.lower())

    def test_authenticated_saas_user_root_redirects_without_legacy_access(self):
        class FakeSaaSUser:
            pass
        class FakeProxy:
            is_authenticated=True
            def _get_current_object(self):
                return FakeSaaSUser()
        with (patch.object(store,"SaaSUser",FakeSaaSUser),
              patch.object(app_module,"current_user",FakeProxy())):
            root=self.browser.get("/")
            self.assertEqual(root.status_code,302)
            self.assertIn("/saas/",root.location)
            legacy=self.browser.get("/select-test")
            self.assertEqual(legacy.status_code,403)


if __name__=="__main__":
    unittest.main()
