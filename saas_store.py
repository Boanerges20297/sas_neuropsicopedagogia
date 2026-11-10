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
        self.mfa_required = self.is_admin() or bool(row.get("mfa_required", False))
        self.mfa_enabled = bool(row.get("mfa_enabled", False))
        self.admin_rights = (
            {feature: bool(row.get("allow_" + feature, False))
             for feature in ("accounts", "professionals", "activations", "clinic")}
            if row.get("rights_id") is not None else None)

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
        """SELECT u.id,u.nome,u.email,u.global_role,u.active,u.must_change_password,
                  COALESCE(f.required,0) AS mfa_required,
                  (f.enabled_at IS NOT NULL) AS mfa_enabled,
                  r.user_id AS rights_id,r.allow_accounts,r.allow_professionals,
                  r.allow_activations,r.allow_clinic,
                  EXISTS(SELECT 1 FROM saas_email_verifications v
                     WHERE v.user_id=u.id AND v.required=1 AND v.verified_at IS NULL)
                     AS email_verification_pending
           FROM users u
           LEFT JOIN saas_mfa_factors f ON f.user_id=u.id
           LEFT JOIN saas_account_rights r ON r.user_id=u.id WHERE u.id=%s""",
        (uid,))
    return SaaSUser(row) if row and row["active"] and not row["email_verification_pending"] else None


def user_by_email(email):
    return one(
        """SELECT u.*,COALESCE(f.required,0) AS mfa_required,
                  (f.enabled_at IS NOT NULL) AS mfa_enabled,
                  r.user_id AS rights_id,r.allow_accounts,r.allow_professionals,
                  r.allow_activations,r.allow_clinic,
                  EXISTS(SELECT 1 FROM saas_email_verifications v
                    WHERE v.user_id=u.id AND v.required=1 AND v.verified_at IS NULL)
                    AS email_verification_pending
           FROM users u
           LEFT JOIN saas_mfa_factors f ON f.user_id=u.id
           LEFT JOIN saas_account_rights r ON r.user_id=u.id WHERE u.email=%s""",
        (email.strip().lower(),))


def audit(cur, actor, tenant_id, action, resource_type, resource_id, outcome="allowed", reason=None):
    cur.execute(
        """INSERT INTO audit_events (actor_id,tenant_id,action,resource_type,resource_id,access_reason,outcome)
           VALUES (%s,%s,%s,%s,%s,%s,%s)""",
        (actor, tenant_id, action, resource_type, resource_id, reason, outcome))


def register_professional(nome, email, password_hash, profession, registry_code="",
                          cpf="", birth_date="", phone=""):
    from saas_profile_data import LEGACY_AREA, validate_details
    name = (nome or "").strip()
    mail = (email or "").strip().lower()
    if not name or len(name)>160 or len(mail)>254 or not EMAIL_RE.fullmatch(mail):
        raise ValueError("Nome ou e-mail inválido")
    details = validate_details(cpf, profession, birth_date, phone)
    with transaction() as cur:
        cur.execute(
            """INSERT INTO users (nome,email,password_hash,global_role,active,must_change_password)
               VALUES (%s,%s,%s,'professional',0,0)""",
            (name, mail, password_hash))
        user_id = cur.lastrowid
        # Registration cannot become an authenticated identity without mailbox proof.
        from saas_email_verification import enrollment_required
        enrollment_required(cur,user_id)
        # Require choice and confirmation of a TOTP authenticator at first access.
        cur.execute(
            "INSERT INTO saas_mfa_factors(user_id,required) VALUES(%s,1)",
            (user_id,))
        cur.execute(
            """INSERT INTO professional_profiles(user_id,profession,registry_code,verification_status)
               VALUES(%s,%s,%s,'pending')""",
            (user_id, LEGACY_AREA[profession], (registry_code or "").strip()[:100] or None))
        cur.execute(
            """INSERT INTO professional_details
               (user_id,cpf_digest,cpf_encrypted,practice_area,birth_date,phone)
               VALUES(%s,%s,%s,%s,%s,%s)""",
            (user_id, details["cpf_digest"], details["cpf_encrypted"],
             details["practice_area"], details["birth_date"], details["phone"]))
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
    """List own patients; a today's schedule is only a correlated summary."""
    from datetime import timedelta, timezone
    from zoneinfo import ZoneInfo
    zone = ZoneInfo("America/Fortaleza")
    midnight = datetime.now(zone).replace(hour=0, minute=0, second=0, microsecond=0)
    start = midnight.astimezone(timezone.utc).replace(tzinfo=None)
    end = (midnight + timedelta(days=1)).astimezone(timezone.utc).replace(tzinfo=None)
    rows = all_rows(
        """SELECT c.id,c.nome,c.email,c.birth_date,c.status,c.created_at,
                  (SELECT pr.status FROM care_portal_access_requests pr
                    WHERE pr.tenant_id=c.tenant_id AND pr.client_id=c.id
                      AND pr.professional_user_id=c.professional_user_id
                    LIMIT 1) AS portal_request_status,
                  (SELECT MIN(a.starts_at_utc)
                     FROM care_appointments a
                    WHERE a.tenant_id=c.tenant_id
                      AND a.client_id=c.id
                      AND a.professional_user_id=c.professional_user_id
                      AND a.status IN ('scheduled','confirmed')
                      AND a.starts_at_utc >= %s AND a.starts_at_utc < %s
                  ) AS today_time_utc
           FROM clients c JOIN tenant_members m ON m.tenant_id=c.tenant_id
           WHERE m.user_id=%s AND m.status='active' AND c.tenant_id=%s
             AND c.professional_user_id=%s ORDER BY c.created_at DESC""",
        (start, end, user_id, tenant_id, user_id))
    for row in rows:
        appt = row.get("today_time_utc")
        row["today_at"] = (appt.replace(tzinfo=timezone.utc).astimezone(zone).strftime("%H:%M")
                           if appt else None)
        row.pop("today_time_utc", None)
    return rows


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
    # Verify membership here as well as at the route boundary. Otherwise a
    # future caller could pass an arbitrary tenant_id and read private tests.
    return all_rows(
        """SELECT t.id,t.title,t.description,t.visibility,t.status,t.tenant_id
           FROM tests t
           WHERE t.active=1 AND t.status='approved'
             AND ((t.visibility='global' AND t.tenant_id IS NULL)
               OR (t.visibility='private' AND t.tenant_id=%s))
             AND EXISTS (
                 SELECT 1 FROM tenant_members m
                 JOIN tenants tenant ON tenant.id=m.tenant_id
                 WHERE m.tenant_id=%s AND m.user_id=%s
                   AND m.status='active' AND tenant.status='active'
             )
           ORDER BY t.title""",
        (tenant_id,tenant_id,user_id))


def get_account_profile(user_id):
    from saas_profile_data import masked_cpf, phone_display
    profile = one(
        """SELECT u.id,u.nome,u.email,u.global_role,u.must_change_password,
                  d.practice_area,d.birth_date,d.phone,d.cpf_encrypted,
                  EXISTS(SELECT 1 FROM saas_email_verifications v
                    WHERE v.user_id=u.id AND v.verified_at IS NOT NULL)
                    AS email_verified,
                  EXISTS(SELECT 1 FROM saas_email_verifications v
                    WHERE v.user_id=u.id AND v.required=1 AND v.verified_at IS NULL)
                    AS email_pending
           FROM users u LEFT JOIN professional_details d ON d.user_id=u.id
           WHERE u.id=%s AND u.active=1""", (user_id,))
    if not profile:
        raise ValueError("Conta não encontrada")
    profile["cpf_masked"] = masked_cpf(profile.pop("cpf_encrypted"))
    profile["phone_display"] = phone_display(profile.get("phone"))
    return profile


def update_account_profile(user_id, nome, email, *, cpf="", practice_area="",
                           birth_date="", phone=""):
    from saas_profile_data import LEGACY_AREA, validate_details
    name = (nome or "").strip()
    mail = (email or "").strip().lower()
    if not name or len(name)>160 or len(mail)>254 or not EMAIL_RE.fullmatch(mail):
        raise ValueError("Nome ou e-mail inválido")
    with transaction() as cur:
        cur.execute("SELECT id,global_role,email FROM users WHERE id=%s AND active=1 FOR UPDATE",
                    (user_id,))
        user = cur.fetchone()
        if not user:
            raise PermissionError("Conta inativa")
        if mail != user["email"].strip().lower():
            raise ValueError("A troca de e-mail exige codigo de verificacao; use a secao E-mail")
        cur.execute("SELECT 1 FROM professional_details WHERE user_id=%s FOR UPDATE",
                    (user_id,))
        has_details = bool(cur.fetchone())
        # The personal profile is independent of professional registration.
        # Validate clinical fields only when that separate section is submitted.
        requested = any((cpf, practice_area, birth_date, phone))
        if requested:
            if not all((practice_area, birth_date, phone)) or (not has_details and not cpf):
                raise ValueError("Preencha todos os dados profissionais")
            from saas_profile_data import validate_area, validate_birth_date, validate_phone, prepare_cpf
            practice_area = validate_area(practice_area)
            birth = validate_birth_date(birth_date)
            telephone = validate_phone(phone)
            if cpf:
                digest, encrypted = prepare_cpf(cpf)
                cur.execute(
                    "SELECT user_id FROM professional_details "
                    "WHERE cpf_digest=%s AND user_id<>%s FOR UPDATE",
                    (digest,user_id))
                if cur.fetchone():
                    raise ValueError("CPF já cadastrado")
                if has_details:
                    cur.execute(
                        """UPDATE professional_details SET cpf_digest=%s,
                           cpf_encrypted=%s,practice_area=%s,birth_date=%s,phone=%s
                           WHERE user_id=%s""",
                        (digest,encrypted,practice_area,birth,telephone,user_id))
                else:
                    cur.execute(
                        """INSERT INTO professional_details
                           (user_id,cpf_digest,cpf_encrypted,practice_area,birth_date,phone)
                           VALUES (%s,%s,%s,%s,%s,%s)""",
                        (user_id,digest,encrypted,practice_area,birth,telephone))
            else:
                cur.execute(
                    """UPDATE professional_details SET practice_area=%s,
                       birth_date=%s,phone=%s WHERE user_id=%s""",
                    (practice_area,birth,telephone,user_id))
            cur.execute("UPDATE professional_profiles SET profession=%s WHERE user_id=%s",
                        (LEGACY_AREA[practice_area],user_id))
        cur.execute("UPDATE users SET nome=%s,email=%s WHERE id=%s",
                    (name,mail,user_id))
        audit(cur,user_id,None,"account_profile_updated","user",user_id)


def change_account_password(user_id, new_hash):
    with transaction() as cur:
        cur.execute("SELECT id FROM users WHERE id=%s AND active=1 FOR UPDATE", (user_id,))
        if not cur.fetchone():
            raise PermissionError("Conta inativa")
        cur.execute(
            "UPDATE users SET password_hash=%s,must_change_password=0 WHERE id=%s",
            (new_hash,user_id))
        # Changing credentials invalidates device trust on every other browser.
        cur.execute(
            """UPDATE saas_mfa_trusted_devices SET revoked_at=UTC_TIMESTAMP()
               WHERE user_id=%s AND revoked_at IS NULL""", (user_id,))
        audit(cur,user_id,None,"account_password_changed","user",user_id)


def admin_global_stats():
    return one(
        """SELECT (SELECT COUNT(*) FROM users WHERE global_role='professional') AS professionals,
                  (SELECT COUNT(*) FROM users WHERE global_role='professional' AND active=0) AS pending,
                  (SELECT COUNT(*) FROM tenants WHERE status='active') AS active_tenants,
                  (SELECT COUNT(*) FROM clients) AS total_clients""")
