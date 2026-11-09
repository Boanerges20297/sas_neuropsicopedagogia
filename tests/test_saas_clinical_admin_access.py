"""Regression: dual administrative/clinical roles and branded denial responses."""
import unittest
from unittest.mock import patch

from app import app
import saas_store as store
import saas_routes
import saas_neurocore_store as neuro_store


class ClinicalAdministratorAccessTests(unittest.TestCase):
    def setUp(self):
        self.previous_testing = app.config["TESTING"]
        app.config["TESTING"] = True
        self.client = app.test_client()
        self.user = store.SaaSUser({
            "id": 9, "nome": "Pessoa Administradora", "email": "sa@example.invalid",
            "global_role": "superadmin", "active": True,
            "must_change_password": False, "mfa_enabled": True,
        })
        self.tenant = {"id": 101, "nome": "Clinica Particular",
                       "slug": "admin-clinic-9", "status": "active"}
        self.identity_patch = patch.object(store, "get_user", return_value=self.user)
        self.permissions_patch = patch.object(saas_routes, "can_admin", return_value=True)
        self.workspace_patch = patch.object(saas_routes, "own_admin_workspace",
                                            return_value=self.tenant)
        self.identity_patch.start()
        self.permissions_patch.start()
        self.workspace_patch.start()
        with self.client.session_transaction() as sess:
            sess["_user_id"] = "saas:9"
            sess["_fresh"] = True
            sess["saas_auth"] = True
            sess["saas_mfa_passed"] = True
            sess["saas_csrf"] = "test-csrf"

    def tearDown(self):
        self.workspace_patch.stop()
        self.permissions_patch.stop()
        self.identity_patch.stop()
        app.config["TESTING"] = self.previous_testing

    def test_superadmin_own_clinic_is_available_without_cross_tenant_listing(self):
        with patch.object(store, "list_clients", return_value=[]) as listing:
            response = self.client.get("/saas/pacientes")
        self.assertEqual(response.status_code, 200)
        self.assertIn('href="/saas/pacientes"', response.get_data(as_text=True))
        listing.assert_called_once_with(9, 101)

    def test_administrator_own_clinic_still_works(self):
        self.user.role = "admin"
        with patch.object(store, "list_clients", return_value=[]) as listing:
            response = self.client.get("/saas/pacientes")
        self.assertEqual(response.status_code, 200)
        listing.assert_called_once_with(9, 101)

    def test_admin_and_superadmin_without_own_tenant_cannot_access_clinic(self):
        with patch.object(saas_routes, "own_admin_workspace", return_value=None):
            for role in ("admin", "superadmin"):
                with self.subTest(role=role):
                    self.user.role = role
                    response = self.client.get("/saas/pacientes")
                    self.assertEqual(response.status_code, 403)
                    self.assertIn("Este recurso não está disponível",
                                  response.get_data(as_text=True))
                    self.assertNotIn("<h1>Forbidden</h1>",
                                     response.get_data(as_text=True))

    def test_clinic_permission_is_still_required_for_administrator(self):
        self.user.role = "admin"
        with patch.object(saas_routes, "can_admin", return_value=False):
            response = self.client.get("/saas/pacientes")
        self.assertEqual(response.status_code, 403)

    def test_other_professionals_patient_remains_inaccessible(self):
        with patch.object(neuro_store, "scoped_client", return_value=None) as lookup:
            response = self.client.get("/saas/pacientes/222")
        self.assertEqual(response.status_code, 404)
        lookup.assert_called_once_with(9, 101, 222)
        self.assertIn("Página não encontrada", response.get_data(as_text=True))

    def test_permission_error_json_response_retains_http_code(self):
        self.user.role = "admin"
        with patch.object(saas_routes, "can_admin", return_value=False):
            response = self.client.get("/saas/pacientes",
                                       headers={"Accept": "application/json"})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json()["codigo"], 403)

    def test_invalid_csrf_is_branded_but_is_still_http_400(self):
        response = self.client.post("/saas/meu-espaco/ativar",
                                    data={"csrf_token": "invalid"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("Não foi possível concluir", response.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
