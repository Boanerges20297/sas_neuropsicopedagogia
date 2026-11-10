"""Scoped calendar availability and patient appointment requests.

A published slot is not an appointment. Patient requests reserve one slot
until the owning clinician confirms or rejects it. All writes are serialized
by the clinician's tenant_members row and audited; no clinical notes exposed.
"""
from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

import saas_store as store
import saas_care_store as care

MAX_SLOTS = 240


def _member_lock(cur, professional_id, tenant_id):
    cur.execute(
        """SELECT m.user_id FROM tenant_members m
           JOIN tenants t ON t.id=m.tenant_id
           JOIN users u ON u.id=m.user_id
           WHERE m.user_id=%s AND m.tenant_id=%s
             AND m.status='active' AND m.membership_role IN ('owner','professional')
             AND t.status='active' AND u.active=1 FOR UPDATE""",
        (professional_id, tenant_id))
    if not cur.fetchone():
        raise PermissionError("Espaço profissional indisponível")


def _conflicts(cur, tenant_id, user_id, start, end, *, exclude_slot=None,
               exclude_appointment=None):
    cur.execute(
        """SELECT id FROM care_schedule_slots
           WHERE tenant_id=%s AND professional_user_id=%s
             AND status IN ('open','pending','booked')
             AND starts_at_utc < %s AND ends_at_utc > %s
             AND (%s IS NULL OR id<>%s)
           LIMIT 1""",
        (tenant_id, user_id, end, start, exclude_slot, exclude_slot))
    if cur.fetchone():
        raise ValueError("Já existe horário publicado nesse intervalo")
    cur.execute(
        """SELECT id FROM care_appointments
           WHERE tenant_id=%s AND professional_user_id=%s
             AND status IN ('scheduled','confirmed')
             AND starts_at_utc < %s AND ends_at_utc > %s
             AND (%s IS NULL OR id<>%s) LIMIT 1""",
        (tenant_id, user_id, end, start, exclude_appointment, exclude_appointment))
    if cur.fetchone():
        raise ValueError("Já existe consulta agendada nesse intervalo")


def _day(raw):
    try:
        if not isinstance(raw, str) or len(raw) != 10:
            raise ValueError()
        parsed = date.fromisoformat(raw)
    except ValueError:
        raise ValueError("Data inválida") from None
    return parsed


def publish_slots(user_id, tenant_id, *, start_date, end_date, weekdays,
                  open_time, close_time, duration, gap, service_type, modality,
                  now=None):
    """Publish a bounded daily timetable, all-or-nothing. No partial calendar."""
    first, last = _day(start_date), _day(end_date)
    if last < first or (last - first).days > 30:
        raise ValueError("Selecione até 31 dias consecutivos")
    try:
        day_set = {int(d) for d in weekdays}
        minutes, spacing = int(duration), int(gap)
        h1 = datetime.strptime(open_time, "%H:%M")
        h2 = datetime.strptime(close_time, "%H:%M")
    except (ValueError, TypeError):
        raise ValueError("Confira horários, dias e intervalos") from None
    if not day_set or not day_set.issubset(set(range(7))):
        raise ValueError("Escolha ao menos um dia da semana")
    if minutes not in care.DURATIONS or spacing not in (0, 15, 30, 45, 60):
        raise ValueError("Duração ou intervalo não permitido")
    if (h1.minute % 15 or h2.minute % 15 or
            (h2 - h1).total_seconds() < minutes * 60):
        raise ValueError("Informe uma faixa de horários válida, em blocos de 15 minutos")
    if service_type not in care.SERVICES or modality not in care.MODALITIES:
        raise ValueError("Tipo de atendimento inválido")
    slots = []
    current_day = first
    while current_day <= last:
        if current_day.weekday() in day_set:
            wall = datetime.combine(current_day, h1.time())
            stop = datetime.combine(current_day, h2.time())
            while wall + timedelta(minutes=minutes) <= stop:
                local = wall.strftime("%Y-%m-%dT%H:%M")
                start, end = care.parse_start(local, minutes, now=now)
                slots.append((start, end))
                if len(slots) > MAX_SLOTS:
                    raise ValueError("Limite de 240 horários por operação")
                wall += timedelta(minutes=minutes + spacing)
        current_day += timedelta(days=1)
    if not slots:
        raise ValueError("Nenhum horário gerado; confira os dias selecionados")
    with store.transaction() as cur:
        _member_lock(cur, user_id, tenant_id)
        for start, end in slots:
            _conflicts(cur, tenant_id, user_id, start, end)
        for start, end in slots:
            cur.execute(
                """INSERT INTO care_schedule_slots
                   (tenant_id,professional_user_id,starts_at_utc,ends_at_utc,
                    service_type,modality,status)
                   VALUES(%s,%s,%s,%s,%s,%s,'open')""",
                (tenant_id, user_id, start, end, service_type, modality))
        store.audit(cur, user_id, tenant_id, "care_slots_published",
                    "tenant", tenant_id, reason="slots=" + str(len(slots)))
    return len(slots)


def list_slots(user_id, tenant_id, *, limit=250):
    if not (1 <= limit <= 300):
        raise ValueError("Limite inválido")
    rows = store.all_rows(
        """SELECT s.id,s.tenant_id,s.professional_user_id,s.starts_at_utc,
                  s.ends_at_utc,s.service_type,s.modality,s.status,
                  s.pending_client_id,c.nome AS patient_name,
                  s.appointment_id
           FROM care_schedule_slots s
           JOIN tenant_members m ON m.tenant_id=s.tenant_id
             AND m.user_id=s.professional_user_id AND m.status='active'
           LEFT JOIN clients c ON c.id=s.pending_client_id
             AND c.tenant_id=s.tenant_id AND c.professional_user_id=s.professional_user_id
           WHERE s.tenant_id=%s AND s.professional_user_id=%s
             AND s.starts_at_utc>=UTC_TIMESTAMP() - INTERVAL 1 DAY
           ORDER BY s.starts_at_utc ASC LIMIT %s""",
        (tenant_id, user_id, limit))
    return [_display(r) for r in rows]


def _display(row):
    from zoneinfo import ZoneInfo
    output = dict(row)
    start = row["starts_at_utc"]
    output["local_start"] = start.replace(tzinfo=timezone.utc).astimezone(
        ZoneInfo(care.CLINIC_TIMEZONE)).strftime("%d/%m/%Y %H:%M")
    output["local_input"] = start.replace(tzinfo=timezone.utc).astimezone(
        ZoneInfo(care.CLINIC_TIMEZONE)).strftime("%Y-%m-%dT%H:%M")
    output["minutes"] = int((row["ends_at_utc"] - start).total_seconds() // 60)
    return output


def change_slot(user_id, tenant_id, slot_id, *, action, local_start=None,
                duration=None, service_type=None, modality=None):
    if action not in {"edit", "close", "reject", "accept"}:
        raise ValueError("Ação inválida")
    with store.transaction() as cur:
        _member_lock(cur, user_id, tenant_id)
        cur.execute(
            """SELECT * FROM care_schedule_slots
               WHERE id=%s AND tenant_id=%s AND professional_user_id=%s
               FOR UPDATE""", (slot_id, tenant_id, user_id))
        slot = cur.fetchone()
        if not slot:
            raise PermissionError("Horário não encontrado")
        if action in {"edit", "close"}:
            if slot["status"] != "open":
                raise ValueError("Resolva a solicitação ou consulta antes de alterar o horário")
            if action == "close":
                cur.execute("UPDATE care_schedule_slots SET status='closed' WHERE id=%s",
                            (slot_id,))
            else:
                if service_type not in care.SERVICES or modality not in care.MODALITIES:
                    raise ValueError("Tipo de consulta inválido")
                start, end = care.parse_start(local_start, duration)
                _conflicts(cur, tenant_id, user_id, start, end, exclude_slot=slot_id)
                cur.execute(
                    """UPDATE care_schedule_slots
                       SET starts_at_utc=%s,ends_at_utc=%s,service_type=%s,modality=%s
                       WHERE id=%s""",
                    (start, end, service_type, modality, slot_id))
        else:
            if slot["status"] != "pending":
                raise ValueError("Não há solicitação pendente para este horário")
            if action == "reject":
                cur.execute(
                    """UPDATE care_schedule_slots
                       SET status='open',pending_user_id=NULL,pending_client_id=NULL,
                           requested_at=NULL WHERE id=%s""", (slot_id,))
            else:
                cur.execute(
                    """SELECT id FROM clients
                       WHERE id=%s AND tenant_id=%s AND professional_user_id=%s
                         AND status='active' FOR UPDATE""",
                    (slot["pending_client_id"], tenant_id, user_id))
                if not cur.fetchone():
                    raise PermissionError("Paciente não pertence mais a este profissional")
                _appointment_conflict(cur, tenant_id, user_id,
                                      slot["starts_at_utc"], slot["ends_at_utc"])
                from saas_portal_policy import SELECT_ALLOWED, SELECT_SELF_ALLOWED
                args=(slot["pending_user_id"], tenant_id, slot["pending_client_id"],
                      "appointments")
                cur.execute(SELECT_ALLOWED, args)
                if not cur.fetchone():
                    cur.execute(SELECT_SELF_ALLOWED, args)
                    if not cur.fetchone():
                        raise PermissionError("A autorização de acesso expirou")
                request_id = str(uuid4())
                cur.execute(
                    """INSERT INTO care_appointments
                       (tenant_id,client_id,professional_user_id,request_id,
                        service_type,modality,timezone_name,starts_at_utc,
                        ends_at_utc,status)
                       VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,'confirmed')""",
                    (tenant_id, slot["pending_client_id"], user_id, request_id,
                     slot["service_type"], slot["modality"], care.CLINIC_TIMEZONE,
                     slot["starts_at_utc"], slot["ends_at_utc"]))
                appointment_id = cur.lastrowid
                cur.execute(
                    """UPDATE care_schedule_slots
                       SET status='booked',appointment_id=%s WHERE id=%s""",
                    (appointment_id, slot_id))
        store.audit(cur, user_id, tenant_id, "care_slot_" + action,
                    "care_slot", slot_id)
    return action


def _appointment_conflict(cur, tenant_id, user_id, start, end):
    cur.execute(
        """SELECT id FROM care_appointments
           WHERE tenant_id=%s AND professional_user_id=%s
             AND status IN ('scheduled','confirmed')
             AND starts_at_utc < %s AND ends_at_utc > %s LIMIT 1""",
        (tenant_id, user_id, end, start))
    if cur.fetchone():
        raise ValueError("Horário ocupado por outra consulta")


def eligible_patients(principal_id):
    """Never infer clinical links from email. Return only explicitly granted patients."""
    from saas_portal_policy import can_access
    rows = store.all_rows(
        """SELECT a.tenant_id,a.client_id,a.professional_user_id,
                  c.nome AS client_name,t.nome AS tenant_name,u.nome AS clinician_name
           FROM care_portal_client_activations a
           JOIN clients c ON c.id=a.client_id AND c.tenant_id=a.tenant_id
             AND c.professional_user_id=a.professional_user_id AND c.status='active'
           JOIN tenants t ON t.id=a.tenant_id AND t.status='active'
           JOIN users u ON u.id=a.professional_user_id AND u.active=1
           WHERE a.user_id=%s AND a.status='active'
           ORDER BY t.nome,c.nome LIMIT 30""", (principal_id,))
    return [r for r in rows if can_access(principal_id, r["tenant_id"],
                                          r["client_id"], "appointments")]


def available_for_client(principal_id, tenant_id, client_id, professional_id):
    from saas_portal_policy import can_access
    if not can_access(principal_id, tenant_id, client_id, "appointments"):
        raise PermissionError("Acesso ao agendamento não autorizado")
    rows = store.all_rows(
        """SELECT s.id,s.starts_at_utc,s.ends_at_utc,s.service_type,s.modality
           FROM care_schedule_slots s
           JOIN clients c ON c.tenant_id=s.tenant_id
             AND c.professional_user_id=s.professional_user_id AND c.id=%s
             AND c.status='active'
           WHERE s.tenant_id=%s AND s.professional_user_id=%s
             AND s.status='open' AND s.starts_at_utc>UTC_TIMESTAMP()
             AND NOT EXISTS (
               SELECT 1 FROM care_appointments a
                WHERE a.tenant_id=s.tenant_id
                  AND a.professional_user_id=s.professional_user_id
                  AND a.status IN ('scheduled','confirmed')
                  AND a.starts_at_utc < s.ends_at_utc
                  AND a.ends_at_utc > s.starts_at_utc)
           ORDER BY s.starts_at_utc ASC LIMIT 100""",
        (client_id, tenant_id, professional_id))
    return [_display(r) for r in rows]


def patient_requests(principal_id, tenant_id, client_id, professional_id):
    from saas_portal_policy import can_access
    if not can_access(principal_id, tenant_id, client_id, "appointments"):
        raise PermissionError("Acesso ao agendamento não autorizado")
    rows = store.all_rows(
        """SELECT id,starts_at_utc,ends_at_utc,service_type,modality,status
           FROM care_schedule_slots
           WHERE tenant_id=%s AND professional_user_id=%s AND pending_client_id=%s
             AND pending_user_id=%s AND status IN ('pending','booked')
           ORDER BY starts_at_utc DESC LIMIT 100""",
        (tenant_id, professional_id, client_id, principal_id))
    return [_display(r) for r in rows]


def patient_slot_action(principal_id, tenant_id, client_id, professional_id,
                        slot_id, action):
    if action not in ("request", "withdraw"):
        raise ValueError("Ação inválida")
    from saas_portal_policy import SELECT_ALLOWED, SELECT_SELF_ALLOWED
    with store.transaction() as cur:
        # Membership lock serializes concurrent direct bookings, schedule edits
        # and patient requests by this clinician.
        _member_lock(cur, professional_id, tenant_id)
        cur.execute(
            """SELECT id,global_role,active FROM users WHERE id=%s""",
            (principal_id,))
        account = cur.fetchone()
        if not account or account["global_role"] != "patient" or not account["active"]:
            raise PermissionError("Conta não autorizada")
        cur.execute(
            """SELECT id FROM clients WHERE id=%s AND tenant_id=%s
               AND professional_user_id=%s AND status='active'""",
            (client_id, tenant_id, professional_id))
        if not cur.fetchone():
            raise PermissionError("Vínculo clínico indisponível")
        args=(principal_id, tenant_id, client_id, "appointments")
        cur.execute(SELECT_ALLOWED, args)
        if not cur.fetchone():
            cur.execute(SELECT_SELF_ALLOWED, args)
            if not cur.fetchone():
                raise PermissionError("Acesso ao agendamento não autorizado")
        cur.execute(
            """SELECT * FROM care_schedule_slots WHERE id=%s
               AND tenant_id=%s AND professional_user_id=%s FOR UPDATE""",
            (slot_id, tenant_id, professional_id))
        slot = cur.fetchone()
        if not slot:
            raise PermissionError("Horário indisponível")
        if action == "request":
            if slot["status"] != "open" or slot["starts_at_utc"] <= datetime.now(timezone.utc).replace(tzinfo=None):
                raise ValueError("Este horário não está mais disponível")
            _appointment_conflict(cur, tenant_id, professional_id,
                                  slot["starts_at_utc"], slot["ends_at_utc"])
            cur.execute(
                """UPDATE care_schedule_slots
                   SET status='pending',pending_user_id=%s,pending_client_id=%s,
                       requested_at=UTC_TIMESTAMP() WHERE id=%s""",
                (principal_id, client_id, slot_id))
        else:
            if (slot["status"] != "pending"
                    or slot["pending_user_id"] != principal_id
                    or slot["pending_client_id"] != client_id):
                raise PermissionError("Solicitação indisponível")
            cur.execute(
                """UPDATE care_schedule_slots
                   SET status='open',pending_user_id=NULL,pending_client_id=NULL,
                       requested_at=NULL WHERE id=%s""", (slot_id,))
        store.audit(cur, principal_id, tenant_id, "care_slot_" + action,
                    "care_slot", slot_id)
    return action
