"""Run once for a superadmin bootstrap; never store plaintext secrets in source."""
import os
import secrets
from uuid import uuid4
from saas_store import transaction


def provision():
    email=os.environ.get("SAAS_SUPERADMIN_EMAIL","").strip().lower()
    if os.environ.get("SAAS_SUPERADMIN_PROVISION_APPROVED")!="1":
        raise RuntimeError("Authorization required")
    if not email or "@" not in email or len(email)>254:
        raise ValueError("Invalid admin email")
    from app import bcrypt
    temporary=secrets.token_urlsafe(24)
    hashed=bcrypt.generate_password_hash(temporary).decode()
    with transaction() as cur:
        cur.execute("SELECT id, email, global_role, active FROM users WHERE global_role IN ('admin','superadmin') FOR UPDATE")
        admins=cur.fetchall()
        if len(admins)>1:
            raise ValueError("Unexpected number of administrators")
        cur.execute("SELECT id FROM users WHERE email=%s FOR UPDATE",(email,))
        other=cur.fetchone()
        if other and (not admins or other["id"]!=admins[0]["id"]):
            raise ValueError("Email already exists")
        if admins:
            admin=admins[0]
            if not admin["active"]:
                raise ValueError("Administrator inactive")
            if admin["global_role"]=="superadmin" and admin["email"]==email:
                print("SUPERADMIN_ALREADY_READY")
                return
            uid=admin["id"]
            cur.execute("UPDATE users SET email=%s,password_hash=%s,global_role='superadmin',active=1,must_change_password=1 WHERE id=%s",(email,hashed,uid))
        else:
            cur.execute("INSERT INTO users(nome,email,password_hash,global_role,active,must_change_password) VALUES('Superadmin',%s,%s,'superadmin',1,1)",(email,hashed))
            uid=cur.lastrowid
        cur.execute("SELECT id FROM tenants WHERE owner_user_id=%s ORDER BY id LIMIT 1",(uid,))
        own=cur.fetchone()
        if own:
            tid=own["id"]
            cur.execute("UPDATE tenants SET status='active' WHERE id=%s",(tid,))
        else:
            cur.execute("INSERT INTO tenants(nome,slug,owner_user_id,status) VALUES('Administração',%s,%s,'active')",("admin-"+uuid4().hex,uid))
            tid=cur.lastrowid
        cur.execute("INSERT INTO tenant_members(tenant_id,user_id,membership_role,status) VALUES(%s,%s,'owner','active') ON DUPLICATE KEY UPDATE membership_role='owner',status='active'",(tid,uid))
        cur.execute("INSERT INTO professional_profiles(user_id,profession,verification_status,verified_at) VALUES(%s,'neuropsicopedagogo','verified',NOW()) ON DUPLICATE KEY UPDATE verification_status='verified'",(uid,))
        cur.execute("INSERT INTO audit_events(actor_id,tenant_id,action,resource_type,resource_id,outcome,access_reason) VALUES(%s,%s,'superadmin_bootstrap','user',%s,'allowed','Authorized initial access')",(uid,tid,uid))
    print("SUPERADMIN_PROVISIONED",email)
    print("TEMPORARY_PASSWORD="+temporary)
    print("CHANGE_PASSWORD_REQUIRED")

if __name__=="__main__":
    provision()
