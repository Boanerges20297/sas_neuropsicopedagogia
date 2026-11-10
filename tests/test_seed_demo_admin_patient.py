"""Synthetic administrator demo patient: strict single-admin scope and idempotence."""
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from unittest.mock import patch
import unittest

from scripts import seed_demo_admin_patient as demo


class Cursor:
    def __init__(self, rows=None, lists=None):
        self.rows = list(rows or [])
        self.lists = list(lists or [])
        self.calls = []
        self.lastrowid = 100

    def execute(self, statement, args=()):
        self.calls.append((statement, args))

    def fetchone(self):
        return self.rows.pop(0) if self.rows else None

    def fetchall(self):
        return self.lists.pop(0) if self.lists else []


@contextmanager
def tx(cur):
    yield cur


class DemoPatientContract(unittest.TestCase):
    def test_admin_must_be_unique_and_have_clinic_right(self):
        with patch.object(demo.store, "all_rows",
                          return_value=[{"id": 3}, {"id": 4}]):
            with self.assertRaises(demo.SeedRefused):
                demo.select_admin()
        with patch.object(demo.store, "all_rows",
                          return_value=[{"id": 3}, {"id": 4}]), \
             patch.object(demo.access, "can_admin", return_value=True):
            self.assertEqual(demo.select_admin(4), 4)
        with patch.object(demo.store, "all_rows", return_value=[{"id": 3}]), \
             patch.object(demo.access, "can_admin", return_value=False):
            with self.assertRaises(demo.SeedRefused):
                demo.select_admin()

    def test_dry_run_makes_no_database_writes_or_activations(self):
        with patch.object(demo, "select_admin", return_value=7), \
             patch.object(demo.workspace, "own_admin_workspace", return_value=None), \
             patch.object(demo.workspace, "activate_personal_admin_workspace") as act, \
             patch.object(demo.store, "transaction") as db:
            result = demo.seed()
        self.assertEqual(result["status"], "would_create")
        self.assertTrue(result["workspace_activation_needed"])
        db.assert_not_called()
        act.assert_not_called()

    def test_apply_creates_only_scoped_minor_and_fake_guardian(self):
        cur = Cursor(rows=[{"id": 11}], lists=[[]])
        with patch.object(demo, "select_admin", return_value=7), \
             patch.object(demo.workspace, "own_admin_workspace",
                          return_value={"id": 11}), \
             patch.object(demo.store, "transaction", return_value=tx(cur)), \
             patch.object(demo.store, "audit") as audit, \
             patch.object(demo.intake, "_cipher") as cipher:
            cipher.return_value.encrypt.return_value = b"encrypted-synthetic-text"
            result = demo.seed(apply=True)
        self.assertEqual(result["status"], "created")
        self.assertEqual(result["client_id"], 100)
        sql = "\n".join(stmt for stmt, _ in cur.calls)
        self.assertIn("owner_user_id=%s", sql)
        self.assertIn("INSERT INTO clients", sql)
        self.assertIn("INSERT INTO care_client_contacts", sql)
        self.assertIn("INSERT INTO care_patient_intakes", sql)
        self.assertNotIn("INSERT INTO users", sql)
        guardian = next(args for stmt, args in cur.calls
                        if "INSERT INTO care_client_contacts" in stmt)
        self.assertEqual(guardian, (11, 100, 7, demo.DEMO_GUARDIAN))
        clinic = next(args for stmt, args in cur.calls
                      if "INSERT INTO care_patient_intakes" in stmt)
        self.assertEqual(clinic[3], b"encrypted-synthetic-text")
        self.assertIn("NULL", sql)
        audit.assert_called_once()

    def test_repeat_seed_returns_same_patient_and_does_not_insert(self):
        cur = Cursor(rows=[{"id": 11}, {"representation_mode": "guardian",
                                      "full_name": demo.DEMO_GUARDIAN, "email": None}],
                     lists=[[{"id": 123, "birth_date": date(2016, 8, 18)}]])
        with patch.object(demo, "select_admin", return_value=7), \
             patch.object(demo.workspace, "own_admin_workspace",
                          return_value={"id": 11}), \
             patch.object(demo.store, "transaction", return_value=tx(cur)), \
             patch.object(demo.store, "audit") as audit, \
             patch.object(demo.intake, "_cipher") as cipher:
            cipher.return_value.encrypt.return_value = b"encrypted"
            result = demo.seed(apply=True)
        self.assertEqual(result["status"], "already_exists")
        self.assertEqual(result["client_id"], 123)
        self.assertFalse(any("INSERT" in stmt for stmt, _ in cur.calls))
        audit.assert_not_called()

    def test_existing_name_with_inconsistent_birth_is_not_overwritten(self):
        cur = Cursor(rows=[{"id": 11}],
                     lists=[[{"id": 123, "birth_date": date(2018, 1, 1)}]])
        with patch.object(demo, "select_admin", return_value=7), \
             patch.object(demo.workspace, "own_admin_workspace",
                          return_value={"id": 11}), \
             patch.object(demo.store, "transaction", return_value=tx(cur)), \
             patch.object(demo.intake, "_cipher") as cipher:
            cipher.return_value.encrypt.return_value = b"encrypted"
            with self.assertRaises(demo.SeedRefused):
                demo.seed(apply=True)
        self.assertFalse(any("INSERT" in stmt for stmt, _ in cur.calls))

    def test_docker_build_context_contains_demo_seed(self):
        root = Path(__file__).resolve().parents[1]
        rules = (root / '.dockerignore').read_text(encoding='utf-8').splitlines()
        self.assertIn('scripts/*', rules)
        self.assertIn('!scripts/seed_demo_admin_patient.py', rules)
        self.assertLess(rules.index('scripts/*'),
                        rules.index('!scripts/seed_demo_admin_patient.py'))
        dockerfile = (root / 'Dockerfile').read_text(encoding='utf-8')
        self.assertIn('COPY --chown=neuro:neuro scripts/seed_demo_admin_patient.py',
                      dockerfile)

    def test_no_real_identity_or_automatic_seed_on_import(self):
        self.assertEqual(demo.DEMO_BIRTH, "2016-08-18")
        self.assertIn("FICTICIO", demo.DEMO_NAME)
        self.assertNotIn("@", demo.DEMO_REPORT)
        self.assertNotIn("@", demo.DEMO_GUARDIAN)


if __name__ == "__main__":
    unittest.main()
