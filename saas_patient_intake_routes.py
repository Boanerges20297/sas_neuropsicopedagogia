"""Professional-only initial patient intake, never a public portal endpoint."""
from flask import abort, render_template, make_response
from flask_login import current_user

import saas_neurocore_store as nc
import saas_patient_intake as intake
from saas_routes import licensed_tenant, practitioner_only


def register_patient_intake_routes(bp):
    @bp.route("/pacientes/<int:client_id>/dados-iniciais")
    @practitioner_only
    def patient_intake_details(client_id):
        tenant, decision = licensed_tenant()
        if not decision.allowed:
            abort(403)
        uid = int(current_user.id)
        client = nc.scoped_client(uid, tenant["id"], client_id)
        if not client:
            abort(404)
        response = make_response(render_template(
            "saas_patient_intake_details.html",
            tenant=tenant, client=client,
            intake=intake.scoped_summary(uid, tenant["id"], client_id),
        ))
        response.headers["Cache-Control"] = "private, no-store"
        return response
