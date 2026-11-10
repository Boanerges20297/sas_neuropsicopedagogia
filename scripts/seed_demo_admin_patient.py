"""One-time, idempotent synthetic patient for the sole active SaaS administrator.

Opt-in CLI only. Never runs on app startup, migration or public HTTP routes.
No real names, mailboxes, credentials, CPF or live guardian accounts are created.
Usage inside the deployed web container:
  python scripts/seed_demo_admin_patient.py --dry-run
  python scripts/seed_demo_admin_patient.py --apply
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import saas_store as store
import saas_patient_intake as intake
import saas_account_access as access
import saas_admin_workspace as workspace

DEMO_NAME = "PACIENTE FICTICIO - TESTE NEURO-DIAGNOSIS"
DEMO_BIRTH = "2016-08-18"
DEMO_GUARDIAN = "RESPONSAVEL FICTICIO - NAO E PESSOA REAL"
DEMO_REPORT = (
    "CASO TOTALMENTE FICTICIO PARA VALIDACAO DO SISTEMA. "
    "Relato ilustrativo de dificuldade de manter atencao durante tarefas, "
    "agitacao em sala e sensibilidade a alguns sons. "
    "Nao representa pessoa real, teste clinico validado ou diagnostico."
)


class SeedRefused(ValueError):
    pass


def select_admin(admin_id=None):
    """Never guess among multiple administrators or use the superadmin."""
    rows = store.all_rows(
        """SELECT id FROM users WHERE global_role='admin' AND active=1
           ORDER BY id"""
    )
    if admin_id is not None:
        rows = [row for row in rows if row["id"] == admin_id]
    if len(rows) != 1:
        raise SeedRefused(
            "Esperado exatamente um administrador ativo. "
            "Use --admin-id para selecionar explicitamente quando necessario."
        )
    uid = rows[0]["id"]
    if not access.can_admin(uid, "clinic"):
        raise SeedRefused("O administrador nao possui permissao de espaco clinico")
    return uid


def _existing(cur, uid, tenant_id):
    cur.execute(
        """SELECT id,birth_date FROM clients
           WHERE tenant_id=%s AND professional_user_id=%s AND nome=%s
           ORDER BY id FOR UPDATE""",
        (tenant_id, uid, DEMO_NAME)
    )
    rows = cur.fetchall()
    if not rows:
        return None
    if len(rows) != 1 or str(rows[0]["birth_date"]) != DEMO_BIRTH:
        raise SeedRefused("Cadastro homonimo inconsistente: revisar sem sobrescrever")
    client_id = rows[0]["id"]
    cur.execute(
        """SELECT i.representation_mode,c.full_name,c.email
           FROM care_patient_intakes i
           LEFT JOIN care_client_contacts c ON
             c.id=i.guardian_contact_id AND c.tenant_id=i.tenant_id
             AND c.client_id=i.client_id AND c.professional_user_id=i.professional_user_id
           WHERE i.tenant_id=%s AND i.client_id=%s
             AND i.professional_user_id=%s""",
        (tenant_id, client_id, uid)
    )
    profile = cur.fetchone()
    if (not profile or profile["representation_mode"] != "guardian"
            or profile["full_name"] != DEMO_GUARDIAN
            or profile["email"] is not None):
        raise SeedRefused("Paciente ficticio existente exige revisao; nada alterado")
    return client_id


def seed(*, apply=False, admin_id=None):
    fields = intake.validate_intake(
        "guardian", DEMO_NAME, DEMO_BIRTH, DEMO_REPORT, DEMO_GUARDIAN
    )
    uid = select_admin(admin_id)
    tenant = workspace.own_admin_workspace(uid)
    if not apply:
        return {
            "status": "would_exist" if tenant and _find_demo(uid, tenant["id"]) else "would_create",
            "admin_id": uid, "tenant_id": tenant["id"] if tenant else None,
            "workspace_activation_needed": tenant is None,
        }

    # Reuse the application's authorized admin workspace creation, never impersonate
    # an external professional or widen another tenant's visibility.
    if not tenant:
        workspace.activate_personal_admin_workspace(uid)
        tenant = workspace.own_admin_workspace(uid)
    if not tenant:
        raise SeedRefused("Nao foi possivel confirmar o espaco clinico proprio")

    ciphertext = intake._cipher().encrypt(fields["report"].encode("utf-8"))
    with store.transaction() as cur:
        cur.execute(
            """SELECT t.id FROM tenants t
               JOIN tenant_members m ON m.tenant_id=t.id
               WHERE t.id=%s AND t.owner_user_id=%s AND t.status='active'
                 AND m.user_id=%s AND m.membership_role='owner'
                 AND m.status='active' FOR UPDATE""",
            (tenant["id"], uid, uid)
        )
        if not cur.fetchone():
            raise SeedRefused("Espaco clinico proprio nao esta ativo")
        existing = _existing(cur, uid, tenant["id"])
        if existing is not None:
            return {"status": "already_exists", "admin_id": uid,
                    "tenant_id": tenant["id"], "client_id": existing}
        cur.execute(
            """INSERT INTO clients(tenant_id,professional_user_id,nome,email,birth_date)
               VALUES(%s,%s,%s,NULL,%s)""",
            (tenant["id"], uid, fields["name"], fields["birth"])
        )
        client_id = cur.lastrowid
        cur.execute(
            """INSERT INTO care_client_contacts
               (tenant_id,client_id,professional_user_id,full_name,
                contact_role,email,verification_status)
               VALUES(%s,%s,%s,%s,'legal_guardian',NULL,'unverified')""",
            (tenant["id"], client_id, uid, DEMO_GUARDIAN)
        )
        contact_id = cur.lastrowid
        cur.execute(
            """INSERT INTO care_patient_intakes
               (tenant_id,client_id,professional_user_id,representation_mode,
                initial_report_encrypted,guardian_contact_id)
               VALUES(%s,%s,%s,'guardian',%s,%s)""",
            (tenant["id"], client_id, uid, ciphertext, contact_id)
        )
        store.audit(cur, uid, tenant["id"], "synthetic_patient_seeded",
                    "client", client_id, reason="test record: no real person")
        return {"status": "created", "admin_id": uid,
                "tenant_id": tenant["id"], "client_id": client_id}


def _find_demo(uid, tenant_id):
    result = store.one(
        """SELECT id FROM clients WHERE tenant_id=%s
           AND professional_user_id=%s AND nome=%s LIMIT 1""",
        (tenant_id, uid, DEMO_NAME)
    )
    return bool(result)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Synthetic admin clinical patient")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument("--admin-id", type=int)
    args = parser.parse_args(argv)
    try:
        result = seed(apply=args.apply, admin_id=args.admin_id)
    except (SeedRefused, ValueError, PermissionError) as exc:
        print("DEMO_PATIENT_REFUSED:", str(exc), file=sys.stderr)
        return 2
    print("DEMO_PATIENT_" + result["status"].upper(),
          "admin_id=" + str(result["admin_id"]),
          "tenant_id=" + str(result["tenant_id"]),
          "client_id=" + str(result.get("client_id", "pending")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
