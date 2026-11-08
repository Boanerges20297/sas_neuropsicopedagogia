"""Activation queue permissions and route contracts using synthetic data."""
import unittest
from unittest.mock import patch
from app import app
import saas_store as store
import saas_portal_activation_queue as queue
import saas_portal_activation_routes as routes
from bta_license_client import LicenseDecision


class ActivationQueueScopeTests(unittest.TestCase):
    def test_professional_cannot_enumerate_other_patients(self):
        with patch.object(store,"one",return_value={
            "id":11,"global_role":"professional","active":1}), \
             patch.object(store,"all_rows",return_value=[]) as listed:
            self.assertEqual(queue.pending_activation_queue(11),[])
            self.assertEqual(listed.call_args.args[1],(0,11))
            sql=listed.call_args.args[0]
            self.assertIn("p.professional_user_id=%s",sql)
            self.assertIn("care_portal_client_activations",sql)
            self.assertIn("care_portal_login_requests",sql)
            self.assertIn("guardian_link.contact_id=intake.guardian_contact_id",sql)
            self.assertNotIn("initial_report_encrypted",sql)

    def test_administrators_can_see_all_tenants(self):
        for role in ("admin","superadmin"):
            with self.subTest(role=role), \
                 patch.object(store,"one",return_value={
                    "id":33,"global_role":role,"active":1}), \
                 patch.object(store,"all_rows",return_value=[]) as listed:
                queue.pending_activation_queue(33)
                self.assertEqual(listed.call_args.args[1],(1,33))

    def test_patient_and_invalid_actor_denied_without_listing(self):
        with patch.object(store,"one",return_value={
            "id":9,"global_role":"patient","active":1}), \
             patch.object(store,"all_rows") as listed:
            with self.assertRaises(PermissionError):
                queue.pending_activation_queue(9)
            listed.assert_not_called()
            with self.assertRaises(PermissionError):
                queue.pending_activation_queue(True)

    def test_suspended_and_unverified_contacts_not_eligible(self):
        sql=queue.QUEUE_SQL
        for fragment in (
            "req.status IN ('pending','active')",
            "activation.status='pending'",
            "guardian_link.verification_status='verified'",
            "contact.verification_status='verified'",
            "self_link.verification_status='verified'",
            "guardian_link.verified_by=p.professional_user_id",
            "self_link.verified_by=p.professional_user_id",
            "contact.contact_role='legal_guardian'",
            "p.birth_date > DATE_SUB(",
            "p.birth_date <= DATE_SUB(",
        ):
            self.assertIn(fragment,sql)


class ActivationQueueRouteTests(unittest.TestCase):
    def setUp(self):
        self.old=app.config["TESTING"]
        app.config["TESTING"]=True
        self.browser=app.test_client()
        self.user=store.SaaSUser({
            "id":33,"nome":"Admin synthetic","email":"admin@example.invalid",
            "global_role":"superadmin","active":1,
            "must_change_password":False,"mfa_enabled":True})
        self.get_user=patch.object(store,"get_user",side_effect=lambda uid:self.user)
        self.get_user.start()
        # Admins can review activations without creating a clinical tenant.
        self.workspace=patch("saas_routes.own_admin_workspace",return_value=None)
        self.workspace.start()
        self.permissions=patch.object(routes,"can_admin",return_value=True)
        self.permissions.start()
        with self.browser.session_transaction() as s:
            s["_user_id"]="saas:33"
            s["_fresh"]=True
            s["saas_auth"]=True
            s["saas_mfa_passed"]=True
            s["saas_csrf"]="activation-queue-test-csrf"

    def tearDown(self):
        self.permissions.stop()
        self.workspace.stop()
        self.get_user.stop()
        app.config["TESTING"]=self.old

    def test_global_admin_without_workspace_can_view_queue(self):
        record={
            "client_id":301,"patient_name":"Child Alpha",
            "tenant_id":201,"tenant_name":"Clinic Alpha",
            "professional_user_id":11,"clinician_name":"Doctor Alpha",
            "principal_id":104,"account_name":"Guardian Alpha",
            "representation_mode":"guardian","login_status":"pending"}
        with patch.object(routes,"pending_activation_queue",return_value=[record]) as listed, \
             patch.object(routes,"licensed_tenant") as licensed:
            response=self.browser.get("/saas/ativacoes")
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.headers["Cache-Control"],"private, no-store")
            body=response.get_data(as_text=True)
            self.assertIn("Child Alpha",body)
            self.assertIn("Doctor Alpha",body)
            self.assertIn("Guardian Alpha",body)
            self.assertIn("activation-queue-test-csrf",body)
            listed.assert_called_once_with(33)
            licensed.assert_not_called()

    def test_professional_is_licensed_before_listing(self):
        self.user=store.SaaSUser({
            "id":11,"nome":"Professional","email":"pro@example.invalid",
            "global_role":"professional","active":1,
            "must_change_password":False})
        with self.browser.session_transaction() as s:
            s["_user_id"]="saas:11"
        with patch.object(routes,"pending_activation_queue") as listed, \
             patch.object(routes,"licensed_tenant",return_value=(
                 {"id":201},LicenseDecision(status="unlicensed"))):
            self.assertEqual(self.browser.get("/saas/ativacoes").status_code,403)
            listed.assert_not_called()

    def test_patient_cannot_view_admin_activation_queue(self):
        self.user=store.SaaSUser({
            "id":104,"nome":"Patient","email":"person@example.invalid",
            "global_role":"patient","active":1,
            "must_change_password":False})
        with self.browser.session_transaction() as s:
            s["_user_id"]="saas:104"
        with patch.object(routes,"pending_activation_queue") as listed:
            self.assertEqual(self.browser.get("/saas/ativacoes").status_code,403)
            listed.assert_not_called()


if __name__=="__main__":
    unittest.main()
