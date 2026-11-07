"""Patient / guardian portal authorization — strict deny-by-default contracts."""
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

import saas_portal_policy as gate

ROOT = Path(__file__).resolve().parents[1]


class PortalPolicyTests(TestCase):
    def test_invalid_inputs_fail_before_database(self):
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

    def test_absent_grants_deny_both_modes(self):
        with patch.object(gate.store, "one", return_value=None) as lookup:
            self.assertFalse(gate.can_access(104, 201, 301, "appointments"))
            self.assertEqual(lookup.call_count, 2)
            self.assertEqual(lookup.call_args_list[0].args[1],
                             (104, 201, 301, "appointments"))
            self.assertEqual(lookup.call_args_list[1].args[1],
                             (104, 201, 301, "appointments"))

    def test_guardian_requires_minor_independent_proof_consent_grant(self):
        sql = gate.SELECT_ALLOWED
        for required in (
            "g.status='active'", "g.expires_at > UTC_TIMESTAMP()",
            "g.authorized_by=g.professional_user_id",
            "i.verification_status='verified'",
            "i.verified_by=i.professional_user_id",
            "c.verification_status='verified'",
            "c.contact_role='legal_guardian'",
            "intake.representation_mode='guardian'",
            "intake.guardian_contact_id=c.id",
            "p.birth_date > DATE_SUB(",
            "v.status='accepted'",
            "v.confirmed_by_user_id=g.user_id",
            "m.status='active'", "t.status='active'",
            "u.active=1", "u.global_role='patient'",
            "p.professional_user_id=g.professional_user_id",
        ):
            self.assertIn(required, sql)

    def test_adult_requires_self_record_consent_and_no_guardian(self):
        sql = gate.SELECT_SELF_ALLOWED
        for required in (
            "g.status='active'", "g.expires_at > UTC_TIMESTAMP()",
            "g.authorized_by=g.professional_user_id",
            "i.verification_status='verified'",
            "i.verified_by=i.professional_user_id",
            "i.consent_evidence_ref IS NOT NULL",
            "intake.representation_mode='self'",
            "intake.guardian_contact_id IS NULL",
            "p.birth_date <= DATE_SUB(",
            "v.status='accepted'",
            "v.confirmed_by_user_id=g.user_id",
            "m.status='active'", "t.status='active'",
            "u.global_role='patient'",
        ):
            self.assertIn(required, sql)

    def test_only_authorized_database_admission_returns_true(self):
        with patch.object(gate.store, "one", return_value={"allowed": 1}) as lookup:
            self.assertTrue(gate.can_access(104, 201, 301, "appointments"))
            lookup.assert_called_once()
        with patch.object(gate.store, "one", side_effect=[None, {"allowed": 1}]) as lookup:
            self.assertTrue(gate.can_access(105, 202, 302, "released_documents"))
            self.assertEqual(lookup.call_count, 2)

    def test_schema_enforces_guardian_and_adult_scoped_grants(self):
        guardian = (ROOT / "scripts/mysql_care_portal_access_migration.sql").read_text(
            encoding="utf-8")
        for required in (
            "CREATE TABLE IF NOT EXISTS care_portal_identity_links",
            "CREATE TABLE IF NOT EXISTS care_portal_grants",
            "uq_portal_link_all_scope", "uq_portal_grant_scope",
            "FOREIGN KEY (contact_id,tenant_id,client_id,professional_user_id)",
            "FOREIGN KEY (identity_link_id,tenant_id,client_id,professional_user_id,user_id)",
            "verification_status ENUM('pending','verified','revoked') NOT NULL DEFAULT 'pending'",
            "status ENUM('pending','active','revoked') NOT NULL DEFAULT 'pending'",
            "CONSTRAINT chk_portal_active", "CONSTRAINT chk_portal_verified",
        ):
            self.assertIn(required, guardian)
        self.assertNotIn("DROP TABLE", guardian)
        adult = (ROOT / "scripts/mysql_care_portal_self_access_migration.sql").read_text(
            encoding="utf-8")
        for required in (
            "CREATE TABLE IF NOT EXISTS care_portal_self_links",
            "CREATE TABLE IF NOT EXISTS care_portal_self_grants",
            "CREATE TABLE IF NOT EXISTS care_portal_consents",
            "uq_self_patient", "uq_self_link_full_scope",
            "uq_self_grant_scope", "uq_portal_consent_scope",
            "CONSTRAINT chk_self_verified", "CONSTRAINT chk_self_grant_active",
            "CONSTRAINT chk_portal_consent_accepted",
            "FOREIGN KEY (self_link_id,tenant_id,client_id,professional_user_id,user_id)",
        ):
            self.assertIn(required, adult)
        self.assertNotIn("DROP TABLE", adult)
        self.assertNotIn("CREATE USER", adult)

    def test_no_public_portal_and_safe_deploy_order(self):
        from app import app
        self.assertFalse(any(rule.rule.startswith("/saas/portal")
                             for rule in app.url_map.iter_rules()))
        docker = (ROOT / "Dockerfile").read_text(encoding="utf-8")
        self.assertIn("saas_portal_policy.py", docker)
        self.assertIn("saas_portal_activation.py", docker)
        self.assertIn("saas_portal_activation_routes.py", docker)
        self.assertIn("saas_portal_activation_queue.py", docker)
        deploy = (ROOT / "infra/host/deploy-neuro-diagnosis-saas.sh").read_text(
            encoding="utf-8")
        backup = deploy.index("NEURO_BACKUP_INVALID")
        care = deploy.index("mysql_care_workflow_migration.sql")
        guardian = deploy.index("mysql_care_portal_access_migration.sql")
        intake = deploy.index("mysql_care_patient_intake_migration.sql")
        adult = deploy.index("mysql_care_portal_self_access_migration.sql")
        web = deploy.index('docker compose -f "$COMPOSE" up -d web', adult)
        self.assertLess(backup, care)
        self.assertLess(care, guardian)
        self.assertLess(guardian, intake)
        self.assertLess(intake, adult)
        self.assertLess(adult, web)

    def test_disposable_mysql_harness(self):
        code = (ROOT / "scripts/homologate_mysql_care.py").read_text(
            encoding="utf-8")
        self.assertIn('"neuro_hml_" + secrets.token_hex(6)', code)
        self.assertIn("if created:", code)
        self.assertIn('mysql("DROP DATABASE " + db + ";")', code)
        self.assertIn("PORTAL_POLICY_HOMOLOGATION_OK", code)
        self.assertIn("mysql_care_portal_self_access_migration.sql", code)
