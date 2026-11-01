"""Static guardrails for the isolated non-Actions release pipeline."""
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
class PipelineStructureTests(unittest.TestCase):
    def test_release_request_is_explicit_and_optional(self):
        request_path = ROOT / ".release" / "request.json"
        if request_path.exists():
            import json
            from importlib import util
            module_path = ROOT / "scripts" / "release_request.py"
            spec = util.spec_from_file_location("neuro_release_contract", module_path)
            module = util.module_from_spec(spec)
            spec.loader.exec_module(module)
            request = json.loads(request_path.read_text(encoding="utf-8"))
            release = json.loads((ROOT / "release.json").read_text(encoding="utf-8"))
            module.validate(request, release)
        self.assertTrue((ROOT / ".release" / "README.md").exists())
    def test_no_patient_data_packaged(self):
        ignored = (ROOT / ".dockerignore").read_text(encoding="utf-8-sig")
        for pattern in (".env", "*.db", "*.xlsx", "*.pdf", ".venv"):
            with self.subTest(pattern=pattern):
                self.assertIn(pattern, ignored)
    def test_isolated_host_gateway(self):
        gateway = (ROOT / "infra" / "host" / "neuro-host-gateway").read_text(
            encoding="utf-8-sig"
        )
        self.assertIn("SSH_ORIGINAL_COMMAND", gateway)
        self.assertIn("NEURO_GATEWAY_DENIED", gateway)
        self.assertIn("deploy", gateway)
        self.assertIn("smoke", gateway)
    def test_compose_local_only_and_runner_no_socket(self):
        compose = (ROOT / "docker-compose.production.yml").read_text(
            encoding="utf-8-sig"
        )
        self.assertIn("127.0.0.1:8781:8000", compose)
        self.assertNotIn("/var/run/docker.sock", compose)
        self.assertIn("read_only: true", compose)
        self.assertNotIn("privileged: true", compose)
    def test_health_endpoints_do_not_require_login(self):
        from app import app
        app.config["TESTING"] = True
        with app.test_client() as client:
            self.assertEqual(client.get("/health/live").status_code, 200)
            self.assertEqual(client.get("/health/ready").status_code, 200)
if __name__ == "__main__":
    unittest.main()
