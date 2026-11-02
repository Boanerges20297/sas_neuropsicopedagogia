"""Contract tests: every first-party module imported by the SaaS runtime is in the Docker image."""
import ast
from pathlib import Path
import unittest

PROJECT = Path(__file__).resolve().parents[1]


class DockerPackagingTests(unittest.TestCase):
    def test_saas_runtime_python_modules_copied_to_image(self):
        dockerfile = (PROJECT / "Dockerfile").read_text(encoding="utf-8")
        copy_lines = [
            line.strip().split()
            for line in dockerfile.splitlines()
            if line.strip().startswith("COPY ") and line.strip().endswith(" ./")
        ]
        copied = {value for parts in copy_lines for value in parts[1:-1]
                  if not value.startswith("--")}
        entrypoint = ["app.py", "saas_routes.py", "saas_store.py",
                      "saas_profile_routes.py", "saas_profile_data.py",
                      "saas_scope.py", "account_management.py",
                      "bta_license_client.py", "schema.py"]
        for path in entrypoint:
            with self.subTest(module=path):
                self.assertTrue((PROJECT / path).is_file())
                self.assertIn(path, copied, f"{path} missing from Docker image")

    def test_no_first_party_python_dependency_missing(self):
        dockerfile = (PROJECT / "Dockerfile").read_text(encoding="utf-8")
        copy_lines = [
            line.strip().split()
            for line in dockerfile.splitlines()
            if line.strip().startswith("COPY ") and line.strip().endswith(" ./")
        ]
        copied = {value for parts in copy_lines for value in parts[1:-1]
                  if not value.startswith("--")}
        for module in sorted(copied):
            if not module.endswith(".py"):
                continue
            tree = ast.parse((PROJECT / module).read_text(encoding="utf-8"))
            names = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    names.add(node.module.split(".")[0])
                elif isinstance(node, ast.Import):
                    names.update(alias.name.split(".")[0] for alias in node.names)
            for dep in names:
                local = PROJECT / (dep + ".py")
                if local.is_file():
                    with self.subTest(parent=module, dependency=dep):
                        self.assertIn(local.name, copied)


if __name__ == "__main__":
    unittest.main()
