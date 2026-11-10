"""SaaS practitioner-side scheduling routes. The client portal is NOT exposed."""
from uuid import uuid4

from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user

import saas_care_store as care
import saas_neurocore_store as nc
from saas_routes import licensed_tenant, practitioner_only, check_csrf, csrf

SERVICE_NAMES = {
    "initial": "Avaliação inicial", "follow_up": "Acompanhamento",
    "assessment": "Aplicação de instrumento", "feedback": "Devolutiva",
}
MODALITY_NAMES = {"in_person": "Presencial", "remote": "Remoto"}
STATUS_NAMES = {
    "scheduled": "Agendado", "confirmed": "Confirmado",
    "completed": "Realizado", "cancelled": "Cancelado",
    "no_show": "Não compareceu",
}


def register_care_routes(bp):
    @bp.route("/agenda")
    @practitioner_only
    def care_calendar():
        tenant, decision = licensed_tenant()
        if not decision.allowed:
            abort(403)
        from flask import make_response
        from saas_slot_booking import list_slots
        from saas_store import list_clients
        uid = int(current_user.id)
        response = make_response(render_template(
            "saas_care_calendar.html", tenant=tenant,
            appointments=care.list_calendar(uid, tenant["id"]),
            slots=list_slots(uid, tenant["id"]),
            clients=list_clients(uid, tenant["id"]),
            service_names=SERVICE_NAMES, status_names=STATUS_NAMES,
            modality_names=MODALITY_NAMES, csrf_token=csrf(),
            request_id=str(uuid4()),
        ))
        response.headers["Cache-Control"] = "private, no-store"
        return response

    @bp.route("/pacientes/<int:client_id>/agenda", methods=["GET", "POST"])
    @practitioner_only
    def client_appointments(client_id):
        tenant, decision = licensed_tenant()
        if not decision.allowed:
            abort(403)
        uid = int(current_user.id)
        client = nc.scoped_client(uid, tenant["id"], client_id)
        if not client:
            abort(404)
        if request.method == "POST":
            check_csrf()
            try:
                care.create_appointment(
                    uid, tenant["id"], client_id,
                    local_start=request.form.get("local_start", ""),
                    duration=request.form.get("duration", ""),
                    service_type=request.form.get("service_type", ""),
                    modality=request.form.get("modality", ""),
                    request_id=request.form.get("request_id", ""),
                )
            except ValueError as exc:
                flash(str(exc), "danger")
            except PermissionError:
                abort(404)
            else:
                flash("Agendamento registrado.", "success")
                return redirect(url_for("saas.client_appointments", client_id=client_id))
        return render_template(
            "saas_care_appointments.html", tenant=tenant, client=client,
            appointments=care.list_client_appointments(uid, tenant["id"], client_id),
            service_names=SERVICE_NAMES, status_names=STATUS_NAMES,
            modality_names=MODALITY_NAMES, csrf_token=csrf(),
            request_id=str(uuid4()),
        )

    @bp.route("/pacientes/<int:client_id>/agenda/<int:appointment_id>/acao",
              methods=["POST"])
    @practitioner_only
    def appointment_action(client_id, appointment_id):
        tenant, decision = licensed_tenant()
        if not decision.allowed:
            abort(403)
        uid = int(current_user.id)
        if not nc.scoped_client(uid, tenant["id"], client_id):
            abort(404)
        check_csrf()
        target = request.form.get("target", "")
        try:
            care.transition_appointment(uid, tenant["id"], client_id, appointment_id, target)
        except ValueError as exc:
            flash(str(exc), "danger")
        except PermissionError:
            abort(404)
        else:
            flash("Situação do agendamento atualizada.", "success")
        return redirect(url_for("saas.client_appointments", client_id=client_id))
