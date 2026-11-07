"""Portal account activation: professional owns clients; admin/superadmin any client.

This is an administrative release of an existing patient login *for one client*.
It never creates a minor's login, never approves identity documents and never
releases clinical notes, assessments or unapproved documents.
"""
from datetime import date
import saas_store as store
from saas_patient_intake import age_years


def _positive_int(value):
    return type(value) is int and value > 0


def activate_client_account(actor_id, client_id, principal_user_id):
    """Activate one verified patient/account link, with audit in one transaction.

    Raises PermissionError when the operator has no rights to the client,
    ValueError when identity/guardian proof is incomplete, or identifiers invalid.
    Returns True on a new per-client activation, False if already active.
    """
    if not all(_positive_int(v) for v in
               (actor_id, client_id, principal_user_id)):
        raise ValueError("Identificadores invalidos")

    with store.transaction() as cur:
        cur.execute(
            "SELECT id,global_role,active FROM users WHERE id=%s FOR UPDATE",
            (actor_id,))
        actor = cur.fetchone()
        if not actor or not actor["active"] or actor["global_role"] not in (
                "professional", "admin", "superadmin"):
            raise PermissionError("Ativacao exige profissional ou administrador")

        cur.execute(
            """SELECT p.id,p.tenant_id,p.professional_user_id,p.birth_date,
                      p.status,t.status AS tenant_status,
                      m.status AS professional_membership,
                      m.membership_role
               FROM clients p
               JOIN tenants t ON t.id=p.tenant_id
               JOIN tenant_members m ON m.tenant_id=p.tenant_id
                 AND m.user_id=p.professional_user_id
               WHERE p.id=%s FOR UPDATE""",
            (client_id,))
        patient = cur.fetchone()
        if not patient or patient["status"] != "active" or (
                patient["tenant_status"] != "active"
                or patient["professional_membership"] != "active"
                or patient["membership_role"] not in ("owner", "professional")):
            raise PermissionError("Paciente ou espaco indisponivel")
        if (actor["global_role"] == "professional"
                and patient["professional_user_id"] != actor_id):
            raise PermissionError("Profissional so libera seus pacientes")

        cur.execute(
            "SELECT id,global_role,active FROM users WHERE id=%s FOR UPDATE",
            (principal_user_id,))
        login = cur.fetchone()
        if not login or login["global_role"] != "patient":
            raise ValueError("A ativacao so permite contas de pacientes ou responsaveis")

        cur.execute(
            """SELECT user_id,status FROM care_portal_login_requests
               WHERE user_id=%s FOR UPDATE""", (principal_user_id,))
        login_request = cur.fetchone()
        if not login_request or login_request["status"] == "suspended":
            raise ValueError("Conta nao elegivel para ativacao")
        if login_request["status"] == "pending" and login["active"]:
            raise ValueError("Estado da conta inconsistente; exige revisao")
        if login_request["status"] == "active" and not login["active"]:
            raise ValueError("Conta suspensa ou desativada; exige revisao")

        cur.execute(
            """SELECT representation_mode,guardian_contact_id
               FROM care_patient_intakes
               WHERE tenant_id=%s AND client_id=%s AND professional_user_id=%s
               FOR UPDATE""",
            (patient["tenant_id"], client_id, patient["professional_user_id"]))
        intake = cur.fetchone()
        if not intake or not isinstance(patient["birth_date"], date):
            raise ValueError("Cadastro do paciente precisa ser validado")
        age = age_years(patient["birth_date"])
        mode = intake["representation_mode"]
        args = (patient["tenant_id"], client_id,
                patient["professional_user_id"], principal_user_id)
        if mode == "self" and age >= 18 and not intake["guardian_contact_id"]:
            cur.execute(
                """SELECT id FROM care_portal_self_links
                   WHERE tenant_id=%s AND client_id=%s
                     AND professional_user_id=%s AND user_id=%s
                     AND verification_status='verified'
                     AND verified_by=professional_user_id
                     AND verified_at IS NOT NULL
                     AND verification_evidence_ref IS NOT NULL
                     AND verification_evidence_ref<>''
                     AND consent_evidence_ref IS NOT NULL
                     AND consent_evidence_ref<>''
                     AND consent_at IS NOT NULL FOR UPDATE""", args)
        elif mode == "guardian" and age < 18 and age >= 0 and intake["guardian_contact_id"]:
            cur.execute(
                """SELECT i.id FROM care_portal_identity_links i
                   JOIN care_client_contacts c
                     ON c.id=i.contact_id AND c.tenant_id=i.tenant_id
                    AND c.client_id=i.client_id
                    AND c.professional_user_id=i.professional_user_id
                   WHERE i.tenant_id=%s AND i.client_id=%s
                     AND i.professional_user_id=%s AND i.user_id=%s
                     AND i.contact_id=%s
                     AND i.verification_status='verified'
                     AND i.verified_by=i.professional_user_id
                     AND i.verified_at IS NOT NULL
                     AND i.verification_evidence_ref IS NOT NULL
                     AND i.verification_evidence_ref<>''
                     AND c.contact_role='legal_guardian'
                     AND c.verification_status='verified' FOR UPDATE""",
                args + (intake["guardian_contact_id"],))
        else:
            raise ValueError("Representacao ou maioridade exige revisao")
        if not cur.fetchone():
            raise ValueError("Comprove o vinculo ou identidade antes de ativar")

        cur.execute(
            """SELECT id,status FROM care_portal_client_activations
               WHERE tenant_id=%s AND client_id=%s AND user_id=%s FOR UPDATE""",
            (patient["tenant_id"], client_id, principal_user_id))
        existing = cur.fetchone()
        if existing and existing["status"] == "revoked":
            raise ValueError("Vinculo revogado exige nova revisao")
        if existing and existing["status"] == "active":
            return False
        if existing:
            cur.execute(
                """UPDATE care_portal_client_activations
                   SET status='active',activated_by=%s,
                       activated_at=UTC_TIMESTAMP(),revoked_at=NULL
                   WHERE id=%s""",
                (actor_id, existing["id"]))
        else:
            cur.execute(
                """INSERT INTO care_portal_client_activations
                   (tenant_id,client_id,professional_user_id,user_id,
                    status,activated_by,activated_at)
                   VALUES (%s,%s,%s,%s,'active',%s,UTC_TIMESTAMP())""",
                args + (actor_id,))
        # One adult / guardian login can serve multiple children. Activate the
        # login once; clinical grants and activation remain isolated by child.
        if login_request["status"] == "pending":
            cur.execute(
                """UPDATE care_portal_login_requests
                   SET status='active',activated_by=%s,
                       activated_at=UTC_TIMESTAMP()
                   WHERE user_id=%s AND status='pending'""",
                (actor_id, principal_user_id))
            cur.execute(
                """UPDATE users SET active=1
                   WHERE id=%s AND global_role='patient' AND active=0""",
                (principal_user_id,))
        store.audit(cur, actor_id, patient["tenant_id"],
                    "portal_client_account_activated", "client", client_id)
        return True
