"""Patient intake is a clinical profile, NOT a second login account.

Adults may act for themselves; a minor is a patient associated with ONE
guardian contact (existing account can be linked later after verification).
Initial symptomatic observations are encrypted at rest and never audited.
"""
from datetime import date, datetime
from zoneinfo import ZoneInfo
import base64
import os
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

import saas_store as store

MAX_REPORT_CHARS = 2000
MODES = frozenset({"self", "guardian"})


def age_years(birth, today=None):
    today = today or datetime.now(ZoneInfo('America/Fortaleza')).date()
    return today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))


def validate_intake(mode, name, birth_date, initial_report="", guardian_name="", guardian_email=""):
    if mode not in MODES:
        raise ValueError("Selecione se o paciente responde por si ou é menor")
    name = (name or "").strip()
    if not name or len(name) > 180:
        raise ValueError("Informe o nome completo do paciente")
    try:
        if not isinstance(birth_date, str) or len(birth_date.strip()) != 10:
            raise ValueError()
        birth = date.fromisoformat(birth_date.strip())
    except ValueError:
        raise ValueError("Data de nascimento inválida") from None
    age = age_years(birth)
    if age < 0 or age > 120:
        raise ValueError("Data de nascimento fora do intervalo permitido")
    if mode == "self" and age < 18:
        raise ValueError("Menores precisam de um responsável legal")
    if mode == "guardian" and age >= 18:
        raise ValueError("Paciente adulto deve ser cadastrado na modalidade própria")
    report = (initial_report or "").strip()
    if len(report) > MAX_REPORT_CHARS:
        raise ValueError("Observações iniciais excedem 2000 caracteres")
    gname = (guardian_name or "").strip()
    gmail = (guardian_email or "").strip().lower()
    if mode == "guardian":
        if not gname or len(gname) > 160:
            raise ValueError("Informe o nome do responsável legal")
        if gmail and (len(gmail) > 254 or not store.EMAIL_RE.fullmatch(gmail)):
            raise ValueError("E-mail do responsável inválido")
    else:
        gname = ""
        gmail = ""
    return {"mode": mode, "name": name, "birth": birth,
            "report": report, "guardian_name": gname, "guardian_email": gmail,
            "age": age}


def _cipher():
    secret = os.getenv("SECRET_KEY", "")
    if len(secret) < 32:
        raise RuntimeError("SECRET_KEY segura é necessária para dados de saúde")
    key = HKDF(
        algorithm=hashes.SHA256(), length=32,
        salt=b"neuro-diagnosis-saas-v1",
        info=b"clinical:patient-intake-report-v1",
    ).derive(secret.encode("utf-8"))
    return Fernet(base64.urlsafe_b64encode(key))


def register_intake(user_id, tenant_id, *, mode, name, birth_date, initial_report="",
                    guardian_name="", guardian_email="", email=""):
    fields = validate_intake(mode, name, birth_date, initial_report,
                             guardian_name, guardian_email)
    email = (email or "").strip().lower()
    if mode == "self" and email and (len(email) > 254 or not store.EMAIL_RE.fullmatch(email)):
        raise ValueError("E-mail do paciente inválido")
    # Encrypt before beginning database writes. A failure must leave no partial
    # patient or contact record behind.
    encrypted = (_cipher().encrypt(fields["report"].encode("utf-8"))
                 if fields["report"] else None)
    with store.transaction() as cur:
        cur.execute(
            """SELECT 1 FROM tenant_members m JOIN tenants t ON t.id=m.tenant_id
               WHERE m.tenant_id=%s AND m.user_id=%s
                 AND m.status='active' AND t.status='active'
                 AND m.membership_role IN ('owner','professional') FOR UPDATE""",
            (tenant_id, user_id),
        )
        if not cur.fetchone():
            raise PermissionError("Profissional não autorizado neste espaço")
        cur.execute(
            """INSERT INTO clients(tenant_id,professional_user_id,nome,email,birth_date)
               VALUES(%s,%s,%s,%s,%s)""",
            (tenant_id, user_id, fields["name"], email or None
             if mode == "self" else None, fields["birth"]),
        )
        client_id = cur.lastrowid
        contact_id = None
        if mode == "guardian":
            cur.execute(
                """INSERT INTO care_client_contacts
                   (tenant_id,client_id,professional_user_id,
                    full_name,contact_role,email,verification_status)
                   VALUES(%s,%s,%s,%s,'legal_guardian',%s,'unverified')""",
                (tenant_id, client_id, user_id, fields["guardian_name"],
                 fields["guardian_email"] or None),
            )
            contact_id = cur.lastrowid
        cur.execute(
            """INSERT INTO care_patient_intakes
               (tenant_id,client_id,professional_user_id,representation_mode,
                initial_report_encrypted,guardian_contact_id)
               VALUES(%s,%s,%s,%s,%s,%s)""",
            (tenant_id, client_id, user_id, mode, encrypted, contact_id),
        )
        store.audit(cur, user_id, tenant_id, "patient_intake_created",
                    "client", client_id)
        return client_id


def scoped_summary(user_id, tenant_id, client_id):
    """No direct access unless the client belongs to this clinician."""
    from saas_neurocore_store import scoped_client
    if not scoped_client(user_id, tenant_id, client_id):
        return None
    row = store.one(
        """SELECT i.representation_mode,patient.birth_date,
                  i.initial_report_encrypted,c.full_name AS guardian_name
           FROM care_patient_intakes i
           JOIN clients patient ON patient.id=i.client_id
             AND patient.tenant_id=i.tenant_id
             AND patient.professional_user_id=i.professional_user_id
           LEFT JOIN care_client_contacts c
             ON c.id=i.guardian_contact_id AND c.tenant_id=i.tenant_id
             AND c.client_id=i.client_id AND c.professional_user_id=i.professional_user_id
           WHERE i.tenant_id=%s AND i.client_id=%s
             AND i.professional_user_id=%s""",
        (tenant_id, client_id, user_id),
    )
    if not row:
        return None  # existing/legacy patients need explicit, authorized intake
    row["age"] = age_years(row["birth_date"])
    blob = row.pop("initial_report_encrypted")
    row["initial_report"] = (_cipher().decrypt(bytes(blob)).decode("utf-8")
                             if blob else "")
    return row
