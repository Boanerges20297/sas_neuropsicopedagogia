"""Guardian portal admission policy — deny-by-default regression contracts."""
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

import saas_portal_policy as gate

ROOT = Path(__file__).resolve().parents[1]


class PortalPolicyTests(TestCase):
    def test_all_unapproved_or_invalid_inputs_are_denied_before_query(self):
        with patch.object(gate.store, "one") as lookup:
            for args in (
                (104, 201, 301, "private_notes"),
                (104, 201, 301, "diagnosis"),
                (104, 201, 301, ""),
                (0, 201, 301, "appointments"),
                (104, -1, 301, "appointments"),
                ("104", 201, 301, "appointments"),
                (True, 201, 301, "appointments"),
                (104, 201, None, "appointments"),
            ):
                with self.subTest(args=args):
                    self.assertFalse(gate.can_access(*args))
            lookup.assert_not_called()

    def test_without_explicit_permission_no_read(self):
        with patch.object(gate.store, "one", return_value=None) as lookup:
            self.assertFalse(gate.can_access(104, 201, 301, "appointments"))
            sql, args = lookup.call_args.args
            self.assertEqual(args, (104, 201, 301, "appointments"))
            for check in (
                "g.status='active'",
                "g.expires_at > UTC_TIMESTAMP()",
                "g.authorized_by=g.professional_user_id",
                "i.verification_status='verified'",
                "c.verification_status='verified'",
                "c.contact_role='legal_guardian'",
                "m.status='active'",
                "t.status='active'",
                "u.active=1",
                "u.global_role='patient'",
                "p.professional_user_id=g.professional_user_id",
            ):
                self.assertIn(check, sql)

    def test_only_database_admission_can_allow(self):
        with patch.object(gate.store, "one", return_value={"allowed": 1}) as lookup:
            self.assertTrue(gate.can_access(104, 201, 301, "released_documents"))
            self.assertEqual(lookup.call_args.args[1][-1], "released_documents")

    def test_schema_enforces_identity_and_grant_scope(self):
        schema = (ROOT / "scripts/mysql_care_portal_access_migration.sql").read_text(
            encoding="utf-8")
        for part in (
            "CREATE TABLE IF NOT EXISTS care_portal_identity_links",
            "CREATE TABLE IF NOT EXISTS care_portal_grants",
            "uq_portal_link_all_scope",
            "uq_portal_grant_scope",
            "FOREIGN KEY (contact_id,tenant_id,client_id,professional_user_id)",
            "FOREIGN KEY (identity_link_id,tenant_id,client_id,professional_user_id,user_id)",
            "verification_status ENUM('pending','verified','revoked') NOT NULL DEFAULT 'pending'",
            "status ENUM('pending','active','revoked') NOT NULL DEFAULT 'pending'",
            "CONSTRAINT chk_portal_active",
            "CONSTRAINT chk_portal_verified",
        ):
            self.assertIn(part, schema)
        self.assertNotIn("DROP TABLE", schema)

    def test_no_portal_routes_and_deploy_migration_order(self):
        # A future portal is not equivalent to public access to clinical data.
        from app import app
        self.assertFalse(any(rule.rule.startswith("/saas/portal")
                             for rule in app.url_map.iter_rules()))
        docker = (ROOT / "Dockerfile").read_text(encoding="utf-8")
        self.assertIn("saas_portal_policy.py", docker)
        deploy = (ROOT / "infra/host/deploy-neuro-diagnosis-saas.sh").read_text(
            encoding="utf-8")
        backup = deploy.index("NEURO_BACKUP_INVALID")
        care = deploy.index("mysql_care_workflow_migration.sql")
        portal = deploy.index("mysql_care_portal_access_migration.sql")
        web = deploy.index('docker compose -f "$COMPOSE" up -d web', portal)
        self.assertLess(backup, care)
        self.assertLess(care, portal)
        self.assertLess(portal, web)

    def test_mysql_homologation_harness_requires_disposable_unique_schema(self):
        code = (ROOT / "scripts/homologate_mysql_care.py").read_text(
            encoding="utf-8")
        self.assertIn('"neuro_hml_" + secrets.token_hex(6)', code)
        self.assertIn('if created:', code)
        self.assertIn('mysql("DROP DATABASE " + db + ";")', code)
        self.assertIn('PORTAL_POLICY_HOMOLOGATION_OK', code)
