"""Isolated superadmin bootstrap tests: no real credentials or MySQL."""
from contextlib import contextmanager, redirect_stdout
from io import StringIO
from unittest.mock import patch
import os
import unittest

from app import bcrypt
from scripts import provision_superadmin as mod


class FakeCursor:
    def __init__(self, admins=None):
        self.admins = admins if admins is not None else [
            {"id":1,"email":"old-admin@example.invalid","global_role":"admin","active":1}]
        self.queries=[]
        self.lastrowid=77
        self._fetch=[]
        self._one=None
    def execute(self, sql, args=()):
        self.queries.append((sql,args))
        if "FROM users WHERE global_role" in sql and sql.startswith("SELECT id,"):
            self._fetch=list(self.admins)
        elif "SELECT id FROM users WHERE email" in sql:
            self._one=None
        elif "SELECT id FROM tenants WHERE owner_user_id" in sql:
            self._one={"id":5}
        elif "INSERT INTO users" in sql:
            self.lastrowid=77
        elif "INSERT INTO tenants" in sql:
            self.lastrowid=55
    def fetchall(self):
        return self._fetch
    def fetchone(self):
        return self._one


class BootstrapTests(unittest.TestCase):
    def run_with_cursor(self, cursor, allow="1"):
        @contextmanager
        def tx():
            yield cursor
        captured=StringIO()
        with patch.object(mod,"transaction",tx), patch.dict(os.environ,{
            "SAAS_SUPERADMIN_EMAIL":"new-admin@example.invalid",
            "SAAS_SUPERADMIN_PROVISION_APPROVED":allow
        }):
            with redirect_stdout(captured):
                mod.provision()
        return captured.getvalue()

    def test_existing_test_admin_is_promoted_and_temporary_secret_works(self):
        cursor=FakeCursor()
        output=self.run_with_cursor(cursor)
        self.assertIn("SUPERADMIN_PROVISIONED",output)
        self.assertIn("TEMPORARY_PASSWORD=",output)
        secret=output.split("TEMPORARY_PASSWORD=",1)[1].splitlines()[0]
        update=next((args for sql,args in cursor.queries if sql.startswith("UPDATE users SET")),None)
        self.assertEqual(update[0],"new-admin@example.invalid")
        self.assertTrue(bcrypt.check_password_hash(update[1],secret))
        self.assertEqual(update[2],1)
        self.assertTrue(any("must_change_password=1" in sql for sql,args in cursor.queries))
        self.assertFalse(any(sql.startswith("INSERT INTO users") for sql,args in cursor.queries))

    def test_already_provisioned_is_idempotent(self):
        cursor=FakeCursor([{"id":1,"email":"new-admin@example.invalid",
                           "global_role":"superadmin","active":1}])
        output=self.run_with_cursor(cursor)
        self.assertIn("SUPERADMIN_ALREADY_READY",output)
        self.assertNotIn("TEMPORARY_PASSWORD=",output)
        self.assertFalse(any(sql.startswith("UPDATE users SET") for sql,args in cursor.queries))

    def test_missing_authorization_rejected(self):
        with self.assertRaises(RuntimeError):
            self.run_with_cursor(FakeCursor(),allow="0")

    def test_multiple_admins_rejected(self):
        with self.assertRaises(ValueError):
            self.run_with_cursor(FakeCursor([{"id":1,"email":"a","global_role":"admin","active":1},
                                             {"id":2,"email":"b","global_role":"admin","active":1}]))


if __name__=="__main__":
    unittest.main()
