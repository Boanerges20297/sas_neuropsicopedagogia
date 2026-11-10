"""Care journey — scoped scheduling and encounter metadata (MySQL SaaS).

Only a professional's OWN active clients are addressable. No clinical narratives,
diagnoses, portal invites or unverified-guardian access. All writes audited.
"""
from datetime import datetime, timedelta, timezone
from uuid import UUID
from zoneinfo import ZoneInfo

import saas_store as store

CLINIC_TIMEZONE = "America/Fortaleza"
SERVICES = frozenset({"initial", "follow_up", "assessment", "feedback"})
MODALITIES = frozenset({"in_person", "remote"})
DURATIONS = frozenset({30, 45, 60, 90, 120})
TRANSITIONS = {
    "scheduled": frozenset({"confirmed", "completed", "cancelled", "no_show"}),
    "confirmed": frozenset({"completed", "cancelled", "no_show"}),
    "completed": frozenset(),
    "cancelled": frozenset(),
    "no_show": frozenset(),
}


def normalize_request_id(raw):
    if not isinstance(raw, str) or len(raw) != 36:
        raise ValueError("Identificador do agendamento inválido")
    try:
        value = UUID(raw)
    except (ValueError, AttributeError) as exc:
        raise ValueError("Identificador do agendamento inválido") from exc
    if value.version != 4 or str(value) != raw.lower():
        raise ValueError("Identificador do agendamento inválido")
    return str(value)


def parse_start(local_start, duration, *, now=None):
    """Local Fortaleza wall time -> MySQL UTC DATETIME values.

    The extra UTC round-trip rejects nonexistent local times from DST changes.
    """
    if not isinstance(local_start, str) or len(local_start) != 16:
        raise ValueError("Informe data e hora válidas")
    try:
        wall = datetime.strptime(local_start, "%Y-%m-%dT%H:%M")
        minutes = int(duration)
    except (TypeError, ValueError) as exc:
        raise ValueError("Data, hora ou duração inválida") from exc
    if minutes not in DURATIONS or wall.minute % 15:
        raise ValueError("Duração ou horário fora das opções permitidas")
    zone = ZoneInfo(CLINIC_TIMEZONE)
    zoned = wall.replace(tzinfo=zone)
    start = zoned.astimezone(timezone.utc)
    if start.astimezone(zone).replace(tzinfo=None) != wall:
        raise ValueError("Horário local inexistente")
    current = now if now is not None else datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise ValueError("Relógio de referência sem fuso horário")
    if start < current - timedelta(minutes=5) or start > current + timedelta(days=366):
        raise ValueError("Agendamento deve ser atual ou futuro, no máximo 366 dias")
    return (start.replace(tzinfo=None),
            (start + timedelta(minutes=minutes)).replace(tzinfo=None))


def format_appointment(row):
    """Format UTC data only for an authenticated, scope-checked result."""
    copy = dict(row)
    value = copy.get("starts_at_utc")
    if isinstance(value, datetime):
        local = value.replace(tzinfo=timezone.utc).astimezone(ZoneInfo(CLINIC_TIMEZONE))
        copy["local_start"] = local.strftime("%d/%m/%Y %H:%M")
        copy["local_input"] = local.strftime("%Y-%m-%dT%H:%M")
        end = copy.get("ends_at_utc")
        copy["minutes"] = (int((end - value).total_seconds() // 60)
                           if isinstance(end, datetime) else 60)
    return copy


def _lock_owned_client(cur, user_id, tenant_id, client_id):
    # Lock the shared tenant membership row to serialize scheduling for the
    # practitioner across clients, avoiding phantom overlap insertions.
    cur.execute(
        """SELECT c.id FROM clients c
           JOIN tenant_members m ON m.tenant_id=c.tenant_id
           JOIN tenants t ON t.id=c.tenant_id
           WHERE c.id=%s AND c.tenant_id=%s AND c.professional_user_id=%s
             AND c.status='active' AND m.user_id=%s
             AND m.membership_role IN ('owner','professional')
             AND m.status='active' AND t.status='active'
           FOR UPDATE""", (client_id, tenant_id, user_id, user_id),
    )
    if not cur.fetchone():
        raise PermissionError("Paciente indisponível neste espaço profissional")


def create_appointment(user_id, tenant_id, client_id, *, local_start, duration,
                       service_type, modality, request_id, now=None):
    if service_type not in SERVICES or modality not in MODALITIES:
        raise ValueError("Tipo ou modalidade não permitidos")
    ident = normalize_request_id(request_id)
    with store.transaction() as cur:
        _lock_owned_client(cur, user_id, tenant_id, client_id)
        cur.execute(
            """SELECT id,client_id FROM care_appointments
               WHERE tenant_id=%s AND professional_user_id=%s AND request_id=%s
               LIMIT 1 FOR UPDATE""", (tenant_id, user_id, ident),
        )
        previous = cur.fetchone()
        if previous:
            if previous["client_id"] != client_id:
                raise ValueError("Identificador de agendamento já utilizado por outro cliente")
            return previous["id"]
        start, end = parse_start(local_start, duration, now=now)
        cur.execute(
            """SELECT id FROM care_appointments
               WHERE tenant_id=%s AND professional_user_id=%s
                 AND status IN ('scheduled','confirmed')
                 AND starts_at_utc < %s AND ends_at_utc > %s
               LIMIT 1 FOR UPDATE""", (tenant_id, user_id, end, start),
        )
        if cur.fetchone():
            raise ValueError("Profissional já possui atendimento nesse intervalo")
        # A patient-requested slot is held until the clinician decides.
        cur.execute(
            """SELECT id FROM care_schedule_slots
               WHERE tenant_id=%s AND professional_user_id=%s AND status='pending'
                 AND starts_at_utc < %s AND ends_at_utc > %s LIMIT 1""",
            (tenant_id, user_id, end, start))
        if cur.fetchone():
            raise ValueError("Existe uma solicitação de paciente neste horário")
        cur.execute(
            """INSERT INTO care_appointments
               (tenant_id,client_id,professional_user_id,request_id,service_type,
                modality,timezone_name,starts_at_utc,ends_at_utc,status)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'scheduled')""",
            (tenant_id, client_id, user_id, ident, service_type, modality,
             CLINIC_TIMEZONE, start, end),
        )
        appt_id = cur.lastrowid
        # Direct professional bookings withdraw overlapping public availability.
        cur.execute(
            """UPDATE care_schedule_slots SET status='closed'
               WHERE tenant_id=%s AND professional_user_id=%s
                 AND status='open'
                 AND starts_at_utc < %s AND ends_at_utc > %s""",
            (tenant_id, user_id, end, start))
        store.audit(cur, user_id, tenant_id, "care_appointment_scheduled",
                    "care_appointment", appt_id)
        return appt_id


def list_client_appointments(user_id, tenant_id, client_id, *, limit=50):
    from saas_neurocore_store import scoped_client
    if not scoped_client(user_id, tenant_id, client_id):
        raise PermissionError("Paciente indisponível neste espaço profissional")
    if not isinstance(limit, int) or limit < 1 or limit > 100:
        raise ValueError("Limite inválido")
    records = store.all_rows(
        """SELECT id,client_id,service_type,modality,starts_at_utc,ends_at_utc,status
           FROM care_appointments
           WHERE tenant_id=%s AND professional_user_id=%s AND client_id=%s
           ORDER BY starts_at_utc DESC LIMIT %s""",
        (tenant_id, user_id, client_id, limit),
    )
    return [format_appointment(r) for r in records]


def list_calendar(user_id, tenant_id, *, days=30):
    if not isinstance(days, int) or days < 1 or days > 90:
        raise ValueError("Período inválido")
    records = store.all_rows(
        """SELECT a.id,a.client_id,c.nome AS client_name,
                  a.service_type,a.modality,a.starts_at_utc,a.ends_at_utc,a.status
           FROM care_appointments a
           JOIN clients c ON c.id=a.client_id AND c.tenant_id=a.tenant_id
           JOIN tenants t ON t.id=a.tenant_id
           JOIN tenant_members m ON m.tenant_id=a.tenant_id AND m.user_id=%s
           WHERE a.tenant_id=%s AND a.professional_user_id=%s
             AND c.professional_user_id=%s AND c.status='active'
             AND m.status='active' AND t.status='active'
             AND a.starts_at_utc >= UTC_TIMESTAMP() - INTERVAL 1 DAY
             AND a.starts_at_utc < UTC_TIMESTAMP() + INTERVAL %s DAY
           ORDER BY a.starts_at_utc ASC LIMIT 200""",
        (user_id, tenant_id, user_id, user_id, days),
    )
    return [format_appointment(r) for r in records]


def reschedule_appointment(user_id, tenant_id, client_id, appointment_id, *,
                           local_start, duration, service_type, modality):
    """Edit a live appointment transactionally, retaining the appointment ID."""
    if service_type not in SERVICES or modality not in MODALITIES:
        raise ValueError("Tipo ou modalidade inválidos")
    start, end = parse_start(local_start, duration)
    with store.transaction() as cur:
        _lock_owned_client(cur, user_id, tenant_id, client_id)
        cur.execute(
            """SELECT id,status FROM care_appointments
               WHERE id=%s AND tenant_id=%s AND client_id=%s
                 AND professional_user_id=%s FOR UPDATE""",
            (appointment_id, tenant_id, client_id, user_id))
        appt = cur.fetchone()
        if not appt:
            raise PermissionError("Agendamento não encontrado")
        if appt["status"] not in ("scheduled", "confirmed"):
            raise ValueError("Somente consultas ativas podem ser alteradas")
        cur.execute(
            """SELECT id FROM care_schedule_slots
               WHERE tenant_id=%s AND professional_user_id=%s
                 AND appointment_id=%s AND status='booked' FOR UPDATE""",
            (tenant_id, user_id, appointment_id))
        bound = cur.fetchone()
        bound_id = bound["id"] if bound else None
        cur.execute(
            """SELECT id FROM care_appointments
               WHERE tenant_id=%s AND professional_user_id=%s
                 AND id<>%s AND status IN ('scheduled','confirmed')
                 AND starts_at_utc < %s AND ends_at_utc > %s LIMIT 1""",
            (tenant_id, user_id, appointment_id, end, start))
        if cur.fetchone():
            raise ValueError("Outra consulta ocupa este horário")
        cur.execute(
            """SELECT id FROM care_schedule_slots
               WHERE tenant_id=%s AND professional_user_id=%s
                 AND status IN ('open','pending','booked')
                 AND starts_at_utc < %s AND ends_at_utc > %s
                 AND (%s IS NULL OR id<>%s) LIMIT 1""",
            (tenant_id, user_id, end, start, bound_id, bound_id))
        if cur.fetchone():
            raise ValueError("Horário reservado ou publicado; retire a disponibilidade primeiro")
        cur.execute(
            """UPDATE care_appointments
               SET starts_at_utc=%s,ends_at_utc=%s,service_type=%s,
                   modality=%s WHERE id=%s""",
            (start, end, service_type, modality, appointment_id))
        if bound_id:
            cur.execute(
                """UPDATE care_schedule_slots
                   SET starts_at_utc=%s,ends_at_utc=%s,service_type=%s,
                       modality=%s WHERE id=%s""",
                (start, end, service_type, modality, bound_id))
        store.audit(cur, user_id, tenant_id, "care_appointment_rescheduled",
                    "care_appointment", appointment_id)
    return appointment_id


def transition_appointment(user_id, tenant_id, client_id, appointment_id, target):
    if target not in {"confirmed", "completed", "cancelled", "no_show"}:
        raise ValueError("Transição inválida")
    with store.transaction() as cur:
        _lock_owned_client(cur, user_id, tenant_id, client_id)
        cur.execute(
            """SELECT id,status,starts_at_utc FROM care_appointments
               WHERE id=%s AND tenant_id=%s AND client_id=%s
                 AND professional_user_id=%s LIMIT 1 FOR UPDATE""",
            (appointment_id, tenant_id, client_id, user_id),
        )
        appt = cur.fetchone()
        if not appt:
            raise PermissionError("Atendimento não encontrado neste espaço")
        if appt["status"] == target:
            return target
        if target not in TRANSITIONS.get(appt["status"], ()):
            raise ValueError("Transição de atendimento não permitida")
        if target in {"completed", "no_show"}:
            if appt["starts_at_utc"] > (datetime.now(timezone.utc).replace(tzinfo=None)
                                           + timedelta(minutes=15)):
                raise ValueError("Não é possível finalizar um atendimento futuro")
        cur.execute(
            """UPDATE care_appointments SET status=%s
               WHERE id=%s AND tenant_id=%s AND client_id=%s
                 AND professional_user_id=%s""",
            (target, appointment_id, tenant_id, client_id, user_id),
        )
        if target == "cancelled":
            # Clinical history stays in the appointment and audit log.
            cur.execute(
                """UPDATE care_schedule_slots
                   SET status='closed',appointment_id=NULL,
                       pending_user_id=NULL,pending_client_id=NULL
                   WHERE tenant_id=%s AND professional_user_id=%s
                     AND appointment_id=%s AND status='booked'""",
                (tenant_id, user_id, appointment_id))
        if target == "completed":
            cur.execute(
                """INSERT INTO care_encounters
                   (tenant_id,appointment_id,client_id,professional_user_id,status)
                   VALUES (%s,%s,%s,%s,'draft')""",
                (tenant_id, appointment_id, client_id, user_id),
            )
        store.audit(cur, user_id, tenant_id, "care_appointment_" + target,
                    "care_appointment", appointment_id)
        return target
