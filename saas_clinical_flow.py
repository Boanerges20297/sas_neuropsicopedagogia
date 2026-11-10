"""Private professional encounters, revisioned encrypted notes and scoped reports.

No superadmin can select another clinician's clinical record: every query
derives the owner from the authenticated principal and its own active tenant.
"""
from datetime import date, datetime, timedelta, timezone
from html import escape
from html.parser import HTMLParser
from uuid import UUID
from zoneinfo import ZoneInfo
import base64
import os
import re

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

import saas_store as store
import saas_care_store as care

SAFE_TAGS = frozenset(("p", "br", "strong", "em", "u", "ul", "ol",
                       "li", "blockquote", "h2", "h3"))
DISCARD_TAGS = frozenset(("script", "style", "iframe", "svg", "math",
                          "object", "template", "noscript"))
ALLOWED_PERIODS = frozenset(("day", "month", "year"))
CLINIC_TZ = ZoneInfo("America/Fortaleza")


class _Sanitizer(HTMLParser):
    """Allow formatting only. No user-supplied attributes, links or media."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.blocked = 0

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in DISCARD_TAGS:
            self.blocked += 1
        elif not self.blocked and tag in SAFE_TAGS:
            self.parts.append("<" + tag + ">")

    def handle_startendtag(self, tag, attrs):
        if not self.blocked and tag.lower() == "br":
            self.parts.append("<br>")

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in DISCARD_TAGS:
            self.blocked = max(0, self.blocked - 1)
        elif not self.blocked and tag in SAFE_TAGS and tag != "br":
            self.parts.append("</" + tag + ">")

    def handle_data(self, data):
        if not self.blocked:
            self.parts.append(escape(data, quote=True))


def sanitize_note(html):
    if not isinstance(html, str) or len(html) > 30000:
        raise ValueError("O registro excede 30 mil caracteres")
    parser = _Sanitizer()
    parser.feed(html)
    parser.close()
    cleaned = "".join(parser.parts).strip()
    if len(cleaned.encode("utf-8")) > 40000:
        raise ValueError("Registro muito extenso")
    return cleaned


def _cipher(purpose):
    secret = os.getenv("SECRET_KEY", "")
    if len(secret) < 32:
        raise RuntimeError("SECRET_KEY segura é necessária para evoluções clínicas")
    key = HKDF(algorithm=hashes.SHA256(), length=32,
               salt=b"neuro-diagnosis-saas-v1",
               info=("clinical:" + purpose + "-v1").encode("ascii")).derive(
                   secret.encode("utf-8"))
    return Fernet(base64.urlsafe_b64encode(key))


def encrypt_text(value, purpose):
    return _cipher(purpose).encrypt(value.encode("utf-8"))


def decrypt_text(blob, purpose):
    return _cipher(purpose).decrypt(bytes(blob)).decode("utf-8")


def _uuid4(raw):
    try:
        val = UUID(str(raw))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError("Identificador de abertura inválido") from exc
    if val.version != 4 or str(val) != raw:
        raise ValueError("Identificador de abertura inválido")
    return raw


def start_encounter(user_id, tenant_id, client_id, request_id):
    """Idempotent one-click visit without a scheduled appointment."""
    rid = _uuid4(request_id)
    with store.transaction() as cur:
        care._lock_owned_client(cur, user_id, tenant_id, client_id)
        cur.execute(
            """SELECT encounter_id,client_id FROM care_encounter_starts
               WHERE tenant_id=%s AND professional_user_id=%s AND request_id=%s
               LIMIT 1 FOR UPDATE""", (tenant_id, user_id, rid))
        prior = cur.fetchone()
        if prior:
            if prior["client_id"] != client_id:
                raise ValueError("Identificador já utilizado em outro paciente")
            return prior["encounter_id"]
        cur.execute(
            """INSERT INTO care_encounters
               (tenant_id,appointment_id,client_id,professional_user_id,status)
               VALUES(%s,NULL,%s,%s,'draft')""",
            (tenant_id, client_id, user_id))
        ident = cur.lastrowid
        cur.execute(
            """INSERT INTO care_encounter_starts
               (tenant_id,client_id,professional_user_id,encounter_id,request_id)
               VALUES(%s,%s,%s,%s,%s)""",
            (tenant_id, client_id, user_id, ident, rid))
        store.audit(cur, user_id, tenant_id, "care_encounter_opened",
                    "care_encounter", ident)
        return ident


def scoped_encounter(user_id, tenant_id, client_id, encounter_id):
    """Filters every dimension; do not return 403 with ID existence leaks."""
    return store.one(
        """SELECT e.id,e.status,e.opened_at,e.signed_at,e.appointment_id,
                  c.nome AS client_name,c.birth_date
           FROM care_encounters e
           JOIN clients c ON c.id=e.client_id AND c.tenant_id=e.tenant_id
               AND c.professional_user_id=e.professional_user_id
           JOIN tenant_members m ON m.tenant_id=e.tenant_id
                AND m.user_id=e.professional_user_id
           JOIN tenants t ON t.id=e.tenant_id
           WHERE e.id=%s AND e.tenant_id=%s AND e.client_id=%s
             AND e.professional_user_id=%s AND m.user_id=%s
             AND m.status='active' AND t.status='active'
             AND c.status='active' LIMIT 1""",
        (encounter_id, tenant_id, client_id, user_id, user_id))


def list_encounters(user_id, tenant_id, client_id=None, limit=80):
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("Limite inválido")
    filters = ""
    args = [user_id, tenant_id, user_id, user_id]
    if client_id is not None:
        filters = " AND e.client_id=%s"
        args.append(client_id)
    args.append(limit)
    return store.all_rows(
        """SELECT e.id,e.client_id,e.opened_at,e.status,c.nome AS client_name
           FROM care_encounters e
           JOIN clients c ON c.id=e.client_id AND c.tenant_id=e.tenant_id
             AND c.professional_user_id=e.professional_user_id
           JOIN tenant_members m ON m.tenant_id=e.tenant_id AND m.user_id=%s
             AND m.status='active'
           WHERE e.tenant_id=%s AND e.professional_user_id=%s
             AND c.professional_user_id=%s AND c.status='active'"""
        + filters + " ORDER BY e.opened_at DESC,e.id DESC LIMIT %s", tuple(args))


def latest_note(user_id, tenant_id, client_id, encounter_id):
    if not scoped_encounter(user_id, tenant_id, client_id, encounter_id):
        raise PermissionError("Atendimento não localizado")
    row = store.one(
        """SELECT revision,ciphertext,created_at FROM care_encounter_notes
           WHERE encounter_id=%s ORDER BY revision DESC LIMIT 1""", (encounter_id,))
    if not row:
        return {"revision": 0, "html": "", "created_at": None}
    return {"revision": row["revision"],
            "html": decrypt_text(row["ciphertext"], "encounter-note"),
            "created_at": row["created_at"]}


def save_note(user_id, tenant_id, client_id, encounter_id, html, expected_revision):
    cleaned = sanitize_note(html)
    try:
        expected = int(expected_revision)
    except (TypeError, ValueError) as exc:
        raise ValueError("Versão de edição inválida") from exc
    if expected < 0:
        raise ValueError("Versão de edição inválida")
    payload = encrypt_text(cleaned, "encounter-note")
    with store.transaction() as cur:
        care._lock_owned_client(cur, user_id, tenant_id, client_id)
        cur.execute(
            """SELECT id,status FROM care_encounters
               WHERE id=%s AND tenant_id=%s AND client_id=%s
                 AND professional_user_id=%s FOR UPDATE""",
            (encounter_id, tenant_id, client_id, user_id))
        row = cur.fetchone()
        if not row:
            raise PermissionError("Atendimento não localizado")
        if row["status"] != "draft":
            raise ValueError("Registros assinados não podem ser editados")
        cur.execute(
            """SELECT revision FROM care_encounter_notes
               WHERE encounter_id=%s ORDER BY revision DESC LIMIT 1""",
            (encounter_id,))
        old = cur.fetchone()
        revision = old["revision"] if old else 0
        if expected != revision:
            raise ValueError("Este atendimento mudou em outra aba. Atualize antes de salvar.")
        cur.execute(
            """INSERT INTO care_encounter_notes
               (encounter_id,revision,ciphertext,edited_by)
               VALUES (%s,%s,%s,%s)""",
            (encounter_id, revision + 1, payload, user_id))
        store.audit(cur, user_id, tenant_id, "care_encounter_note_saved",
                    "care_encounter", encounter_id)
        return revision + 1


def record_diagnosis(user_id, tenant_id, client_id, encounter_id,
                     label, code="", certainty="hypothesis"):
    name = (label or "").strip()
    code = (code or "").strip().upper()
    if len(name) < 3 or len(name) > 160:
        raise ValueError("Descreva o diagnóstico ou hipótese em 3 a 160 caracteres")
    if code and not re.fullmatch(r"[A-Z0-9.\-]{2,32}", code):
        raise ValueError("Código informado é inválido")
    if certainty not in ("hypothesis", "confirmed", "excluded"):
        raise ValueError("Classificação inválida")
    with store.transaction() as cur:
        care._lock_owned_client(cur, user_id, tenant_id, client_id)
        cur.execute(
            """SELECT id,status FROM care_encounters
               WHERE id=%s AND tenant_id=%s AND client_id=%s
                 AND professional_user_id=%s FOR UPDATE""",
            (encounter_id, tenant_id, client_id, user_id))
        item = cur.fetchone()
        if not item:
            raise PermissionError("Atendimento não localizado")
        if item["status"] != "draft":
            raise ValueError("Registro assinado não pode ser alterado")
        cur.execute(
            """INSERT INTO care_diagnosis_records
               (tenant_id,client_id,professional_user_id,encounter_id,code,label,certainty)
               VALUES (%s,%s,%s,%s,%s,%s,%s)""",
            (tenant_id, client_id, user_id, encounter_id, code or None, name, certainty))
        ident = cur.lastrowid
        store.audit(cur, user_id, tenant_id, "care_diagnosis_recorded",
                    "care_diagnosis", ident)
        return ident


def list_diagnoses(user_id, tenant_id, client_id, encounter_id):
    """Longitudinal clinical history, restricted to the same professional/patient.

    A hypothesis belongs to the patient's assessment over several visits,
    not to an automatically completed single appointment.
    """
    if not scoped_encounter(user_id, tenant_id, client_id, encounter_id):
        raise PermissionError("Atendimento não localizado")
    return store.all_rows(
        """SELECT d.id,d.label,d.code,d.certainty,d.recorded_at,
                  d.encounter_id,e.opened_at AS encounter_opened_at
           FROM care_diagnosis_records d
           JOIN care_encounters e ON e.id=d.encounter_id
             AND e.tenant_id=d.tenant_id AND e.client_id=d.client_id
             AND e.professional_user_id=d.professional_user_id
           WHERE d.tenant_id=%s AND d.client_id=%s
             AND d.professional_user_id=%s
           ORDER BY d.recorded_at DESC,d.id DESC LIMIT 100""",
        (tenant_id, client_id, user_id))


def _range(period, anchor):
    if period not in ALLOWED_PERIODS:
        raise ValueError("Filtro inválido")
    today = datetime.now(CLINIC_TZ).date()
    if not anchor:
        anchor = (today.isoformat() if period == "day"
                  else today.strftime("%Y-%m") if period == "month"
                  else str(today.year))
    try:
        if period == "day":
            day = date.fromisoformat(anchor)
            if day.isoformat() != anchor:
                raise ValueError()
            start = datetime(day.year, day.month, day.day, tzinfo=CLINIC_TZ)
            end = start + timedelta(days=1)
            fmt = "%H:00"
        elif period == "month":
            if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", anchor):
                raise ValueError()
            year, month = map(int, anchor.split("-"))
            start = datetime(year, month, 1, tzinfo=CLINIC_TZ)
            end = datetime(year + (month == 12), month % 12 + 1, 1,
                           tzinfo=CLINIC_TZ)
            fmt = "%d/%m"
        else:
            if not re.fullmatch(r"\d{4}", anchor):
                raise ValueError()
            year = int(anchor)
            start = datetime(year, 1, 1, tzinfo=CLINIC_TZ)
            end = datetime(year + 1, 1, 1, tzinfo=CLINIC_TZ)
            fmt = "%m/%Y"
        if start.year < 2020 or start.year > 2100:
            raise ValueError()
    except (ValueError, OverflowError, TypeError) as exc:
        raise ValueError("Informe uma data válida entre 2020 e 2100") from exc
    return start.astimezone(timezone.utc).replace(tzinfo=None), end.astimezone(
        timezone.utc).replace(tzinfo=None), fmt, anchor


def professional_dashboard(user_id, tenant_id, period="month", anchor=""):
    start, end, group_fmt, chosen = _range(period, anchor)
    params = (tenant_id, user_id, start, end)
    metrics = store.one(
        """SELECT COUNT(*) AS total,
                  COUNT(DISTINCT e.client_id) AS unique_clients
           FROM care_encounters e
           WHERE e.tenant_id=%s AND e.professional_user_id=%s
             AND e.opened_at >= %s AND e.opened_at < %s""", params)
    assessments = store.one(
        """SELECT COUNT(*) AS total,
                  COALESCE(SUM(a.status IN ('submitted','reviewed')),0) AS answered
           FROM assessments a
           WHERE a.tenant_id=%s AND a.responsible_user_id=%s
             AND a.created_at >= %s AND a.created_at < %s""", params)
    # Only manually confirmed diagnoses, never inferred from a test score.
    diagnoses = store.all_rows(
        """SELECT d.label,COUNT(DISTINCT d.client_id) AS quantity
           FROM care_diagnosis_records d
           WHERE d.tenant_id=%s AND d.professional_user_id=%s
             AND d.recorded_at >= %s AND d.recorded_at < %s
             AND d.certainty='confirmed'
           GROUP BY d.label ORDER BY quantity DESC,d.label LIMIT 12""", params)
    # Input format is fixed in this module (not interpolated from HTTP).
    timeline = store.all_rows(
        """SELECT DATE_FORMAT(DATE_SUB(e.opened_at,INTERVAL 3 HOUR),'"""
        + group_fmt.replace("%", "%%") + """') AS bucket,COUNT(*) AS quantity
           FROM care_encounters e
           WHERE e.tenant_id=%s AND e.professional_user_id=%s
             AND e.opened_at >= %s AND e.opened_at < %s
           GROUP BY bucket ORDER BY MIN(e.opened_at)""", params)
    return {"period": period, "anchor": chosen,
            "total": metrics["total"], "unique_clients": metrics["unique_clients"],
            "tests": assessments["total"], "tests_answered": assessments["answered"],
            "diagnoses": diagnoses, "timeline": timeline}
