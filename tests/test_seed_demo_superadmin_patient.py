"""Synthetic adult patient must belong solely to the intended superadmin."""
from contextlib import contextmanager
from datetime import date
from unittest.mock import patch
import unittest

from scripts import seed_demo_superadmin_patient as demo


class Cursor:
    def __init__(self, one=(), many=()):
        self.one = list(one)
        self.many = list(many)
        self.calls = []
        self.lastrowid = 71

    def execute(self, sql, params=()):
        self.calls.append((sql, params))

    def fetchone(self):
        return self.one.pop(0) if self.one else None

    def fetchall(self):
        return self.many.pop(0) if self.many else []


@contextmanager
def tx(c):
    yield c


class SuperadminDemoTests(unittest.TestCase):
    def test_unique_superadmin_only_and_name_match(self):
        with patch.object(demo.store, "all_rows", return_value=[
                {"id": 2, "nome": "Boanerges Teixeira de Almeida"}]):
            self.assertEqual(demo.select_owner(), 2)
        with patch.object(demo.store, "all_rows", return_value=[
                {"id": 2, "nome": "Outra Pessoa"}]):
            with self.assertRaises(ValueError):
                demo.select_owner()
        with patch.object(demo.store, "all_rows", return_value=[
                {"id": 2, "nome": "Boanerges Teixeira de Almeida"},
                {"id": 3, "nome": "Boanerges Falso"}]):
            with self.assertRaises(ValueError):
                demo.select_owner()

    def test_dry_run_has_no_writes(self):
        with patch.object(demo, "select_owner", return_value=2), \
             patch.object(demo.work, "own_admin_workspace", return_value=None), \
             patch.object(demo.work, "activate_personal_admin_workspace") as create, \
             patch.object(demo.store, "transaction") as transaction:
            result = demo.seed()
        self.assertEqual(result["status"], "would_create")
        self.assertIsNone(result["tenant_id"])
        create.assert_not_called()
        transaction.assert_not_called()

    def test_apply_creates_no_account_and_scoped_intake(self):
        cur = Cursor(one=[{"id": 8}], many=[[]])
        with patch.object(demo, "select_owner", return_value=2), \
             patch.object(demo.work, "own_admin_workspace", return_value={"id": 8}), \
             patch.object(demo.store, "transaction", return_value=tx(cur)), \
             patch.object(demo.store, "audit") as audit, \
             patch.object(demo.intake, "_cipher") as cipher:
            cipher.return_value.encrypt.return_value = b"secret"
            record = demo.seed(apply=True)
        self.assertEqual(record["status"], "created")
        self.assertEqual(record["client_id"], 71)
        queries = " ".join(q for q, _ in cur.calls)
        self.assertIn("INSERT INTO clients", queries)
        self.assertIn("INSERT INTO care_patient_intakes", queries)
        self.assertNotIn("INSERT INTO users", queries)
        self.assertNotIn("care_client_contacts", queries)
        self.assertIn("NULL", queries)
        audit.assert_called_once()

    def test_idempotent_and_wrong_history_rejected(self):
        cur = Cursor(one=[{"id": 8}, {"representation_mode": "self"}],
                     many=[[{"id": 71, "birth_date": date(2001, 5, 15)}]])
        with patch.object(demo, "select_owner", return_value=2), \
             patch.object(demo.work, "own_admin_workspace", return_value={"id": 8}), \
             patch.object(demo.store, "transaction", return_value=tx(cur)), \
             patch.object(demo.intake, "_cipher") as cipher:
            cipher.return_value.encrypt.return_value = b"secret"
            record = demo.seed(apply=True)
        self.assertEqual(record["status"], "already_exists")
        self.assertFalse(any("INSERT" in q for q, _ in cur.calls))
        cur = Cursor(one=[{"id": 8}], many=[[{"id": 71, "birth_date": date(2000, 5, 15)}]])
        with patch.object(demo, "select_owner", return_value=2), \
             patch.object(demo.work, "own_admin_workspace", return_value={"id": 8}), \
             patch.object(demo.store, "transaction", return_value=tx(cur)), \
             patch.object(demo.intake, "_cipher") as cipher:
            cipher.return_value.encrypt.return_value = b"secret"
            with self.assertRaises(ValueError):
                demo.seed(apply=True)

    def test_docker_context_explicitly_whitelists_script(self):
        root = demo.ROOT
        ignore = (root / ".dockerignore").read_text(encoding="utf-8")
        docker = (root / "Dockerfile").read_text(encoding="utf-8")
        self.assertIn("!scripts/seed_demo_superadmin_patient.py", ignore)
        self.assertIn("scripts/seed_demo_superadmin_patient.py", docker)


if __name__ == "__main__":
    unittest.main()
