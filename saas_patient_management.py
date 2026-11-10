"""Private patient lifecycle: alta, encerramento e reativacao, sem apagar prontuarios.

The client owner is ALWAYS the authenticated professional's own tenant member.
Existing schema states: active=em acompanhamento, inactive=alta,
archived=encerrado. No patient or medical record DELETE.
"""
from datetime import date

import saas_store as store

STATES = {"active": "Em acompanhamento", "inactive": "Alta",
          "archived": "Encerrado"}
ACTIONS = {
    "active": {"alta": "inactive", "encerrar": "archived"},
    "inactive": {"reativar": "active", "encerrar": "archived"},
    "archived": {"reativar": "active"},
}


def _lock_own_client(cur, uid, tenant_id, client_id):
    cur.execute(
        """SELECT c.id,c.nome,c.birth_date,c.email,c.status
           FROM clients c
           JOIN tenant_members m ON m.tenant_id=c.tenant_id
           JOIN tenants t ON t.id=c.tenant_id
           WHERE c.id=%s AND c.tenant_id=%s
             AND c.professional_user_id=%s AND m.user_id=%s
             AND m.status='active'
             AND m.membership_role IN ('owner','professional')
             AND t.status='active' FOR UPDATE""",
        (client_id, tenant_id, uid, uid),
    )
    result = cur.fetchone()
    if not result:
        raise PermissionError("Paciente não pertence a este espaço clínico")
    return result


def own_client(uid, tenant_id, client_id):
    return store.one(
        """SELECT c.id,c.nome,c.birth_date,c.email,c.status
           FROM clients c JOIN tenant_members m ON m.tenant_id=c.tenant_id
           JOIN tenants t ON t.id=c.tenant_id
           WHERE c.id=%s AND c.tenant_id=%s AND c.professional_user_id=%s
             AND m.user_id=%s AND m.status='active'
             AND m.membership_role IN ('owner','professional')
             AND t.status='active' LIMIT 1""",
        (client_id, tenant_id, uid, uid),
    )


def change_status(uid, tenant_id, client_id, action):
    with store.transaction() as cur:
        patient = _lock_own_client(cur, uid, tenant_id, client_id)
        next_status = ACTIONS.get(patient["status"], {}).get(action)
        if not next_status:
            raise ValueError("Esta alteração não é permitida para a situação atual")
        cur.execute(
            """UPDATE clients SET status=%s WHERE id=%s AND tenant_id=%s
               AND professional_user_id=%s AND status=%s""",
            (next_status, client_id, tenant_id, uid, patient["status"]),
        )
        store.audit(cur, uid, tenant_id, "patient_status_changed", "client",
                    client_id, reason=patient["status"] + "->" + next_status)
    return next_status


def update_identity(uid, tenant_id, client_id, *, name, birth_date):
    name = (name or "").strip()
    if not name or len(name) > 180:
        raise ValueError("Informe o nome completo do paciente")
    try:
        parsed = date.fromisoformat(birth_date)
    except (TypeError, ValueError) as exc:
        raise ValueError("Informe uma data de nascimento válida") from exc
    from saas_patient_intake import age_years
    if not 0 <= age_years(parsed) <= 120:
        raise ValueError("Data de nascimento fora do intervalo permitido")
    with store.transaction() as cur:
        old = _lock_own_client(cur, uid, tenant_id, client_id)
        # Intake classification cannot silently change from minor to adult.
        cur.execute(
            """SELECT representation_mode FROM care_patient_intakes
               WHERE tenant_id=%s AND client_id=%s
                 AND professional_user_id=%s""",
            (tenant_id, client_id, uid),
        )
        intake = cur.fetchone()
        if intake:
            if intake["representation_mode"] == "guardian" and age_years(parsed) >= 18:
                raise ValueError("Paciente menor: revise a representação legal antes de alterar a idade")
            if intake["representation_mode"] == "self" and age_years(parsed) < 18:
                raise ValueError("Paciente adulto: revise a representação legal antes de alterar a idade")
        cur.execute(
            """UPDATE clients SET nome=%s,birth_date=%s WHERE id=%s
               AND tenant_id=%s AND professional_user_id=%s""",
            (name, parsed, client_id, tenant_id, uid),
        )
        store.audit(cur, uid, tenant_id, "patient_identity_updated", "client",
                    client_id, reason="demographic_fields")
    return client_id
