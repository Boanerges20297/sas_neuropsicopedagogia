"""Admin clinic workspace is opt-in, never grants access to other tenants."""
import unittest
from unittest.mock import patch

from app import app
import saas_store as store
import saas_admin_workspace as admin_workspace


class AdminWorkspaceRouteTests(unittest.TestCase):
    def setUp(self):
        self.prev = app.config["TESTING"]
        app.config["TESTING"] = True
        self.client = app.test_client()
        self.admin = store.SaaSUser({
            "id": 9, "nome": "Admin Sintético", "email": "admin@example.invalid",
            "global_role": "admin", "active": True, "must_change_password": False,
        })
        self.loader = patch.object(store, "get_user", return_value=self.admin)
        self.loader.start()
        self.permissions=patch("saas_routes.can_admin",return_value=True)
        self.permissions.start()
        with self.client.session_transaction() as sess:
            sess["_user_id"] = "saas:9"
            sess["_fresh"] = True
            sess["saas_auth"] = True
            sess["saas_csrf"] = "admin-csrf"

    def tearDown(self):
        self.permissions.stop()
        self.loader.stop()
        app.config["TESTING"] = self.prev

    def test_admin_without_private_tenant_gets_activation_option_not_patient_link(self):
        with patch("saas_routes.own_admin_workspace", return_value=None), patch.object(
            store, "admin_global_stats", return_value=dict(
                professionals=0, pending=0, active_tenants=0, total_clients=0)):
            response = self.client.get("/saas/painel")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Ativar meu espaço clínico", html)
        self.assertIn('name="csrf_token" value="admin-csrf"', html)
        self.assertNotIn('href="/saas/pacientes"', html)

    def test_admin_activation_requires_csrf_and_post(self):
        with patch.object(admin_workspace, "activate_personal_admin_workspace") as provision:
            self.assertIn(self.client.get("/saas/meu-espaco/ativar").status_code, (403, 405))
            self.assertEqual(self.client.post(
                "/saas/meu-espaco/ativar", data={"csrf_token": "wrong"}).status_code, 400)
            provision.assert_not_called()
            response = self.client.post(
                "/saas/meu-espaco/ativar", data={"csrf_token": "admin-csrf"})
            self.assertEqual(response.status_code, 302)
            provision.assert_called_once_with(9)

    def test_professional_cannot_activate_administrative_workspace(self):
        user = store.SaaSUser({
            "id": 8, "nome": "Profissional", "email": "prof@example.invalid",
            "global_role": "professional", "active": True, "must_change_password": False,
        })
        with patch.object(store, "get_user", return_value=user):
            self.assertEqual(self.client.post(
                "/saas/meu-espaco/ativar", data={"csrf_token": "admin-csrf"}).status_code, 403)


if __name__ == "__main__":
    unittest.main()
