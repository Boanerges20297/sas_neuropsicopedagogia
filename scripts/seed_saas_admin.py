"""One-time safe bootstrap of existing local admin into MySQL SaaS.

Does not remove or change the original SQLite account. Password hash remains
hashed; MySQL application user performs only DML. Idempotent by email.
"""
import sqlite3
from pathlib import Path
from uuid import uuid4
import os
import pymysql
from dotenv import load_dotenv

load_dotenv()
root=Path(__file__).resolve().parents[1]
db=root/(os.getenv("DATABASE_NAME") or "app_database.db")
sqlite=sqlite3.connect(f"file:{db}?mode=ro",uri=True)
sqlite.row_factory=sqlite3.Row
try:
    admins=sqlite.execute(
        "SELECT id,nome,email,senha_hash,role,must_change_password FROM users WHERE role='admin'"
    ).fetchall()
finally:
    sqlite.close()
if len(admins)!=1:
    raise SystemExit(f"BOOTSTRAP_ABORTED: expected one local admin, found {len(admins)}")
admin=dict(admins[0])
if not admin["senha_hash"].startswith(("$2a$","$2b$","$2y$")):
    raise SystemExit("BOOTSTRAP_ABORTED: unexpected bcrypt hash")
import sys
sys.path.insert(0, str(root))
from saas_store import transaction
with transaction() as cur:
    cur.execute("SELECT id,global_role FROM users WHERE email=%s FOR UPDATE",(admin["email"],))
    existing=cur.fetchone()
    if existing:
        if existing["global_role"] not in ("admin","superadmin"):
            raise SystemExit("BOOTSTRAP_ABORTED: existing identity with non-admin role")
        user_id=existing["id"]
    else:
        cur.execute(
            """INSERT INTO users(nome,email,password_hash,global_role,active,must_change_password)
               VALUES(%s,%s,%s,'admin',1,%s)""",
            (admin["nome"],admin["email"],admin["senha_hash"],int(admin["must_change_password"])))
        user_id=cur.lastrowid
    cur.execute("SELECT id FROM tenants WHERE owner_user_id=%s LIMIT 1",(user_id,))
    existing_tenant=cur.fetchone()
    if existing_tenant:
        tenant_id=existing_tenant["id"]
    else:
        cur.execute(
            "INSERT INTO tenants(nome,slug,owner_user_id,status) VALUES(%s,%s,%s,'active')",
            (admin["nome"],"prof-"+uuid4().hex,user_id))
        tenant_id=cur.lastrowid
    cur.execute(
        """INSERT INTO tenant_members(tenant_id,user_id,membership_role,status)
           VALUES(%s,%s,'owner','active')
           ON DUPLICATE KEY UPDATE status='active'""",(tenant_id,user_id))
    cur.execute(
        """INSERT INTO professional_profiles(user_id,profession,verification_status)
           VALUES(%s,'neuropsicopedagogo','verified')
           ON DUPLICATE KEY UPDATE user_id=VALUES(user_id)""",(user_id,))
    cur.execute(
        """INSERT INTO audit_events(actor_id,tenant_id,action,resource_type,resource_id,outcome,access_reason)
           VALUES(%s,%s,'admin_saas_bootstrap','tenant',%s,'allowed','migrate existing admin hash without plaintext')""",
        (user_id,tenant_id,tenant_id))
print("SAAS_ADMIN_READY | tenant provisioned | original SQLite admin preserved")
