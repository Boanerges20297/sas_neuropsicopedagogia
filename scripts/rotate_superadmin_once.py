"""Authorized one-time migration of the existing SaaS administrator to superadmin.

Inputs are environment variables containing the target email and a bcrypt hash.
Neither plaintext passwords nor hashes are written to Git or terminal output.
"""
import os
import re
from saas_store import transaction

mail = os.getenv("SAAS_SUPERADMIN_EMAIL", "").strip().lower()
digest = os.getenv("SAAS_SUPERADMIN_HASH", "")
if os.getenv("SAAS_ADMIN_ROTATE_APPROVED") != "1":
    raise SystemExit("Missing explicit approval")
if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", mail):
    raise SystemExit("Invalid email")
if not re.fullmatch(r"\$2[aby]\$1[012]\$[./0-9A-Za-z]{53}", digest):
    raise SystemExit("Invalid bcrypt hash")

with transaction() as cursor:
    cursor.execute("SELECT id,active FROM users WHERE global_role IN ('admin','superadmin') FOR UPDATE")
    admins = cursor.fetchall()
    if len(admins) != 1 or not admins[0]["active"]:
        raise SystemExit("Expected exactly one active administrator")
    uid = admins[0]["id"]
    cursor.execute("SELECT id FROM users WHERE email=%s FOR UPDATE", (mail,))
    existing = cursor.fetchone()
    if existing and existing["id"] != uid:
        raise SystemExit("Email owned by another account")
    cursor.execute("SELECT COUNT(*) n FROM tenant_members m JOIN tenants t ON m.tenant_id=t.id "
                   "WHERE m.user_id=%s AND m.status='active' AND t.status='active'", (uid,))
    if not cursor.fetchone()["n"]:
        raise SystemExit("No active administrative tenant")
    cursor.execute("UPDATE users SET email=%s,password_hash=%s,global_role='superadmin',"
                   "active=1,must_change_password=1 WHERE id=%s", (mail, digest, uid))
    cursor.execute("INSERT INTO audit_events(actor_id,tenant_id,action,resource_type,resource_id,outcome,access_reason) "
                   "VALUES(%s,NULL,'superadmin_credentials_rotated','user',%s,'allowed','Owner-authorized credential rotation')",
                   (uid, uid))
print("SUPERADMIN_ROTATED | old account preserved | bcrypt stored | password change flagged")
