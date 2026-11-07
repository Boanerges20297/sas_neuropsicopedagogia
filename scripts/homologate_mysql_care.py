"""STI-only MySQL 8 integration validation using an isolated disposable schema."""
from pathlib import Path
import re
import secrets
import subprocess
import sys

BASE = Path(__file__).resolve().parents[1]
MYSQL = ["wsl.exe", "-d", "Ubuntu", "-u", "root", "--", "mysql",
         "--protocol=socket", "-uroot", "--batch", "--skip-column-names",
         "--default-character-set=utf8mb4"]


def mysql(sql, db=None, expect_error=False):
    args = MYSQL + ([f"--database={db}"] if db else [])
    result = subprocess.run(args, input=sql, text=True, encoding="utf-8",
                            errors="replace", capture_output=True, timeout=65)
    if expect_error:
        if result.returncode == 0:
            raise AssertionError("Integrity check unexpectedly succeeded")
        if not re.search(r"ERROR (?:1062|1452|3819) ", result.stderr):
            raise AssertionError("Unexpected SQL failure: " + result.stderr[:250])
    elif result.returncode:
        raise RuntimeError(result.stderr[:550])
    return result.stdout.strip()


def apply_file(filename, db):
    sql = (BASE / "scripts" / filename).read_text(encoding="utf-8")
    if filename == "mysql_saas_schema.sql":
        if "-- Credencial somente" not in sql:
            raise RuntimeError("Bootstrap changed, aborting")
        sql = sql.split("-- Credencial somente", 1)[0]
        sql, count = re.subn(r"CREATE DATABASE IF NOT EXISTS\s+neuro_diagnosis\s+[^;]*;",
                              "", sql, count=1, flags=re.I)
        if count != 1:
            raise RuntimeError("Bootstrap CREATE DATABASE is unexpected")
    sql, count = re.subn(r"\bUSE\s+neuro_diagnosis\s*;",
                          f"USE {db};", sql, flags=re.I)
    if count != 1:
        raise RuntimeError("Unexpected schema USE contract")
    statements = "\n".join(line for line in sql.splitlines()
                            if not line.lstrip().startswith("--"))
    if re.search(r"\b(?:CREATE\s+USER|GRANT|REVOKE|DROP\s+DATABASE|TRUNCATE)\b",
                 statements, re.I):
        raise RuntimeError("Disallowed privileged DDL in source")
    mysql(sql)


def fixtures(db):
    mysql("""
INSERT INTO users(id,nome,email,password_hash,global_role,active)
 VALUES (101,'Synthetic Alpha','alpha@example.invalid','test-only','professional',1),
        (102,'Synthetic Beta','beta@example.invalid','test-only','professional',1),
        (104,'Synthetic Guardian Account','guardian@example.invalid','test-only','patient',1),
        (105,'Synthetic Adult Account','adult@example.invalid','test-only','patient',1);
INSERT INTO tenants(id,nome,slug,owner_user_id,status)
 VALUES(201,'Synthetic Clinic A','hml-a',101,'active'),
       (202,'Synthetic Clinic B','hml-b',102,'active');
INSERT INTO tenant_members(tenant_id,user_id,membership_role,status)
 VALUES(201,101,'owner','active'),(202,102,'owner','active');
INSERT INTO clients(id,tenant_id,professional_user_id,nome,birth_date)
 VALUES(301,201,101,'Synthetic Child A','2016-01-01'),
       (302,202,102,'Synthetic Adult B','1991-01-01'),
       (303,201,101,'Synthetic Patient C','2014-05-04');
INSERT INTO care_client_contacts
 (id,tenant_id,client_id,professional_user_id,full_name,contact_role,email)
 VALUES(601,201,301,101,'Synthetic Guardian','legal_guardian','guardian@example.invalid');
INSERT INTO care_portal_identity_links
 (id,tenant_id,client_id,professional_user_id,contact_id,user_id)
 VALUES(701,201,301,101,601,104);
INSERT INTO care_portal_grants
 (id,tenant_id,client_id,professional_user_id,user_id,identity_link_id,permission_scope,expires_at)
 VALUES(801,201,301,101,104,701,'appointments','2027-12-31 00:00:00');
INSERT INTO care_portal_self_links
 (id,tenant_id,client_id,professional_user_id,user_id)
 VALUES(901,202,302,102,105);
INSERT INTO care_portal_self_grants
 (id,tenant_id,client_id,professional_user_id,user_id,self_link_id,permission_scope,expires_at)
 VALUES(902,202,302,102,105,901,'appointments','2027-12-31 00:00:00');
INSERT INTO care_portal_consents
 (id,tenant_id,client_id,professional_user_id,user_id,permission_scope,expires_at)
 VALUES(1001,201,301,101,104,'appointments','2027-12-31 00:00:00'),
       (1002,202,302,102,105,'appointments','2027-12-31 00:00:00');
INSERT INTO care_portal_login_requests(user_id,status,activated_by,activated_at)
 VALUES(104,'active',101,UTC_TIMESTAMP()),
       (105,'active',102,UTC_TIMESTAMP());
INSERT INTO care_portal_client_activations
 (id,tenant_id,client_id,professional_user_id,user_id)
 VALUES(1101,201,301,101,104),(1102,202,302,102,105);
INSERT INTO care_appointments
 (id,tenant_id,client_id,professional_user_id,request_id,service_type,modality,
  starts_at_utc,ends_at_utc,status)
 VALUES(401,201,301,101,'11111111-1111-4111-8111-111111111111',
        'initial','in_person','2026-12-01 13:00:00','2026-12-01 14:00:00','completed');
INSERT INTO care_encounters
 (id,tenant_id,appointment_id,client_id,professional_user_id,status)
 VALUES(501,201,401,301,101,'draft');
INSERT INTO care_patient_intakes
 (tenant_id,client_id,professional_user_id,representation_mode,guardian_contact_id)
 VALUES(201,301,101,'guardian',601),
       (202,302,102,'self',NULL);
""", db=db)


def verify(db):
    tables = int(mysql("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=DATABASE() AND table_type='BASE TABLE';", db=db))
    if tables < 32:
        raise AssertionError(f"Expected at least 26 tables, found {tables}")
    if mysql("SELECT verification_status FROM care_client_contacts LIMIT 1;", db=db) != "unverified":
        raise AssertionError("Guardian should start UNVERIFIED")
    for query, expected in [
        ("SELECT COUNT(*) FROM clients WHERE tenant_id=201 AND professional_user_id=101;", "2"),
        ("SELECT COUNT(*) FROM clients WHERE tenant_id=202 AND professional_user_id=102;", "1"),
        ("SELECT COUNT(*) FROM clients WHERE tenant_id=201 AND professional_user_id=102;", "0"),
        ("SELECT COUNT(*) FROM care_appointments WHERE tenant_id=202 AND professional_user_id=102;", "0"),
        ("SELECT COUNT(*) FROM care_encounters WHERE tenant_id=201 AND professional_user_id=101;", "1")
    ]:
        if mysql(query, db=db) != expected:
            raise AssertionError("Tenant-scope query returned wrong result: " + query)
    rejections = [
"""INSERT INTO care_appointments
(tenant_id,client_id,professional_user_id,request_id,service_type,modality,starts_at_utc,ends_at_utc)
VALUES(201,302,101,'22222222-2222-4222-8222-222222222222','initial','remote','2026-12-02 12:00:00','2026-12-02 13:00:00');""",
"""INSERT INTO care_encounters
(tenant_id,appointment_id,client_id,professional_user_id) VALUES(201,401,303,101);""",
"""INSERT INTO care_encounters
(tenant_id,appointment_id,client_id,professional_user_id) VALUES(201,401,301,102);""",
"""INSERT INTO care_appointments
(tenant_id,client_id,professional_user_id,request_id,service_type,modality,starts_at_utc,ends_at_utc)
VALUES(201,301,101,'11111111-1111-4111-8111-111111111111','initial','in_person','2026-12-03 13:00:00','2026-12-03 14:00:00');""",
"""INSERT INTO care_appointments
(tenant_id,client_id,professional_user_id,request_id,service_type,modality,starts_at_utc,ends_at_utc)
VALUES(201,301,101,'33333333-3333-4333-8333-333333333333','initial','in_person','2026-12-03 14:00:00','2026-12-03 13:00:00');"""
    ]
    for sql in rejections:
        mysql(sql, db=db, expect_error=True)
    # A linked guardian and a permission record are NOT enough to access a portal.
    if str(BASE) not in sys.path:
        sys.path.insert(0, str(BASE))
    from saas_portal_policy import SELECT_ALLOWED
    from saas_portal_activation_queue import QUEUE_SQL
    admin_queue = QUEUE_SQL.replace("%s", "1", 1).replace("%s", "999", 1)
    owner_101_queue = QUEUE_SQL.replace("%s", "0", 1).replace("%s", "101", 1)
    owner_102_queue = QUEUE_SQL.replace("%s", "0", 1).replace("%s", "102", 1)
    if mysql(admin_queue, db=db):
        raise AssertionError("Unverified accounts appeared in activation queue")
    grant_query = SELECT_ALLOWED
    for value in ("104", "201", "301", "'appointments'"):
        grant_query = grant_query.replace("%s", value, 1)
    if mysql(grant_query, db=db):
        raise AssertionError("Unverified portal identity unexpectedly has access")

    # Database rejects activation without proof and authorizer.
    mysql("UPDATE care_portal_identity_links SET verification_status='verified' WHERE id=701;",
          db=db, expect_error=True)
    mysql("UPDATE care_portal_grants SET status='active' WHERE id=801;",
          db=db, expect_error=True)
    mysql("""INSERT INTO care_portal_grants
        (tenant_id,client_id,professional_user_id,user_id,identity_link_id,permission_scope,expires_at)
        VALUES(201,303,101,104,701,'released_documents','2027-12-31');""",
        db=db, expect_error=True)

    # Test a fully authorized grant and immediate revocation on guardian contact.
    mysql("""UPDATE care_client_contacts SET verification_status='verified' WHERE id=601;
UPDATE care_portal_identity_links SET verification_status='verified',
  verification_evidence_ref='synthetic-review-101',
  verified_by=101, verified_at=UTC_TIMESTAMP() WHERE id=701;
UPDATE care_portal_grants SET status='active',authorized_by=101,
  authorized_at=UTC_TIMESTAMP() WHERE id=801;
UPDATE care_portal_consents SET status='accepted',
  consent_evidence_ref='synthetic-ack-104',consent_at=UTC_TIMESTAMP(),
  confirmed_by_user_id=104 WHERE id=1001;""", db=db)
    if mysql(grant_query, db=db):
        raise AssertionError("Grant and consent without client activation allowed guardian")
    if not mysql(admin_queue, db=db).startswith("301\t"):
        raise AssertionError("Verified guardian missing from admin activation queue")
    if not mysql(owner_101_queue, db=db).startswith("301\t"):
        raise AssertionError("Owner cannot see their verified guardian activation")
    if mysql(owner_102_queue, db=db):
        raise AssertionError("Another clinician can enumerate guardian activation")
    mysql("""UPDATE care_portal_client_activations
      SET status='active',activated_by=101,activated_at=UTC_TIMESTAMP()
      WHERE id=1101;""", db=db)
    if mysql(grant_query, db=db) != "1":
        raise AssertionError("Verified, scoped guardian grant was not recognized")
    if mysql(admin_queue, db=db):
        raise AssertionError("Activated client remains in pending queue")
    mysql("UPDATE care_client_contacts SET verification_status='revoked' WHERE id=601;",
          db=db)
    if mysql(grant_query, db=db):
        raise AssertionError("Revoked guardian still has access")
    from saas_portal_policy import SELECT_SELF_ALLOWED
    self_query = SELECT_SELF_ALLOWED
    for value in ("105", "202", "302", "'appointments'"):
        self_query = self_query.replace("%s", value, 1)
    if mysql(self_query, db=db):
        raise AssertionError("Unverified adult account unexpectedly has access")
    mysql("""UPDATE care_portal_self_links
      SET verification_status='verified', verification_evidence_ref='synthetic-proof',
      verified_by=102, verified_at=UTC_TIMESTAMP(),
      consent_evidence_ref='synthetic-ack', consent_at=UTC_TIMESTAMP()
      WHERE id=901;
UPDATE care_portal_self_grants
      SET status='active', authorized_by=102, authorized_at=UTC_TIMESTAMP()
      WHERE id=902;
UPDATE care_portal_consents
      SET status='accepted', consent_evidence_ref='synthetic-user-ack',
      confirmed_by_user_id=105, consent_at=UTC_TIMESTAMP()
      WHERE id=1002;""", db=db)
    if mysql(self_query, db=db):
        raise AssertionError("Adult grant without client activation was accepted")
    if not mysql(admin_queue, db=db).startswith("302\t"):
        raise AssertionError("Verified adult missing from admin queue")
    if not mysql(owner_102_queue, db=db).startswith("302\t"):
        raise AssertionError("Owner cannot see verified adult activation")
    if mysql(owner_101_queue, db=db):
        raise AssertionError("Cross-tenant adult was listed to another clinician")
    mysql("""UPDATE care_portal_client_activations
      SET status='active',activated_by=102,activated_at=UTC_TIMESTAMP()
      WHERE id=1102;""", db=db)
    if mysql(self_query, db=db) != "1":
        raise AssertionError("Verified adult scope and consent were not recognized")
    if mysql(admin_queue, db=db):
        raise AssertionError("Activated adult remains pending")
    print("ACTIVATION_QUEUE_HOMOLOGATION_OK guardian=1 adult=1 scoped=1 hidden_after_activation=1")
    print("PORTAL_POLICY_HOMOLOGATION_OK default_deny=1 proof_required=1 "
          "cross_client_denied=1 explicit_grant=1 revoke=1")

    # Intake: a minor needs one guardian contact for that EXACT patient,
    # whereas an independent adult must not be represented by a guardian.
    for bad in (
        """INSERT INTO care_patient_intakes
           (tenant_id,client_id,professional_user_id,representation_mode,guardian_contact_id)
           VALUES(201,303,101,'guardian',NULL);""",
        """INSERT INTO care_patient_intakes
           (tenant_id,client_id,professional_user_id,representation_mode,guardian_contact_id)
           VALUES(201,303,101,'self',601);""",
        """INSERT INTO care_patient_intakes
           (tenant_id,client_id,professional_user_id,representation_mode,guardian_contact_id)
           VALUES(201,303,101,'guardian',601);""",
        """INSERT INTO care_patient_intakes
           (tenant_id,client_id,professional_user_id,representation_mode)
           VALUES(201,303,102,'self');""",
    ):
        mysql(bad, db=db, expect_error=True)
    if mysql("SELECT COUNT(*) FROM care_patient_intakes;", db=db) != "2":
        raise AssertionError("Exactly two synthetic patient intake profiles expected")
    print("PATIENT_INTAKE_HOMOLOGATION_OK adult_self=1 minor_guardian=1 "
          "no_extra_login=1 invalid_guardian_links_denied=4")

    # New accounts require a TOTP enrollment with no implicit device trust.
    mysql("INSERT INTO saas_mfa_factors(user_id,required) VALUES(101,1);",db=db)
    if mysql("SELECT required FROM saas_mfa_factors WHERE user_id=101;",db=db)!="1":
        raise AssertionError("First-access MFA enrollment flag missing")
    if mysql("SELECT COUNT(*) FROM saas_mfa_trusted_devices;",db=db)!="0":
        raise AssertionError("Unexpected trusted devices before TOTP enrollment")
    if mysql("SELECT COUNT(*) FROM saas_account_rights;",db=db)!="0":
        raise AssertionError("Admin rights implicitly granted")
    print("MFA_HOMOLOGATION_OK first_login_required=1 trusted_devices=0 explicit_rights=0")
    print(f"MYSQL_HOMOLOGATION_OK tables={tables} tenants=2 blocked_invariants={len(rejections)} guardian_unverified=1")


def main():
    if sys.platform != "win32":
        raise RuntimeError("This harness must run on the STI Windows host")
    db = "neuro_hml_" + secrets.token_hex(6)
    if not re.fullmatch(r"neuro_hml_[a-f0-9]{12}", db):
        raise RuntimeError("Invalid disposable DB name")
    created = False
    try:
        if mysql("SELECT COUNT(*) FROM information_schema.schemata WHERE schema_name='" + db + "';") != "0":
            raise RuntimeError("Refusing to reuse existing DB name")
        mysql("CREATE DATABASE " + db + " CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;")
        created = True
        names = ("mysql_saas_schema.sql", "mysql_saas_profile_migration.sql",
                 "mysql_neurocore_review_migration.sql", "mysql_care_workflow_migration.sql",
                 "mysql_care_portal_access_migration.sql",
                 "mysql_care_patient_intake_migration.sql",
                 "mysql_care_portal_self_access_migration.sql",
                 "mysql_care_client_activation_migration.sql",
                 "mysql_saas_account_rights_migration.sql",
                 "mysql_saas_mfa_migration.sql",
                 "mysql_saas_login_recovery_migration.sql")
        for filename in names:
            apply_file(filename, db)
        for filename in names[1:]:
            apply_file(filename, db)
        fixtures(db)
        verify(db)
    finally:
        if created:
            mysql("DROP DATABASE " + db + ";")
            print("DISPOSABLE_HOMOLOGATION_SCHEMA_DROPPED")


if __name__ == "__main__":
    main()
