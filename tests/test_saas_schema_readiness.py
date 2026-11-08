"""Production readiness contract: a missing login/email table is NOT healthy."""
import unittest
from unittest.mock import patch

from app import app
import pymysql
import saas_store as store


class EmailSchemaReadinessTests(unittest.TestCase):
    def setUp(self):
        self.old_testing = app.config["TESTING"]
        app.config["TESTING"] = True
        self.client = app.test_client()

    def tearDown(self):
        app.config["TESTING"] = self.old_testing

    def test_missing_email_verification_table_is_503(self):
        queries = []
        def query(sql, *args, **kwargs):
            queries.append(sql)
            if "FROM saas_email_verifications" in sql:
                raise pymysql.err.ProgrammingError(
                    1146, "Table 'neuro_diagnosis.saas_email_verifications' doesn't exist")
            return {"ok": 1}
        with patch.object(store, "one", side_effect=query):
            response = self.client.get("/saas/saude")
        self.assertEqual(response.status_code, 503)
        self.assertIn(b"not_ready", response.data)
        self.assertTrue(any("saas_email_verifications" in sql for sql in queries))

    def test_missing_email_challenge_table_is_503(self):
        def query(sql, *args, **kwargs):
            if "FROM saas_email_challenges" in sql:
                raise pymysql.err.ProgrammingError(
                    1146, "Table 'neuro_diagnosis.saas_email_challenges' doesn't exist")
            return {"ok": 1}
        with patch.object(store, "one", side_effect=query):
            response = self.client.get("/saas/saude")
        self.assertEqual(response.status_code, 503)
        self.assertIn(b"not_ready", response.data)

    def test_health_checks_both_tables_before_reporting_ready(self):
        queries = []
        def query(sql, *args, **kwargs):
            queries.append(sql)
            return {"ok": 1}
        with patch.object(store, "one", side_effect=query):
            response = self.client.get("/saas/saude")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'"status":"ready"', response.data)
        self.assertTrue(any("saas_email_verifications" in sql for sql in queries))
        self.assertTrue(any("saas_email_challenges" in sql for sql in queries))


if __name__ == "__main__":
    unittest.main()
