"""Synthetic DDoS hardening checks. No external requests or load generation."""
import os
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import pymysql
from app import app
import saas_routes as routes

ROOT = Path(__file__).resolve().parents[1]


class DDoSGuardTests(unittest.TestCase):
    def setUp(self):
        self.before = {
            key: app.config.get(key) for key in
            ("TESTING", "MAX_CONTENT_LENGTH", "SESSION_COOKIE_SECURE", "SESSION_COOKIE_SAMESITE")
        }
        app.config["TESTING"] = True
        routes._health_cache.update(until=0.0, ok=False)
        self.client = app.test_client()

    def tearDown(self):
        app.config.update(self.before)
        routes._health_cache.update(until=0.0, ok=False)

    def test_readiness_cached_and_schema_still_verified(self):
        with patch.object(routes.store, "one", return_value={"ok": 1}) as query:
            first = self.client.get("/saas/saude")
            second = self.client.get("/saas/saude")
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(query.call_count, len(routes._HEALTH_READINESS_QUERIES))
        self.assertEqual(first.json["status"], "ready")
        routes._health_cache["until"] = 0
        with patch.object(routes.store, "one", side_effect=pymysql.MySQLError("synthetic")) as query:
            failed = self.client.get("/saas/saude")
            again = self.client.get("/saas/saude")
        self.assertEqual(failed.status_code, 503)
        self.assertEqual(again.status_code, 503)
        self.assertEqual(query.call_count, 1)

    def test_concurrent_readiness_probe_does_not_trigger_new_database_query(self):
        routes._health_cache.update(until=0.0, ok=False)
        routes._health_lock.acquire()
        try:
            with patch.object(routes.store, "one") as query:
                response = self.client.get("/saas/saude")
            self.assertEqual(response.status_code, 503)
            query.assert_not_called()
        finally:
            routes._health_lock.release()

    def test_oversized_post_fails_before_password_verification(self):
        app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024
        response = self.client.post("/saas/entrar", data={
            "csrf_token": "synthetic-not-valid",
            "senha": "x" * (2 * 1024 * 1024 + 40),
        })
        self.assertEqual(response.status_code, 413)

    def test_secure_response_headers_and_no_public_cache(self):
        with patch.dict(os.environ, {"SAAS_PRIMARY": "true"}):
            result = self.client.get("/saas/entrar")
            self.assertEqual(result.status_code, 200)
            self.assertEqual(result.headers.get("X-Frame-Options"), "DENY")
            self.assertEqual(result.headers.get("X-Content-Type-Options"), "nosniff")
            self.assertIn("frame-ancestors 'none'",
                          result.headers.get("Content-Security-Policy", ""))
            self.assertIn("max-age=", result.headers.get("Strict-Transport-Security", ""))
            self.assertEqual(result.headers.get("Cache-Control"), "private, no-store")
        source = (ROOT / "app.py").read_text(encoding="utf-8")
        self.assertIn("SESSION_COOKIE_SECURE=True", source)
        self.assertIn("SESSION_COOKIE_SAMESITE=\"Lax\"", source)

    def test_project_scoped_bluegreen_limits_and_no_trusted_proxy_header(self):
        script = (ROOT / "infra/host/neuro-router-bluegreen.sh").read_text(encoding="utf-8")
        compose = (ROOT / "docker-compose.saas.yml").read_text(encoding="utf-8")
        for name in ("neuro-general-limit", "neuro-auth-limit",
                     "neuro-health-limit", "neuro-global-inflight",
                     "neuro-ip-inflight", "neuro-auth-inflight",
                     "neuro-body-limit"):
            self.assertIn(name, script)
            self.assertIn(name, compose)
        for marker in ("neuro-bluegreen-probes:", "priority: 2200",
                       "amount: 48", "amount: 10", "amount: 4",
                       "maxRequestBodyBytes: 2097152",
                       "memRequestBodyBytes: 2097152"):
            self.assertIn(marker, script)
        self.assertIn("ipv6Subnet: 64", script)
        self.assertNotIn("ipStrategy:\n            depth:", script)
        self.assertIn("traefik.enable=${NEURO_TRAEFIK_ENABLED:-false}", compose)
        deploy = (ROOT / "infra/host/deploy-neuro-diagnosis-saas.sh").read_text(
            encoding="utf-8")
        self.assertIn("NEURO_ROUTER_SCRIPT_STALE", deploy)
        self.assertIn('cmp -s - "$ROUTER_SCRIPT"', deploy)

    def test_generated_traefik_template_parses_if_yaml_available(self):
        try:
            import yaml
        except ImportError:
            self.skipTest("PyYAML not installed; static contract still covered")
        script = (ROOT / "infra/host/neuro-router-bluegreen.sh").read_text(encoding="utf-8")
        content = script.split('cat > "$TMP" <<YAML\n', 1)[1].split("\nYAML\n", 1)[0]
        content = content.replace("\\`", "`").replace("$SLOT", "primary").replace("$PORT", "8781")
        doc = yaml.safe_load(content)
        routers = doc["http"]["routers"]
        middleware = doc["http"]["middlewares"]
        self.assertEqual(routers["neuro-bluegreen-probes"]["priority"], 2200)
        self.assertEqual(middleware["neuro-ip-inflight"]["inFlightReq"]["amount"], 10)
        self.assertEqual(middleware["neuro-global-inflight"]["inFlightReq"]["amount"], 48)
        self.assertEqual(middleware["neuro-body-limit"]["buffering"]["maxRequestBodyBytes"], 2097152)
        self.assertEqual(doc["http"]["services"]["neuro-bluegreen"]["loadBalancer"]
                         ["servers"][0]["url"], "http://127.0.0.1:8781")


if __name__ == "__main__":
    unittest.main()
