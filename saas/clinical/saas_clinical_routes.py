"""Clinical professional routes; portal questionnaire access remains disabled."""
from uuid import uuid4

from flask import abort, flash, jsonify, make_response, redirect, render_template, request, url_for
from flask_login import current_user

from saas.core import saas_store as store
from saas.neurocore import saas_neurocore_store as nc
from saas.patients import saas_patient_intake as intake
from saas.clinical import saas_clinical_flow as clinical
from saas.clinical import saas_assessment_flow as assessments
from neurocore.assessment_feedback import received_test_feedback
from neurocore.indicator_engine import identify_indicators
from neurocore.feedback_learning import annotate_report, select_signal
from neurocore.record_context import read_owned_record
from saas.core.saas_routes import check_csrf, csrf, licensed_tenant, practitioner_only
from neurocore import feedback_store as nc_learning


def _own_space():
    tenant, license_result = licensed_tenant()
    if not license_result.allowed:
        abort(403)
    return int(current_user.id), tenant


def _own_patient(uid, tenant, client_id):
    client = nc.scoped_client(uid, tenant["id"], client_id)
    if not client:
        abort(404)
    return client


def _private(template, **kwargs):
    response = make_response(render_template(template, **kwargs))
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


def _json_private(payload, status=200):
    response = make_response(jsonify(payload), status)
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


def _open_hypotheses(records):
    """Show only the latest unresolved state for each longitudinal condition."""
    seen = set()
    pending = []
    for record in records:
        key = ((record["label"] or "").strip().casefold(),
               (record.get("code") or "").strip().upper())
        if key in seen:
            continue
        seen.add(key)
        if record["certainty"] == "hypothesis":
            pending.append(record)
    return pending


def register_clinical_routes(bp):
    @bp.route("/atendimentos")
    @practitioner_only
    def clinical_dashboard():
        uid, tenant = _own_space()
        period = request.args.get("period", "month")
        anchor = request.args.get("anchor", "")
        try:
            stats = clinical.professional_dashboard(uid, tenant["id"], period, anchor)
        except ValueError:
            abort(400)
        return _private(
            "saas_clinical_dashboard.html", tenant=tenant, stats=stats,
            clients=store.list_clients(uid, tenant["id"]),
            encounters=clinical.list_encounters(uid, tenant["id"], limit=15),
            request_id=str(uuid4()), csrf_token=csrf())

    @bp.route("/atendimentos/iniciar", methods=["POST"])
    @practitioner_only
    def clinical_start():
        uid, tenant = _own_space()
        check_csrf()
        try:
            client_id = int(request.form.get("client_id", ""))
        except (TypeError, ValueError):
            abort(400)
        _own_patient(uid, tenant, client_id)
        try:
            encounter_id = clinical.start_encounter(
                uid, tenant["id"], client_id, request.form.get("request_id", ""))
        except ValueError as exc:
            flash(str(exc), "danger")
            return redirect(url_for("saas.clinical_dashboard"))
        return redirect(url_for("saas.clinical_encounter",
                                client_id=client_id, encounter_id=encounter_id))

    @bp.route("/pacientes/<int:client_id>/atendimentos/<int:encounter_id>")
    @practitioner_only
    def clinical_encounter(client_id, encounter_id):
        uid, tenant = _own_space()
        client = _own_patient(uid, tenant, client_id)
        encounter = clinical.scoped_encounter(uid, tenant["id"], client_id, encounter_id)
        if not encounter:
            abort(404)
        diagnoses = clinical.list_diagnoses(uid, tenant["id"], client_id, encounter_id)
        return _private(
            "saas_clinical_encounter.html", tenant=tenant, client=client,
            encounter=encounter,
            intake=intake.scoped_summary(uid, tenant["id"], client_id),
            note=clinical.latest_note(uid, tenant["id"], client_id, encounter_id),
            diagnoses=diagnoses, open_hypotheses=_open_hypotheses(diagnoses),
            patient_encounters=clinical.list_encounters(
                uid, tenant["id"], client_id=client_id, limit=20),
            assigned=assessments.list_for_patient(uid, tenant["id"], client_id),
            csrf_token=csrf())

    @bp.route("/pacientes/<int:client_id>/atendimentos/<int:encounter_id>/nota",
              methods=["POST"])
    @practitioner_only
    def clinical_save_note(client_id, encounter_id):
        uid, tenant = _own_space()
        _own_patient(uid, tenant, client_id)
        check_csrf()
        wants_json = request.accept_mimetypes.best == "application/json"
        try:
            revision = clinical.save_note(
                uid, tenant["id"], client_id, encounter_id,
                request.form.get("html", ""),
                request.form.get("revision", ""))
            if wants_json:
                return _json_private({"ok": True, "revision": revision})
            flash("Evolução salva com histórico de versões.", "success")
        except PermissionError:
            abort(404)
        except ValueError as exc:
            if wants_json:
                return _json_private({"ok": False, "message": str(exc)},
                                     409 if "outra aba" in str(exc) else 400)
            flash(str(exc), "danger")
        next_id = request.form.get("next_assessment", "").strip()
        if next_id.isdecimal():
            instance = assessments.scoped_assessment(
                uid, tenant["id"], client_id, int(next_id))
            if instance and instance.get("encounter_id") == encounter_id:
                return redirect(url_for("saas.clinical_questionnaire",
                                        client_id=client_id, assessment_id=int(next_id)))
        return redirect(url_for("saas.clinical_encounter",
                                client_id=client_id, encounter_id=encounter_id))

    @bp.route("/pacientes/<int:client_id>/atendimentos/<int:encounter_id>/diagnosticos",
              methods=["POST"])
    @practitioner_only
    def clinical_record_diagnosis(client_id, encounter_id):
        uid, tenant = _own_space()
        _own_patient(uid, tenant, client_id)
        check_csrf()
        try:
            clinical.record_diagnosis(
                uid, tenant["id"], client_id, encounter_id,
                request.form.get("label"), request.form.get("code"),
                request.form.get("certainty"),
                hypothesis_id=request.form.get("hypothesis_id"))
            flash("Hipótese diagnóstica registrada para acompanhamento." if
                  request.form.get("certainty") == "hypothesis" else
                  "Evolução da classificação clínica registrada.", "success")
        except PermissionError:
            abort(404)
        except ValueError as exc:
            flash(str(exc), "danger")
        return redirect(url_for("saas.clinical_encounter",
                                client_id=client_id, encounter_id=encounter_id)
                        + "#hipoteses-diagnosticas")

    @bp.route("/pacientes/<int:client_id>/instrumentos", methods=["GET", "POST"])
    @practitioner_only
    def clinical_assign_test(client_id):
        uid, tenant = _own_space()
        client = _own_patient(uid, tenant, client_id)
        encounter_id = request.values.get("encounter_id", "")
        selected_encounter = None
        if encounter_id:
            if not encounter_id.isdecimal():
                abort(400)
            selected_encounter = clinical.scoped_encounter(
                uid, tenant["id"], client_id, int(encounter_id))
            if not selected_encounter:
                abort(404)
        if request.method == "POST":
            check_csrf()
            try:
                version_id = int(request.form.get("version_id", ""))
                assessment_id = assessments.create_assessment(
                    uid, tenant["id"], client_id, version_id,
                    request.form.get("mode", ""),
                    int(encounter_id) if encounter_id else None)
                flash("Instrumento atribuído ao paciente.", "success")
                return redirect(url_for("saas.clinical_questionnaire",
                                        client_id=client_id,
                                        assessment_id=assessment_id))
            except (TypeError, ValueError) as exc:
                flash(str(exc) if isinstance(exc, ValueError) else
                      "Selecione um instrumento válido.", "danger")
            except PermissionError:
                abort(404)
        return _private(
            "saas_clinical_assign.html", tenant=tenant, client=client,
            encounter=selected_encounter, available=assessments.list_available(
                uid, tenant["id"]),
            assigned=assessments.list_for_patient(uid, tenant["id"], client_id),
            csrf_token=csrf())

    @bp.route("/pacientes/<int:client_id>/instrumentos/<int:assessment_id>/neurocore",
              methods=["GET", "POST"])
    @practitioner_only
    def clinical_neurocore_feedback(client_id, assessment_id):
        """Optional, read-only feedback after receiving a completed instrument."""
        from neurocore.engine import load_knowledge
        uid, tenant = _own_space()
        client = _own_patient(uid, tenant, client_id)
        item = assessments.scoped_assessment(
            uid, tenant["id"], client_id, assessment_id)
        if not item:
            abort(404)
        if item["status"] not in ("submitted", "reviewed"):
            abort(409)
        configured = item["definition"].get("neurocore_topic")
        topic = request.values.get("topic", "").strip() or configured
        topics = load_knowledge()["topics"]
        if topic and topic not in topics:
            abort(400)
        if configured and topic and topic != configured:
            abort(400)
        record_context = None
        action = request.form.get("action") if request.method == "POST" else None
        if request.method == "POST":
            check_csrf()
            if action not in ("read_record", "feedback_indicator") or not topic:
                abort(400)
            if action == "read_record" or request.form.get("with_record") == "1":
                record_context = read_owned_record(uid, tenant["id"], client_id)
        feedback = None
        indicator_report = None
        if topic:
            saved = assessments.read_answers(
                uid, tenant["id"], client_id, assessment_id)
            feedback = received_test_feedback(item["definition"], saved, topic)
            indicator_report = identify_indicators(
                topic, definition=item["definition"], answers=saved,
                record=record_context)
            annotate_report(indicator_report, assessment_id=assessment_id)
            if action == "feedback_indicator":
                try:
                    signal = select_signal(
                        indicator_report, request.form.get("domain_key", ""),
                        request.form.get("signal_key", ""))
                    nc_learning.save_feedback(
                        uid, tenant["id"], client_id, topic, signal,
                        request.form.get("verdict", ""),
                        indicator_report["engine_version"],
                        assessment_id=assessment_id)
                except ValueError:
                    abort(400)
                except PermissionError:
                    abort(404)
                flash("Sua avaliação do indicador foi registrada.", "success")
            annotate_report(
                indicator_report, assessment_id=assessment_id,
                existing=nc_learning.list_feedback(
                    uid, tenant["id"], client_id, topic))
        return _private(
            "saas_clinical_neurocore_feedback.html", tenant=tenant,
            client=client, assessment=item, feedback=feedback,
            selected_topic=topic, topics=topics, record_context=record_context,
            indicator_report=indicator_report, csrf_token=csrf())

    @bp.route("/pacientes/<int:client_id>/instrumentos/<int:assessment_id>",
              methods=["GET", "POST"])
    @practitioner_only
    def clinical_questionnaire(client_id, assessment_id):
        uid, tenant = _own_space()
        client = _own_patient(uid, tenant, client_id)
        item = assessments.scoped_assessment(
            uid, tenant["id"], client_id, assessment_id)
        if not item:
            abort(404)
        if request.method == "POST":
            check_csrf()
            try:
                answers = {}
                for q in item["definition"]["questions"]:
                    key = "answer_" + q["key"]
                    if q["type"] == "multiple":
                        answers[q["key"]] = request.form.getlist(key)
                    elif q["type"] == "number":
                        raw = request.form.get(key, "").strip()
                        answers[q["key"]] = float(raw) if raw else None
                    else:
                        answers[q["key"]] = request.form.get(key, "")
                submitted = request.form.get("action") == "submit"
                if request.form.get("action") not in ("save", "submit"):
                    abort(400)
                assessments.save_answers(
                    uid, tenant["id"], client_id, assessment_id,
                    answers, request.form.get("revision"), submit=submitted)
                flash("Respostas enviadas para revisão." if submitted else
                      "Respostas salvas como rascunho.", "success")
                return redirect(url_for("saas.clinical_questionnaire",
                                        client_id=client_id, assessment_id=assessment_id))
            except PermissionError:
                abort(403)
            except ValueError as exc:
                flash(str(exc), "danger")
        saved = assessments.read_answers(
            uid, tenant["id"], client_id, assessment_id)
        encounter = None
        note = None
        if item.get("encounter_id"):
            encounter = clinical.scoped_encounter(
                uid, tenant["id"], client_id, item["encounter_id"])
            if encounter:
                note = clinical.latest_note(
                    uid, tenant["id"], client_id, item["encounter_id"])
        return _private(
            "saas_clinical_questionnaire.html", tenant=tenant, client=client,
            assessment=item, answers=saved, encounter=encounter, note=note,
            professional_score=(assessments.professional_score(item["definition"], saved)
                                if item["status"] in ("submitted", "reviewed") else None),
            csrf_token=csrf())
