"""MySQL data boundary for Neuro-Diagnosis SaaS.

All clinical data is tied to a tenant. No SQLite fallback for SaaS requests.
The application account only needs SELECT/INSERT/UPDATE/DELETE.
"""
from contextlib import contextmanager
from datetime import datetime
from uuid import uuid4
import os
import re

import pymysql
from flask_login import UserMixin

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def connect():
    names = ("MYSQL_HOST", "MYSQL_PORT", "MYSQL_DATABASE", "MYSQL_USER", "MYSQL_PASSWORD")
    if any(not os.getenv(n) for n in names):
        raise RuntimeError("Configuração MySQL SaaS incompleta")
    return pymysql.connect(
        host=os.environ["MYSQL_HOST"], port=int(os.environ["MYSQL_PORT"]),
        database=os.environ["MYSQL_DATABASE"], user=os.environ["MYSQL_USER"],
        password=os.environ["MYSQL_PASSWORD"], charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor, autocommit=False,
        connect_timeout=5, read_timeout=10, write_timeout=10)


@contextmanager
def transaction():
    connection = connect()
    try:
        with connection.cursor() as cur:
            yield cur
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def one(sql, args=()):
    with transaction() as cur:
        cur.execute(sql, args)
        return cur.fetchone()


def all_rows(sql, args=()):
    with transaction() as cur:
        cur.execute(sql, args)
        return cur.fetchall()


class SaaSUser(UserMixin):
    def __init__(self, row):
        self.id = row["id"]
        self.nome = row["nome"]
        self.email = row["email"]
        self.role = row["global_role"]
        self.active = bool(row["active"])
        self.must_change_password = bool(row["must_change_password"])

    @property
    def is_active(self):
        return self.active

    def get_id(self):
        return "saas:" + str(self.id)

    def is_admin(self):
        return self.role in ("admin", "superadmin")

    def is_practitioner(self):
        return self.role in ("admin", "superadmin", "professional")


def get_user(user_id):
    try:
        uid = int(user_id)
    except (ValueError, TypeError):
        return None
    row = one(
        "SELECT id,nome,email,global_role,active,must_change_password FROM users WHERE id=%s",
        (uid,))
    return SaaSUser(row) if row and row["active"] else None


def user_by_email(email):
    return one("SELECT * FROM users WHERE email=%s", (email.strip().lower(),))


def audit(cur, actor, tenant_id, action, resource_type, resource_id, outcome="allowed", reason=None):
    cur.execute(
        """INSERT INTO audit_events (actor_id,tenant_id,action,resource_type,resource_id,access_reason,outcome)
           VALUES (%s,%s,%s,%s,%s,%s,%s)""",
        (actor, tenant_id, action, resource_type, resource_id, reason, outcome))


def register_professional(nome, email, password_hash, profession, registry_code=""):
    name = (nome or "").strip()
    mail = (email or "").strip().lower()
    if not name or len(name)>160 or len(mail)>254 or not EMAIL_RE.fullmatch(mail):
        raise ValueError("Nome ou e-mail inválido")
    if profession not in ("psicologo", "neuropsicopedagogo", "outro"):
        raise ValueError("Profissão inválida")
    with transaction() as cur:
        cur.execute(
            """INSERT INTO users (nome,email,password_hash,global_role,active,must_change_password)
               VALUES (%s,%s,%s,'professional',0,0)""",
            (name, mail, password_hash))
        user_id = cur.lastrowid
        cur.execute(
            """INSERT INTO professional_profiles(user_id,profession,registry_code,verification_status)
               VALUES(%s,%s,%s,'pending')""",
            (user_id, profession, (registry_code or "").strip()[:100] or None))
        slug = "prof-" + uuid4().hex
        cur.execute(
            """INSERT INTO tenants(nome,slug,owner_user_id,status)
               VALUES(%s,%s,%s,'pending')""", (name, slug, user_id))
        tenant_id = cur.lastrowid
        cur.execute(
            """INSERT INTO tenant_members(tenant_id,user_id,membership_role,status)
               VALUES(%s,%s,'owner','pending')""", (tenant_id, user_id))
        audit(cur,user_id,tenant_id,"professional_registered","user",user_id)
        return user_id


def pending_professionals():
    return all_rows(
        """SELECT u.id,u.nome,u.email,u.created_at,p.profession,p.registry_code,
                  p.verification_status,t.id AS tenant_id,t.status AS tenant_status
           FROM users u JOIN professional_profiles p ON p.user_id=u.id
           JOIN tenants t ON t.owner_user_id=u.id
           WHERE u.global_role='professional' AND u.active=0
           ORDER BY u.created_at DESC""")


def list_professionals():
    return all_rows(
        """SELECT u.id,u.nome,u.email,u.active,p.profession,t.id tenant_id,t.status tenant_status
           FROM users u JOIN professional_profiles p ON p.user_id=u.id
           JOIN tenants t ON t.owner_user_id=u.id WHERE u.global_role='professional'
           ORDER BY u.created_at DESC""")


def approve_professional(actor_id, target_id, reason, approve=True):
    if not reason or len(reason.strip())<5:
        raise ValueError("Informe a justificativa da decisão")
    with transaction() as cur:
        cur.execute("SELECT global_role FROM users WHERE id=%s AND active=1", (actor_id,))
        admin = cur.fetchone()
        if not admin or admin["global_role"] not in ("admin","superadmin"):
            raise PermissionError("Permissão administrativa exigida")
        cur.execute(
            """SELECT u.id,u.active,t.id tenant_id,t.status,p.verification_status
               FROM users u JOIN tenants t ON t.owner_user_id=u.id
               JOIN professional_profiles p ON p.user_id=u.id
               WHERE u.id=%s AND u.global_role='professional' FOR UPDATE""", (target_id,))
        target=cur.fetchone()
        if not target or target["active"] or target["status"]!="pending":
            raise ValueError("Solicitação não está pendente")
        cur.execute(
            "UPDATE users SET active=%s WHERE id=%s", (1 if approve else 0,target_id))
        cur.execute(
            "UPDATE tenants SET status=%s WHERE id=%s",
            ("active" if approve else "suspended",target["tenant_id"]))
        cur.execute(
            "UPDATE tenant_members SET status=%s WHERE tenant_id=%s AND user_id=%s",
            ("active" if approve else "suspended",target["tenant_id"],target_id))
        if approve:
            cur.execute(
                "UPDATE professional_profiles SET verification_status='verified',verified_at=NOW(),verified_by=%s WHERE user_id=%s",
                (actor_id,target_id))
        else:
            cur.execute(
                "UPDATE professional_profiles SET verification_status='rejected',verified_at=NOW(),verified_by=%s WHERE user_id=%s",
                (actor_id,target_id))
        audit(cur,actor_id,target["tenant_id"],
              "professional_approved" if approve else "professional_rejected",
              "user",target_id,reason=reason.strip())


def own_tenant(user_id):
    return one(
        """SELECT t.id,t.nome,t.slug,t.status FROM tenants t
           JOIN tenant_members m ON m.tenant_id=t.id
           WHERE m.user_id=%s AND m.status='active' AND t.status='active'
           ORDER BY (m.membership_role='owner') DESC,t.id LIMIT 1""",
        (user_id,))


def list_clients(user_id, tenant_id):
    # Never derive scope from an untrusted request param without membership check.
    return all_rows(
        """SELECT c.id,c.nome,c.email,c.birth_date,c.status,c.created_at
           FROM clients c JOIN tenant_members m ON m.tenant_id=c.tenant_id
           WHERE m.user_id=%s AND m.status='active' AND c.tenant_id=%s
             AND c.professional_user_id=%s ORDER BY c.created_at DESC""",
        (user_id,tenant_id,user_id))


def create_client(user_id, tenant_id, nome, email=None):
    name=(nome or "").strip()
    if not name or len(name)>180:
        raise ValueError("Nome do paciente inválido")
    with transaction() as cur:
        cur.execute(
            """SELECT 1 FROM tenant_members m JOIN tenants t ON t.id=m.tenant_id
               WHERE m.tenant_id=%s AND m.user_id=%s
                 AND m.status='active' AND t.status='active'
                 AND m.membership_role IN ('owner','professional')""",
            (tenant_id,user_id))
        if not cur.fetchone():
            raise PermissionError("Você não pertence a este espaço profissional")
        cur.execute(
            "INSERT INTO clients(tenant_id,professional_user_id,nome,email) VALUES(%s,%s,%s,%s)",
            (tenant_id,user_id,name,(email or "").strip()[:254] or None))
        cid=cur.lastrowid
        audit(cur,user_id,tenant_id,"client_create","client",cid)
        return cid


def list_visible_tests(user_id,tenant_id):
    return all_rows(
        """SELECT t.id,t.title,t.description,t.visibility,t.status,t.tenant_id
           FROM tests t
           WHERE t.active=1 AND t.status='approved'
             AND ((t.visibility='global' AND t.tenant_id IS NULL)
               OR (t.visibility='private' AND t.tenant_id=%s))
           ORDER BY t.title""",
        (tenant_id,))


def admin_global_stats():
    return one(
        """SELECT (SELECT COUNT(*) FROM users WHERE global_role='professional') AS professionals,
                  (SELECT COUNT(*) FROM users WHERE global_role='professional' AND active=0) AS pending,
                  (SELECT COUNT(*) FROM tenants WHERE status='active') AS active_tenants,
                  (SELECT COUNT(*) FROM clients) AS total_clients""")
