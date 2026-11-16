"""TEA/TDAH clinical evidence organization — no diagnosis, no scoring."""
from flask import abort, flash, make_response, redirect, render_template, request, url_for
from uuid import uuid4
from flask_login import current_user, login_required

from neurocore import evaluate_evidence
from neurocore.engine import load_knowledge
from neurocore.indicator_engine import identify_indicators
from neurocore.feedback_learning import annotate_report, select_signal
from neurocore.record_context import read_owned_record
from saas.core.saas_routes import licensed_tenant, practitioner_only, check_csrf, csrf
from saas.neurocore import saas_neurocore_store as nc_store
from neurocore import feedback_store as nc_learning


def register_neurocore_routes(bp):
    @bp.route("/pacientes/<int:client_id>", methods=["GET"])
    @practitioner_only
    def patient_workspace(client_id):
        tenant, license_decision = licensed_tenant()
        if not license_decision.allowed:
            abort(403)
        client = nc_store.scoped_client(int(current_user.id), tenant["id"], client_id)
        if not client:
            abort(404)
        return render_template(
            "saas_patient_workspace.html", tenant=tenant, client=client,
            reviews=nc_store.list_reviews(int(current_user.id), tenant["id"], client_id),
            topics=load_knowledge()["topics"],
            csrf_token=csrf(), start_request_id=str(uuid4()),
        )

    @bp.route("/pacientes/<int:client_id>/neurocore/<topic>", methods=["GET", "POST"])
    @practitioner_only
    def neurocore_review(client_id, topic):
        topics = load_knowledge()["topics"]
        if topic not in topics:
            abort(404)
        tenant, license_decision = licensed_tenant()
        if not license_decision.allowed:
            abort(403)
        user_id = int(current_user.id)
        client = nc_store.scoped_client(user_id, tenant["id"], client_id)
        if not client:
            abort(404)
        fields = topics[topic]["review_fields"]
        record_context = None
        action = request.form.get("action") if request.method == "POST" else None
        if request.method == "POST":
            check_csrf()
        if action in ("read_record", "feedback_indicator"):
            try:
                record_context = read_owned_record(user_id, tenant["id"], client_id)
            except PermissionError:
                abort(404)
        elif request.method == "POST":
            if action not in (None, "save_documentation"):
                abort(400)
            evidence = {}
            for field in fields:
                key = field["key"]
                status = request.form.get("status_" + key, "nao_documentado")
                if status == "nao_aplicavel":
                    evidence[key] = {
                        "status": status,
                        "justificativa": request.form.get("reason_" + key, "").strip()[:400],
                    }
                else:
                    evidence[key] = status
            try:
                checked = evaluate_evidence(topic, evidence)
                nc_store.save_review(
                    user_id, tenant["id"], client_id, topic, evidence, checked["version"])
            except (ValueError, PermissionError) as exc:
                flash(str(exc), "danger")
                abort(400)
            flash("Roteiro documental salvo. Nenhuma conclusão diagnóstica foi gerada.", "success")
            return redirect(url_for("saas.neurocore_review", client_id=client_id, topic=topic))
        row = nc_store.get_review(user_id, tenant["id"], client_id, topic)
        values = row["evidence_json"] if row else {}
        summary = evaluate_evidence(topic, values)
        indicator_report = (identify_indicators(topic, record=record_context)
                            if record_context is not None else None)
        if indicator_report is not None:
            annotate_report(indicator_report)
            if action == "feedback_indicator":
                try:
                    signal = select_signal(
                        indicator_report, request.form.get("domain_key", ""),
                        request.form.get("signal_key", ""))
                    nc_learning.save_feedback(
                        user_id, tenant["id"], client_id, topic, signal,
                        request.form.get("verdict", ""),
                        indicator_report["engine_version"])
                except ValueError:
                    abort(400)
                except PermissionError:
                    abort(404)
                flash("Sua avaliação do indicador foi registrada.", "success")
            annotate_report(indicator_report, existing=nc_learning.list_feedback(
                user_id, tenant["id"], client_id, topic))
        from saas.core.saas_routes import csrf
        result = make_response(render_template(
            "saas_neurocore_review.html",
            tenant=tenant, client=client, fields=fields, topic=topic,
            topic_name=topics[topic]["name"], values=values,
            summary=summary, csrf_token=csrf(), saved=row,
            record_context=record_context, indicator_report=indicator_report,
        ))
        result.headers["Cache-Control"] = "private, no-store"
        result.headers["Referrer-Policy"] = "no-referrer"
        return result
