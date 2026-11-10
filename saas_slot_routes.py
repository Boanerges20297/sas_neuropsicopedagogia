"""Verified patient appointment requests and clinician availability management."""
from uuid import uuid4
from flask import abort, flash, redirect, render_template, request, url_for, make_response
from flask_login import login_required, current_user
import saas_store as store
import saas_neurocore_store as nc
import saas_care_store as care
import saas_slot_booking as slots
from saas_routes import (check_csrf, csrf, practitioner_only, licensed_tenant,
                        is_saas_account)
from saas_care_routes import SERVICE_NAMES, MODALITY_NAMES

def _clinical():
    tenant, decision = licensed_tenant()
    if not decision.allowed:
        abort(403)
    return int(current_user.id), tenant

def _private(template, **context):
    page = make_response(render_template(template, **context))
    page.headers["Cache-Control"] = "private, no-store"
    page.headers["Referrer-Policy"] = "no-referrer"
    return page

def register_slot_routes(bp):
    @bp.route("/agenda/disponibilizar", methods=["POST"])
    @practitioner_only
    def publish_availability():
        uid, tenant = _clinical()
        check_csrf()
        try:
            count = slots.publish_slots(
                uid, tenant["id"], start_date=request.form.get("start_date", ""),
                end_date=request.form.get("end_date", ""),
                weekdays=request.form.getlist("weekday"),
                open_time=request.form.get("open_time", ""),
                close_time=request.form.get("close_time", ""),
                duration=request.form.get("duration", ""),
                gap=request.form.get("gap", "0"),
                service_type=request.form.get("service_type", ""),
                modality=request.form.get("modality", "in_person"))
        except (ValueError, PermissionError) as exc:
            flash(str(exc), "danger")
        else:
            flash(f"{count} horários disponibilizados.", "success")
        return redirect(url_for("saas.care_calendar"))

    @bp.route("/agenda/disponibilidade/<int:slot_id>/acao", methods=["POST"])
    @practitioner_only
    def availability_action(slot_id):
        uid, tenant = _clinical()
        check_csrf()
        action = request.form.get("action", "")
        try:
            slots.change_slot(
                uid, tenant["id"], slot_id, action=action,
                local_start=request.form.get("local_start"),
                duration=request.form.get("duration"),
                service_type=request.form.get("service_type"),
                modality=request.form.get("modality"))
        except (ValueError, PermissionError) as exc:
            flash(str(exc), "danger")
        else:
            flash({"edit":"Horário atualizado.","close":"Horário retirado.",
                   "accept":"Solicitação confirmada; consulta agendada.",
                   "reject":"Solicitação recusada; horário liberado."}[action],
                  "success")
        return redirect(url_for("saas.care_calendar"))

    @bp.route("/agenda/marcar", methods=["POST"])
    @practitioner_only
    def schedule_patient_from_calendar():
        uid, tenant = _clinical()
        check_csrf()
        try:
            client_id = int(request.form.get("client_id", ""))
        except (ValueError, TypeError):
            flash("Selecione um paciente.", "danger")
            return redirect(url_for("saas.care_calendar"))
        if not nc.scoped_client(uid, tenant["id"], client_id):
            abort(404)
        try:
            care.create_appointment(
                uid, tenant["id"], client_id,
                local_start=request.form.get("local_start", ""),
                duration=request.form.get("duration", ""),
                service_type=request.form.get("service_type", ""),
                modality=request.form.get("modality", ""),
                request_id=request.form.get("request_id", ""))
        except ValueError as exc:
            flash(str(exc), "danger")
        else:
            flash("Consulta agendada.", "success")
        return redirect(url_for("saas.care_calendar"))

    @bp.route("/agenda/consultas/<int:appointment_id>/editar", methods=["POST"])
    @practitioner_only
    def reschedule_calendar_appointment(appointment_id):
        uid, tenant = _clinical()
        check_csrf()
        try:
            client_id = int(request.form.get("client_id", ""))
        except (ValueError, TypeError):
            abort(400)
        if not nc.scoped_client(uid, tenant["id"], client_id):
            abort(404)
        try:
            care.reschedule_appointment(
                uid, tenant["id"], client_id, appointment_id,
                local_start=request.form.get("local_start"),
                duration=request.form.get("duration"),
                service_type=request.form.get("service_type"),
                modality=request.form.get("modality"))
        except (ValueError, PermissionError) as exc:
            flash(str(exc), "danger")
        else:
            flash("Consulta atualizada. Histórico preservado.", "success")
        return redirect(url_for("saas.care_calendar"))

    @bp.route("/agenda/consultas/<int:appointment_id>/cancelar", methods=["POST"])
    @practitioner_only
    def cancel_calendar_appointment(appointment_id):
        uid, tenant = _clinical()
        check_csrf()
        try:
            client_id = int(request.form.get("client_id", ""))
        except (TypeError, ValueError):
            abort(400)
        if not nc.scoped_client(uid, tenant["id"], client_id):
            abort(404)
        try:
            care.transition_appointment(uid, tenant["id"], client_id,
                                        appointment_id, "cancelled")
        except (ValueError, PermissionError) as exc:
            flash(str(exc), "danger")
        else:
            flash("Agendamento cancelado. Histórico mantido.", "success")
        return redirect(url_for("saas.care_calendar"))

    @bp.route("/minha-agenda")
    @login_required
    def patient_calendar():
        if not is_saas_account() or current_user.role != "patient":
            abort(403)
        principal = int(current_user.id)
        patients = slots.eligible_patients(principal)
        selected = None
        if patients:
            raw = request.args.get("client_id", "")
            if raw:
                if not raw.isdecimal():
                    abort(404)
                selected = next((p for p in patients if p["client_id"] == int(raw)), None)
                if not selected:
                    abort(404)
            else:
                selected = patients[0]
        available, requests = [], []
        if selected:
            args = (principal, selected["tenant_id"], selected["client_id"],
                    selected["professional_user_id"])
            available = slots.available_for_client(*args)
            requests = slots.patient_requests(*args)
        return _private(
            "saas_patient_calendar.html", patients=patients, selected=selected,
            available=available, patient_requests=requests,
            service_names=SERVICE_NAMES, modality_names=MODALITY_NAMES,
            csrf_token=csrf())

    @bp.route("/minha-agenda/<int:tenant_id>/<int:client_id>/<int:slot_id>/acao",
              methods=["POST"])
    @login_required
    def patient_calendar_action(tenant_id, client_id, slot_id):
        if not is_saas_account() or current_user.role != "patient":
            abort(403)
        check_csrf()
        principal = int(current_user.id)
        patient = next((p for p in slots.eligible_patients(principal)
                        if p["tenant_id"] == tenant_id and p["client_id"] == client_id), None)
        if not patient:
            abort(404)
        try:
            action = slots.patient_slot_action(
                principal, tenant_id, client_id, patient["professional_user_id"],
                slot_id, request.form.get("action", ""))
        except ValueError as exc:
            flash(str(exc), "danger")
        except PermissionError:
            abort(404)
        else:
            flash("Solicitação enviada. Aguarde a confirmação do profissional."
                  if action == "request" else "Solicitação cancelada.", "success")
        return redirect(url_for("saas.patient_calendar", client_id=client_id))
