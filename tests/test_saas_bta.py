"""Contract tests for the Neuro-Diagnosis BTA S2S adapter; no production calls."""
import base64
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

import bta_license_client as bta
import saas_routes


class BTAIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.private = Ed25519PrivateKey.generate()
        self.path = Path(self.temp.name) / "test-private.pem"
        self.path.write_bytes(self.private.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()))
        self.client = bta.BTAClient(
            base_url="http://bta.internal", client_id="neuro-diagnosis-backend",
            key_id="neuro-test", key_file=str(self.path))

    def tearDown(self):
        self.temp.cleanup()

    def test_signed_headers_validate_according_to_bta_contract(self):
        body = b'{"customer_key":"neuro-diagnosis:tenant:prof-123"}'
        headers = self.client.signed_headers("POST", bta.RESOLVE_PATH, body)
        message = "\n".join([
            "POST", bta.RESOLVE_PATH, headers["X-BTA-Timestamp"],
            headers["X-BTA-Nonce"], hashlib.sha256(body).hexdigest(),
        ]).encode()
        self.private.public_key().verify(base64.b64decode(headers["X-BTA-Signature"]), message)
        self.assertEqual(headers["X-BTA-Client-Id"], "neuro-diagnosis-backend")

    def test_license_contract_is_checked_for_correct_product_and_state(self):
        result = {
            "contract_version": 1, "product": "neuro-diagnosis", "licensed": True,
            "license": {"state": "active"}, "limits": {}, "entitlements": {},
        }
        with patch.object(bta.requests, "post", return_value=SimpleNamespace(
                status_code=200, json=lambda: result)) as post:
            decision = self.client.resolve("prof-123", "Profissional")
        self.assertTrue(decision.allowed)
        self.assertEqual(json.loads(post.call_args.kwargs["data"])["customer_key"],
                         "neuro-diagnosis:tenant:prof-123")
        result["product"] = "outro-produto"
        with patch.object(bta.requests, "post", return_value=SimpleNamespace(
                status_code=200, json=lambda: result)):
            self.assertFalse(self.client.resolve("prof-123").allowed)

    def test_resolve_and_trial_use_same_stable_tenant_slug(self):
        tenant = {"id": 123, "slug": "prof-123", "nome": "Exemplo", "status": "active"}
        fake_user = SimpleNamespace(id=8, is_practitioner=lambda: True, is_admin=lambda: False)
        with patch.object(saas_routes, "current_user", fake_user), \
             patch.object(saas_routes, "is_saas_account", return_value=True), \
             patch.object(saas_routes.store, "own_tenant", return_value=tenant), \
             patch.object(saas_routes, "resolve_tenant_license",
                          return_value=bta.LicenseDecision("unlicensed")) as resolve:
            saas_routes.licensed_tenant()
        resolve.assert_called_once_with("prof-123", "Exemplo")

    def test_administrator_has_permanent_access_without_bta_call(self):
        tenant = {"id": 2, "slug": "admin-workspace", "nome": "Administradora"}
        admin = SimpleNamespace(id=1, is_practitioner=lambda: True, is_admin=lambda: True)
        with patch.object(saas_routes, "current_user", admin), \
             patch.object(saas_routes, "is_saas_account", return_value=True), \
             patch.object(saas_routes, "own_admin_workspace", return_value=tenant), \
             patch.object(saas_routes, "can_admin", return_value=True), \
             patch.object(saas_routes, "resolve_tenant_license") as remote:
            own, decision = saas_routes.licensed_tenant()
        self.assertEqual(own, tenant)
        self.assertEqual(decision.status, "exempt")
        self.assertTrue(decision.allowed)
        remote.assert_not_called()

    def test_regular_professional_remains_blocked_without_license(self):
        tenant = {"id": 3, "slug": "prof-regular", "nome": "Profissional"}
        professional = SimpleNamespace(id=9, is_practitioner=lambda: True, is_admin=lambda: False)
        with patch.object(saas_routes, "current_user", professional), \
             patch.object(saas_routes, "is_saas_account", return_value=True), \
             patch.object(saas_routes.store, "own_tenant", return_value=tenant), \
             patch.object(saas_routes, "resolve_tenant_license",
                          return_value=bta.LicenseDecision(status="unavailable")) as remote:
            _, decision = saas_routes.licensed_tenant()
        self.assertFalse(decision.allowed)
        remote.assert_called_once_with("prof-regular", "Profissional")


if __name__ == "__main__":
    unittest.main()
