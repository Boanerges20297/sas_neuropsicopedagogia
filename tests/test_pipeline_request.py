"""Unit checks for the release-request contract (no deployment calls)."""
import importlib.util
import json
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
MODULE = ROOT / "scripts" / "release_request.py"
spec = importlib.util.spec_from_file_location("neuro_release_request", MODULE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
class ReleaseContractTests(unittest.TestCase):
    def setUp(self):
        self.version = {"versionName": "0.1.0", "versionCode": 1}
        self.request = {
            "schemaVersion": 1,
            "action": "release",
            "requestId": "neuro-0.1.0-1-r1",
            "versionName": "0.1.0",
            "versionCode": 1,
        }
    def test_valid_request(self):
        self.assertEqual(module.validate(self.request, self.version),
                         ("neuro-0.1.0-1-r1", "0.1.0", 1))
    def test_optional_release_request_must_be_valid(self):
        request_path = ROOT / ".release" / "request.json"
        if request_path.exists():
            request = json.loads(request_path.read_text(encoding="utf-8"))
            self.assertEqual(
                module.validate(request, self.version),
                (request["requestId"], "0.1.0", 1),
            )
    def test_rejects_unexpected_values(self):
        modifications = [
            {"schemaVersion": 2},
            {"action": "deploy"},
            {"requestId": "../danger"},
            {"versionName": "0.2.0"},
            {"versionCode": 2},
            {"versionCode": True},
            {"extra": "not allowed"},
        ]
        for update in modifications:
            with self.subTest(update=update):
                request = dict(self.request, **update)
                with self.assertRaises(ValueError):
                    module.validate(request, self.version)
    def test_version_file_matches_contract(self):
        data = json.loads((ROOT / "release.json").read_text(encoding="utf-8-sig"))
        self.assertEqual(data, self.version)
if __name__ == "__main__":
    unittest.main()
