"""Seed opt-in para o espaço clínico EXCLUSIVO do superadmin.

Caso adulto inteiramente sintético: sem conta, CPF ou e-mail real.
Não executa na inicialização, migrations ou deploy. Idempotente.
Uso: python scripts/seed_demo_superadmin_patient.py --dry-run | --apply
"""
import argparse
import sys
from pathlib import Path
from unicodedata import normalize

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import saas_store as store
import saas_patient_intake as intake
import saas_admin_workspace as work

NAME = "PACIENTE FICTICIO - VALIDACAO SUPERADMIN"
BIRTH = "2001-05-15"
REPORT = ("CASO SINTETICO. Adulto ficticio relata dificuldades de organizacao "
          "e atencao no trabalho. Sem diagnostico, dados ou pessoa real.")


def canonical(value):
    return "".join(ch for ch in normalize("NFKD", str(value).lower())
                   if ch.isascii() and (ch.isalnum() or ch.isspace())).strip()


def select_owner():
    users = store.all_rows(
        """SELECT id,nome FROM users
           WHERE global_role='superadmin' AND active=1 ORDER BY id"""
    )
    matches = [u for u in users if " ".join(canonical(u["nome"]).split()).startswith("boanerges")]
    if len(matches) != 1:
        raise ValueError("Identidade do superadmin Boanerges não identificada unicamente")
    return matches[0]["id"]


def seed(*, apply=False):
    fields = intake.validate_intake("self", NAME, BIRTH, REPORT)
    uid = select_owner()
    tenant = work.own_admin_workspace(uid)
    if not apply:
        prior = (store.one(
            """SELECT id FROM clients WHERE tenant_id=%s
               AND professional_user_id=%s AND nome=%s LIMIT 1""",
            (tenant["id"], uid, NAME))
            if tenant else None)
        return {"status": "would_exist" if prior else "would_create",
                "superadmin_id": uid, "tenant_id": tenant["id"] if tenant else None}

    if not tenant:
        work.activate_personal_admin_workspace(uid)
        tenant = work.own_admin_workspace(uid)
    if not tenant:
        raise ValueError("Espaço clínico particular do superadmin indisponível")

    ciphertext = intake._cipher().encrypt(fields["report"].encode("utf-8"))
    with store.transaction() as cur:
        cur.execute(
            """SELECT t.id FROM tenants t JOIN tenant_members m
               ON m.tenant_id=t.id AND m.user_id=t.owner_user_id
               WHERE t.id=%s AND t.owner_user_id=%s
                 AND t.status='active' AND m.status='active'
                 AND m.membership_role='owner' FOR UPDATE""",
            (tenant["id"], uid))
        if not cur.fetchone():
            raise PermissionError("O superadmin não é dono do espaço clínico informado")

        cur.execute(
            """SELECT id,birth_date FROM clients
               WHERE tenant_id=%s AND professional_user_id=%s AND nome=%s
               ORDER BY id FOR UPDATE""",
            (tenant["id"], uid, NAME))
        existing = cur.fetchall()
        if existing:
            if len(existing) != 1 or str(existing[0]["birth_date"]) != BIRTH:
                raise ValueError("Cadastro de demonstração inconsistente: revisar")
            client_id = existing[0]["id"]
            cur.execute(
                """SELECT representation_mode FROM care_patient_intakes
                   WHERE tenant_id=%s AND client_id=%s
                     AND professional_user_id=%s""",
                (tenant["id"], client_id, uid))
            profile = cur.fetchone()
            if not profile or profile["representation_mode"] != "self":
                raise ValueError("Perfil de demonstração inconsistente: revisar")
            return {"status": "already_exists", "superadmin_id": uid,
                    "tenant_id": tenant["id"], "client_id": client_id}

        cur.execute(
            """INSERT INTO clients
               (tenant_id,professional_user_id,nome,email,birth_date)
               VALUES(%s,%s,%s,NULL,%s)""",
            (tenant["id"], uid, NAME, fields["birth"]))
        client_id = cur.lastrowid
        cur.execute(
            """INSERT INTO care_patient_intakes
               (tenant_id,client_id,professional_user_id,representation_mode,
                initial_report_encrypted,guardian_contact_id)
               VALUES(%s,%s,%s,'self',%s,NULL)""",
            (tenant["id"], client_id, uid, ciphertext))
        store.audit(cur, uid, tenant["id"], "synthetic_patient_seeded",
                    "client", client_id, reason="superadmin:adult-demo")
        return {"status": "created", "superadmin_id": uid,
                "tenant_id": tenant["id"], "client_id": client_id}


def main():
    p = argparse.ArgumentParser()
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    args = p.parse_args()
    try:
        result = seed(apply=args.apply)
    except (ValueError, PermissionError) as exc:
        print("SUPERADMIN_DEMO_REFUSED:", exc, file=sys.stderr)
        return 2
    print("SUPERADMIN_DEMO_" + result["status"].upper(),
          "superadmin_id=" + str(result["superadmin_id"]),
          "tenant_id=" + str(result["tenant_id"]),
          "client_id=" + str(result.get("client_id", "pending")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
