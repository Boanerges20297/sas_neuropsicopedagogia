"""NeuroCore route protections with synthetic users; zero live clinical data."""
from pathlib import Path
import unittest
from unittest.mock import patch

from app import app
import saas_store as store
import saas_neurocore_routes as routes
from bta_license_client import LicenseDecision

ROOT = Path(__file__).resolve().parents[1]


class NeuroCoreSaaSRouteTests(unittest.TestCase):
    def setUp(self):
        self.old_testing = app.config["TESTING"]
        app.config["TESTING"] = True
        self.client = app.test_client()
        self.user = store.SaaSUser({
            "id": 7, "nome": "Profissional Sintético", "email": "tester@example.invalid",
            "global_role": "professional", "active": 1, "must_change_password": 0,
        })
        self.loader = patch.object(store, "get_user", return_value=self.user)
        self.loader.start()
        self.tenant = {"id": 11, "nome": "Workspace Sintético"}
        self.license = LicenseDecision(status="exempt")
        self.licensed = patch.object(routes, "licensed_tenant", return_value=(
            self.tenant, self.license))
        self.licensed.start()
        self.patient = {"id": 16, "nome": "Pessoa Sintética", "status": "active"}
        self.patient_check = patch.object(routes.nc_store, "scoped_client",
                                          return_value=self.patient)
        self.patient_check.start()
        self.reviews = patch.object(routes.nc_store, "list_reviews", return_value=[])
        self.reviews.start()
        self.review = patch.object(routes.nc_store, "get_review", return_value=None)
        self.review.start()
        with self.client.session_transaction() as sess:
            sess["_user_id"] = "saas:7"
            sess["_fresh"] = True
            sess["saas_auth"] = True
            sess["saas_csrf"] = "test-csrf"

    def tearDown(self):
        self.review.stop()
        self.reviews.stop()
        self.patient_check.stop()
        self.licensed.stop()
        self.loader.stop()
        app.config["TESTING"] = self.old_testing

    def test_patient_workspace_renders_two_topics(self):
        response = self.client.get("/saas/pacientes/16")
        self.assertEqual(response.status_code, 200)
        page = response.get_data(as_text=True)
        self.assertIn("Pessoa Sintética", page)
        self.assertIn("/saas/pacientes/16/neurocore/tea", page)
        self.assertIn("/saas/pacientes/16/neurocore/tdah", page)
        self.assertIn("nem emitem diagnóstico", page)

    def test_review_view_has_eight_documentation_fields(self):
        response = self.client.get("/saas/pacientes/16/neurocore/tdah")
        self.assertEqual(response.status_code, 200)
        page = response.get_data(as_text=True)
        self.assertEqual(page.count('name="status_'), 8)
        self.assertIn("Não há pontuação", page)
        self.assertIn('name="csrf_token" value="test-csrf"', page)

    def test_patient_from_another_tenant_is_not_found(self):
        with patch.object(routes.nc_store, "scoped_client", return_value=None):
            self.assertEqual(self.client.get("/saas/pacientes/16").status_code, 404)
            self.assertEqual(self.client.get(
                "/saas/pacientes/16/neurocore/tea").status_code, 404)
            self.assertEqual(self.client.post(
                "/saas/pacientes/16/neurocore/tea",
                data={"csrf_token": "test-csrf"}).status_code, 404)

    def test_unknown_topic_is_not_found(self):
        self.assertEqual(self.client.get(
            "/saas/pacientes/16/neurocore/diagnostico").status_code, 404)

    def test_unlicensed_profile_cannot_access_or_write(self):
        with patch.object(routes, "licensed_tenant", return_value=(
            self.tenant, LicenseDecision(status="unlicensed"))):
            self.assertEqual(self.client.get(
                "/saas/pacientes/16/neurocore/tea").status_code, 403)
            self.assertEqual(self.client.post(
                "/saas/pacientes/16/neurocore/tea",
                data={"csrf_token": "test-csrf"}).status_code, 403)

    def test_csrf_required_for_write(self):
        with patch.object(routes.nc_store, "save_review") as save:
            response = self.client.post("/saas/pacientes/16/neurocore/tea",
                                        data={"csrf_token": "wrong"})
        self.assertEqual(response.status_code, 400)
        save.assert_not_called()

    def test_invalid_status_not_saved(self):
        with patch.object(routes.nc_store, "save_review") as save:
            response = self.client.post("/saas/pacientes/16/neurocore/tea",
                data={"csrf_token": "test-csrf",
                      "status_historico_desenvolvimento": "diagnosticado"})
        self.assertEqual(response.status_code, 400)
        save.assert_not_called()

    def test_valid_write_is_versioned_and_redirects(self):
        with patch.object(routes.nc_store, "save_review") as save:
            response = self.client.post("/saas/pacientes/16/neurocore/tdah",
                data={"csrf_token": "test-csrf",
                      "status_historico_desenvolvimento": "documentado"})
        self.assertEqual(response.status_code, 302)
        self.assertIn("/saas/pacientes/16/neurocore/tdah", response.location)
        args = save.call_args.args
        self.assertEqual(args[:4], (7, 11, 16, "tdah"))
        self.assertEqual(args[4]["historico_desenvolvimento"], "documentado")
        self.assertEqual(args[5], "0.1.0")

    def test_no_real_login_no_data_access(self):
        self.loader.stop()
        with app.test_client() as guest:
            response = guest.get("/saas/pacientes/16/neurocore/tea")
            self.assertIn(response.status_code, (302, 401))
        self.loader.start()


class NeuroCoreMigrationContractTests(unittest.TestCase):
    def test_migration_is_tenant_bound_and_idempotent(self):
        script = (ROOT / "scripts/mysql_neurocore_review_migration.sql").read_text(
            encoding="utf-8")
        self.assertIn("CREATE TABLE IF NOT EXISTS neurocore_evidence_reviews", script)
        self.assertIn("FOREIGN KEY(client_id, tenant_id)", script)
        self.assertIn("FOREIGN KEY(tenant_id,professional_user_id)", script)
        self.assertIn("UNIQUE KEY uq_nc_evidence_owner_topic", script)

    def test_deploy_backup_precedes_migration_and_web(self):
        deploy = (ROOT / "infra/host/deploy-neuro-diagnosis-saas.sh").read_text(
            encoding="utf-8")
        b = deploy.index("NEURO_BACKUP_INVALID")
        m = deploy.index("mysql_neurocore_review_migration.sql")
        web = deploy.index('up -d --no-deps --force-recreate --no-build web', m)
        self.assertLess(b, m)
        self.assertLess(m, web)
        self.assertIn("mysql_saas_profile_migration.sql", deploy)


if __name__ == "__main__":
    unittest.main()
