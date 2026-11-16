"""Contract tests: every first-party SaaS module is packaged by Docker."""
import ast
from pathlib import Path
import unittest

PROJECT = Path(__file__).resolve().parents[1]


def copied_sources():
    lines = (PROJECT / "Dockerfile").read_text(encoding="utf-8").splitlines()
    return {
        value
        for line in lines
        if line.strip().startswith("COPY ")
        for value in line.strip().split()[1:-1]
        if not value.startswith("--")
    }


def covered(path, sources):
    normalized = str(path).replace("\\", "/")
    return normalized in sources or any(
        normalized.startswith(source)
        for source in sources
        if source.endswith("/")
    )


def local_module(name):
    if not name:
        return None
    candidate = PROJECT / (name.replace(".", "/") + ".py")
    if candidate.is_file():
        return candidate
    return None


class DockerPackagingTests(unittest.TestCase):
    def test_saas_runtime_python_modules_copied_to_image(self):
        sources = copied_sources()
        self.assertIn("saas/", sources)
        expected = [
            "app.py", "schema.py", "account_management.py",
            "bta_license_client.py",
        ] + [
            path.relative_to(PROJECT).as_posix()
            for path in (PROJECT / "saas").rglob("*.py")
        ]
        self.assertGreaterEqual(len(expected), 46)
        for relative in expected:
            with self.subTest(module=relative):
                self.assertTrue((PROJECT / relative).is_file())
                self.assertTrue(covered(relative, sources),
                                f"{relative} missing from Docker image")

    def test_no_first_party_python_dependency_missing(self):
        sources = copied_sources()
        packaged = [
            PROJECT / relative for relative in (
                "app.py", "schema.py", "account_management.py",
                "bta_license_client.py"
            )
        ]
        packaged += list((PROJECT / "saas").rglob("*.py"))
        packaged += list((PROJECT / "neurocore").rglob("*.py"))
        for path in packaged:
            tree = ast.parse(path.read_text(encoding="utf-8"))
            imports = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imports.extend(alias.name for alias in node.names)
                if isinstance(node, ast.ImportFrom) and node.module:
                    imports.append(node.module)
                    imports.extend(
                        node.module + "." + alias.name
                        for alias in node.names
                    )
            for module in imports:
                dependency = local_module(module)
                if dependency is None:
                    continue
                relative = dependency.relative_to(PROJECT).as_posix()
                with self.subTest(parent=str(path), dependency=module):
                    self.assertTrue(covered(relative, sources),
                                    f"{relative} missing from Docker image")


if __name__ == "__main__":
    unittest.main()
