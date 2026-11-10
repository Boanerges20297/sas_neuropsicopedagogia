"""Private management actions for the clinician's own patient records."""
from flask import abort, flash, make_response, redirect, render_template, request, url_for
from flask_login import current_user

import saas_patient_management as management
from saas_routes import licensed_tenant, practitioner_only, check_csrf, csrf


def register_patient_management_routes(bp):
    def scoped(client_id):
        tenant, decision = licensed_tenant()
        if not decision.allowed:
            abort(403)
        uid = int(current_user.id)
        patient = management.own_client(uid, tenant["id"], client_id)
        if not patient:
            abort(404)
        return uid, tenant, patient

    @bp.route("/pacientes/<int:client_id>/gerenciar")
    @practitioner_only
    def patient_manage(client_id):
        uid, tenant, patient = scoped(client_id)
        response = make_response(render_template(
            "saas_patient_manage.html", tenant=tenant, patient=patient,
            actions=management.ACTIONS.get(patient["status"], {}),
            states=management.STATES, csrf_token=csrf(),
        ))
        response.headers["Cache-Control"] = "private, no-store"
        return response

    @bp.route("/pacientes/<int:client_id>/gerenciar/dados", methods=["POST"])
    @practitioner_only
    def patient_manage_identity(client_id):
        uid, tenant, patient = scoped(client_id)
        check_csrf()
        try:
            management.update_identity(
                uid, tenant["id"], client_id, name=request.form.get("nome"),
                birth_date=request.form.get("birth_date"),
            )
        except ValueError as exc:
            flash(str(exc), "danger")
        except PermissionError:
            abort(404)
        else:
            flash("Dados do paciente atualizados.", "success")
        return redirect(url_for("saas.patient_manage", client_id=client_id))

    @bp.route("/pacientes/<int:client_id>/gerenciar/situacao", methods=["POST"])
    @practitioner_only
    def patient_manage_status(client_id):
        uid, tenant, patient = scoped(client_id)
        check_csrf()
        action = request.form.get("action", "")
        try:
            new_state = management.change_status(uid, tenant["id"], client_id, action)
        except ValueError as exc:
            flash(str(exc), "danger")
        except PermissionError:
            abort(404)
        else:
            flash("Situação atualizada: " + management.STATES[new_state] + ".", "success")
        return redirect(url_for("saas.patient_manage", client_id=client_id))

    @bp.route("/pacientes/<int:client_id>/instrumentos/<int:assessment_id>/gerenciar",
              methods=["POST"])
    @practitioner_only
    def patient_assessment_manage(client_id, assessment_id):
        uid, tenant, patient = scoped(client_id)
        check_csrf()
        import saas_assessment_management as assessment_management
        try:
            operation = assessment_management.manage_application(
                uid, tenant["id"], client_id, assessment_id,
                request.form.get("operation", ""),
            )
        except ValueError as exc:
            flash(str(exc), "danger")
        except PermissionError:
            abort(404)
        else:
            flash("Aplicação cancelada." if operation == "cancel"
                  else "Respostas zeradas. Aplicação reiniciada.", "success")
        return redirect(url_for("saas.clinical_assign_test", client_id=client_id))
