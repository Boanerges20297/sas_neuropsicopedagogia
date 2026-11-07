"""Audited administrative account creation with role and capability restrictions.

Global administrator rights never convey clinical access to other clinicians'
patient data. All new accounts must change the temporary password at login.
"""
from uuid import uuid4

import saas_store as store
from saas_account_access import FEATURES, actor_can_grant, can_admin
from saas_profile_data import LEGACY_AREA, validate_details

ACCOUNT_ROLES = frozenset(("patient", "professional", "admin", "superadmin"))
ADMIN_ROLES = frozenset(("admin", "superadmin"))


def _identity(nome, email):
    name = (nome or "").strip()
    mail = (email or "").strip().lower()
    if not 1 <= len(name) <= 160 or len(mail) > 254 or not store.EMAIL_RE.fullmatch(mail):
        raise ValueError("Informe nome e e-mail válidos")
    return name, mail


def create_managed_account(actor_id, *, nome, email, role, password_hash,
                           clinical_workspace=False, cpf="", profession="",
                           birth_date="", phone="", allow_accounts=False,
                           allow_professionals=False, allow_activations=False):
    """Create an account, optional private clinical tenant and initial rights.

    The target has role-based privileges plus explicit limits for new admins.
    Existing administrators without rights rows retain their old permissions.
    An inactive patient/guardian account gets no portal rights until verified.
    """
    if type(actor_id) is not int or actor_id <= 0:
        raise PermissionError("Operador inválido")
    if role not in ACCOUNT_ROLES:
        raise ValueError("Perfil de acesso inválido")
    if not isinstance(password_hash, str) or not 20 <= len(password_hash) <= 255:
        raise ValueError("Hash de credencial inválido")
    name, mail = _identity(nome, email)

    admin_flags = {
        "accounts": bool(allow_accounts),
        "professionals": bool(allow_professionals),
        "activations": bool(allow_activations),
        "clinic": bool(clinical_workspace),
    }
    if role not in ADMIN_ROLES and any(
            (admin_flags["accounts"], admin_flags["professionals"],
             admin_flags["activations"])):
        raise ValueError("Permissões administrativas exigem perfil administrador")
    if role == "patient" and clinical_workspace:
        raise ValueError("Conta de paciente não possui espaço clínico")

    clinical = role == "professional" or bool(clinical_workspace)
    details = validate_details(cpf, profession, birth_date, phone) if clinical else None

    with store.transaction() as cur:
        cur.execute(
            "SELECT id,global_role,active FROM users WHERE id=%s FOR UPDATE",
            (actor_id,),
        )
        operator = cur.fetchone()
        if not operator or not operator["active"] or operator["global_role"] not in ADMIN_ROLES:
            raise PermissionError("Somente administração ativa pode criar contas")
        if role == "superadmin" and operator["global_role"] != "superadmin":
            raise PermissionError("Somente superadmin pode atribuir esse perfil")
        if not actor_can_grant(cur, operator, {"accounts": True}):
            raise PermissionError("Operador sem permissão para criar contas")
        if role == "admin" and not actor_can_grant(cur, operator, admin_flags):
            raise PermissionError("Não é permitido conceder poderes acima dos seus")

        cur.execute(
            """INSERT INTO users(nome,email,password_hash,global_role,active,must_change_password)
               VALUES(%s,%s,%s,%s,%s,1)""",
            (name, mail, password_hash, role, int(role != "patient")),
        )
        new_id = cur.lastrowid
        # First access requires a verified authenticator for every new account.
        cur.execute(
            "INSERT INTO saas_mfa_factors(user_id,required) VALUES(%s,1)",
            (new_id,))
        tenant_id = None

        if role == "patient":
            cur.execute(
                """INSERT INTO care_portal_login_requests(user_id,status)
                   VALUES(%s,'pending')""", (new_id,))
        elif role == "admin":
            # New admin with no checked capability remains scoped down.
            cur.execute(
                """INSERT INTO saas_account_rights
                   (user_id,allow_accounts,allow_professionals,
                    allow_activations,allow_clinic,created_by)
                   VALUES(%s,%s,%s,%s,%s,%s)""",
                (new_id, int(admin_flags["accounts"]),
                 int(admin_flags["professionals"]),
                 int(admin_flags["activations"]),
                 int(admin_flags["clinic"]), actor_id),
            )

        if clinical:
            cur.execute(
                """INSERT INTO professional_profiles
                   (user_id,profession,verification_status,verified_by,verified_at)
                   VALUES(%s,%s,'verified',%s,UTC_TIMESTAMP())""",
                (new_id, LEGACY_AREA[details["practice_area"]], actor_id),
            )
            cur.execute(
                """INSERT INTO professional_details
                   (user_id,cpf_digest,cpf_encrypted,practice_area,birth_date,phone)
                   VALUES(%s,%s,%s,%s,%s,%s)""",
                (new_id, details["cpf_digest"], details["cpf_encrypted"],
                 details["practice_area"], details["birth_date"], details["phone"]),
            )
            slug = ("prof-" + uuid4().hex if role == "professional"
                    else "admin-clinic-" + str(new_id))
            cur.execute(
                """INSERT INTO tenants(nome,slug,owner_user_id,status)
                   VALUES(%s,%s,%s,'active')""",
                (("Espaço clínico de " + name)[:180], slug, new_id),
            )
            tenant_id = cur.lastrowid
            cur.execute(
                """INSERT INTO tenant_members
                   (tenant_id,user_id,membership_role,status)
                   VALUES(%s,%s,'owner','active')""", (tenant_id, new_id),
            )

        # Audit rights, not passwords or health data.
        rights_summary = "".join(k[0] for k in FEATURES if admin_flags[k])
        store.audit(cur, actor_id, tenant_id, "admin_account_created",
                    "user", new_id,
                    reason="role=" + role + ";rights=" + rights_summary)
        return new_id


def list_managed_accounts(actor_id):
    """Only account metadata; no passwords or clinical records."""
    if not can_admin(actor_id, "accounts"):
        raise PermissionError("Gerenciamento de contas não autorizado")
    return store.all_rows(
        """SELECT u.id,u.nome,u.email,u.global_role,u.active,
                  u.must_change_password,u.created_at,
                  EXISTS(SELECT 1 FROM tenants t
                         JOIN tenant_members m ON m.tenant_id=t.id
                          AND m.user_id=u.id AND m.membership_role='owner'
                         WHERE t.owner_user_id=u.id AND t.status='active'
                           AND m.status='active') AS clinical_workspace
           FROM users u
           ORDER BY u.created_at DESC,u.id DESC LIMIT 100"""
    )
