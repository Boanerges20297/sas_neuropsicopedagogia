"""Self-registration, owner-controlled workspaces and BTA license gate.

Mounted on the existing Flask application under /saas. MySQL is the
authoritative store here; no SQLite fallback or implicit BTA activation.
"""
from datetime import timedelta
import os
from functools import wraps
from hmac import compare_digest
import secrets
import time

import pymysql
from flask import Blueprint,abort,flash,redirect,render_template,request,session,url_for
from flask_login import current_user,login_required,login_user,logout_user

import saas_store as store
from saas_login_policy import valid_credential, requirement
from saas_account_access import can_admin, admin_permissions
from saas_admin_workspace import own_admin_workspace
from bta_license_client import LicenseDecision, resolve_tenant_license, activate_tenant_trial

bp=Blueprint("saas",__name__,url_prefix="/saas")


@bp.context_processor
def saas_workspace_navigation():
    available = False
    rights = dict(accounts=False, professionals=False, activations=False, clinic=False)
    if (is_saas_account() and current_user.is_practitioner()
            and not current_user.must_change_password):
        if current_user.is_admin():
            limits = getattr(current_user, "admin_rights", None)
            rights = {key: (current_user.role == "superadmin"
                            or limits is None or limits.get(key, False))
                      for key in rights}
            available = (rights["clinic"]
                         and bool(own_admin_workspace(current_user.id)))
        else:
            available = True
            rights["activations"] = True
    return {"has_saas_workspace": available,
            "can_manage_accounts": rights["accounts"],
            "can_manage_professionals": rights["professionals"],
            "can_manage_activations": rights["activations"],
            "smtp_setup_available": os.getenv("NEURO_SMTP_WEB_CONFIG_ENABLED", "false").lower()=="true"}


def is_saas_account():
    return (current_user.is_authenticated
            and isinstance(current_user._get_current_object(),store.SaaSUser)
            and bool(session.get("saas_auth")))


@bp.before_request
def guard_saas_identity():
    if request.endpoint in ("saas.login", "saas.register", "saas.health",
                            "saas.verify_email", "saas.resend_verification_email"):
        return None
    if current_user.is_authenticated and not is_saas_account():
        abort(403)
    if is_saas_account() and session.get("saas_temporary"):
        # Temporary devices never gain a 30-day trust token.
        # Expire their browser session after 15 minutes without activity.
        last = session.get("saas_last_seen")
        now = time.time()
        if (not isinstance(last, (float, int))
                or last > now + 5 or now - last > 15 * 60):
            logout_user()
            session.clear()
            return redirect(url_for("saas.login"))
        session["saas_last_seen"] = now
    if is_saas_account() and current_user.is_admin():
        # Existing admins also require a real MFA challenge. Legacy sessions
        # without step-up are invalid, even when their device was trusted.
        if current_user.mfa_enabled and session.get("saas_mfa_passed") is not True:
            logout_user()
            session.clear()
            return redirect(url_for("saas.login"))
        if (not current_user.mfa_enabled and not current_user.must_change_password
                and request.endpoint not in ("saas.mfa_settings", "saas.logout")):
            return redirect(url_for("saas.mfa_settings"))
    if (is_saas_account() and current_user.must_change_password
            and request.endpoint not in ("saas.profile", "saas.profile_password", "saas.logout")):
        return redirect(url_for("saas.profile"))
    if (is_saas_account() and not current_user.must_change_password
            and request.endpoint not in ("saas.mfa_settings", "saas.logout")):
        # Newly created accounts must complete MFA before entering the app.
        if current_user.mfa_required and not current_user.mfa_enabled:
            return redirect(url_for("saas.mfa_settings"))
    return None


def csrf():
    if "saas_csrf" not in session:
        session["saas_csrf"]=secrets.token_urlsafe(32)
    return session["saas_csrf"]


def check_csrf():
    a=request.form.get("csrf_token","")
    if not a or not compare_digest(a,session.get("saas_csrf","")):
        abort(400)


def admin_only(f):
    @wraps(f)
    @login_required
    def view(*args,**kwargs):
        if not is_saas_account() or not current_user.is_admin():
            abort(403)
        return f(*args,**kwargs)
    return view


def practitioner_only(f):
    @wraps(f)
    @login_required
    def view(*args,**kwargs):
        if not is_saas_account() or not current_user.is_practitioner():
            abort(403)
        return f(*args,**kwargs)
    return view


def licensed_tenant():
    # Administrative clinical access remains private to the admin-owned tenant.
    # Superadmins cannot browse records belonging to other professionals.
    if (is_saas_account() and current_user.is_admin()
            and not can_admin(int(current_user.id), "clinic")):
        abort(403)
    if not is_saas_account() or not current_user.is_practitioner():
        abort(403)
    tenant=(own_admin_workspace(current_user.id) if current_user.is_admin()
            else store.own_tenant(current_user.id))
    if not tenant:
        abort(403,"Espaço profissional não ativado")
    # Apenas identidades administrativas autenticadas no MySQL ficam isentas do BTA.
    # A isencao nao concede acesso a tenants de outros profissionais.
    decision = (LicenseDecision(status="exempt", reason="admin_permanent_access")
                if current_user.is_admin()
                else resolve_tenant_license(tenant["slug"], tenant["nome"]))
    return tenant,decision


@bp.route("/cadastro",methods=["GET","POST"])
def register():
    if is_saas_account():
        return redirect(url_for("saas.profile" if current_user.must_change_password else "saas.dashboard"))
    if current_user.is_authenticated:
        logout_user()
        session.clear()
    if request.method=="POST":
        check_csrf()
        if session.get("signup_last",0)>time.time()-6:
            abort(429)
        session["signup_last"]=time.time()
        name=request.form.get("nome","").strip()
        email=request.form.get("email","").strip().lower()
        profession=request.form.get("profession","")
        cpf=request.form.get("cpf","")
        birth_date=request.form.get("birth_date","")
        phone=request.form.get("phone","")
        registry=request.form.get("registry_code","").strip()
        password=request.form.get("senha","")
        confirmation=request.form.get("confirmar_senha","")
        if not valid_credential(password) or password!=confirmation:
            flash(requirement() + " Confirme a senha corretamente.","danger")
        else:
            try:
                from app import bcrypt
                store.register_professional(name,email,bcrypt.generate_password_hash(password).decode(),profession,registry,cpf,birth_date,phone)
                import saas_email_verification as mailcheck
                sent=mailcheck.request_registration_code(email)
                flash("Cadastro criado. Confirme o codigo enviado ao e-mail antes da aprovacao profissional."
                      if sent else
                      "Cadastro criado, mas o envio do codigo esta indisponivel. "
                      "Solicite reenvio na tela de verificacao quando o e-mail estiver configurado.",
                      "success" if sent else "warning")
                session["saas_verify_email"]=email
                return redirect(url_for("saas.verify_email"))
            except pymysql.err.IntegrityError:
                flash("E-mail ou CPF já cadastrado.","danger")
            except ValueError as exc:
                flash(str(exc),"danger")
    return render_template("saas_register.html",csrf_token=csrf())


@bp.route("/entrar",methods=["GET","POST"])
def login():
    if is_saas_account():
        return redirect(url_for("saas.profile" if current_user.must_change_password else "saas.dashboard"))
    if current_user.is_authenticated:
        logout_user()
        session.clear()
    if request.method=="POST":
        check_csrf()
        import saas_login_recovery as recovery
        email = request.form.get("email", "").strip().lower()
        if recovery.cooldown_remaining(email):
            flash("Muitas tentativas incorretas. Aguarde a pausa de segurança ou recupere sua senha.", "warning")
            return redirect(url_for("saas.request_password_reset"))
        from app import bcrypt
        row=store.user_by_email(email)
        password=request.form.get("senha","")
        if row and row["active"] and bcrypt.check_password_hash(row["password_hash"],password):
            if row.get("email_verification_pending",False):
                recovery.clear_failures(email)
                flash("Confirme o e-mail cadastrado antes do primeiro acesso.","warning")
                session["saas_verify_email"]=email
                return redirect(url_for("saas.verify_email"))
            import saas_mfa_store as mfa
            from saas_mfa_routes import TRUST_COOKIE
            trusted_device = False
            if row.get("mfa_enabled", False):
                # A verified 30-day trust token is valid for every role.
                # A different or unrecognized device must complete TOTP.
                token = request.cookies.get(TRUST_COOKIE)
                trusted_device = mfa.trusted(
                    int(row["id"]), token, request.headers.get("User-Agent"))
                if not trusted_device:
                    # Signed pending session, with no authenticated user yet.
                    session.clear()
                    session["saas_mfa_pending"] = int(row["id"])
                    session["saas_mfa_is_admin"] = row["global_role"] in ("admin", "superadmin")
                    session["saas_mfa_pending_at"] = time.time()
                    session["saas_mfa_attempts"] = 0
                    session["saas_csrf"] = secrets.token_urlsafe(32)
                    return redirect(url_for("saas.mfa_challenge"))
            user=store.SaaSUser(row)
            session.clear()
            login_user(user,fresh=True)
            session["saas_auth"]=True
            if trusted_device:
                # The trusted-device cookie was verified against the MFA DB.
                session["saas_mfa_passed"]=True
            else:
                # Without a trusted token, require a fresh login after idle.
                session["saas_temporary"]=True
                session["saas_last_seen"]=time.time()
            session["saas_csrf"]=secrets.token_urlsafe(32)
            recovery.clear_failures(email)
            return redirect(url_for("saas.profile" if user.must_change_password else "saas.dashboard"))
        if recovery.note_wrong_password(email):
            flash("Cinco tentativas incorretas. Para recuperar o acesso, solicite um código por e-mail.", "warning")
            return redirect(url_for("saas.request_password_reset"))
        flash("Credenciais inválidas ou cadastro aguardando aprovação.","danger")
    return render_template("login.html",saas_mode=True,csrf_token=csrf())


@bp.route("/sair",methods=["GET","POST"])
@login_required
def logout():
    logout_user()
    session.clear()
    return redirect(url_for("saas.login"))


@bp.route("/painel")
@login_required
def dashboard():
    if is_saas_account() and current_user.role == "patient":
        return redirect(url_for("saas.patient_calendar"))
    if not is_saas_account() or not current_user.is_practitioner():
        abort(403)
    tenant=(own_admin_workspace(current_user.id) if current_user.is_admin()
            else store.own_tenant(current_user.id))
    decision=(LicenseDecision(status="exempt",reason="admin_permanent_access")
              if current_user.is_admin() else
              resolve_tenant_license(tenant["slug"],tenant["nome"]) if tenant else None)
    global_stats=store.admin_global_stats() if current_user.is_admin() else None
    return render_template("saas_dashboard.html",tenant=tenant,license=decision,
                           stats=global_stats,csrf_token=csrf())


@bp.route("/meu-espaco/ativar", methods=["POST"])
@admin_only
def activate_admin_workspace():
    if not can_admin(int(current_user.id), "clinic"):
        abort(403)
    check_csrf()
    from saas_admin_workspace import activate_personal_admin_workspace
    try:
        activate_personal_admin_workspace(int(current_user.id))
        flash("Seu espaço clínico privado está disponível.", "success")
    except (ValueError, PermissionError) as exc:
        flash(str(exc), "danger")
    return redirect(url_for("saas.dashboard"))


@bp.route("/profissionais")
@admin_only
def professionals():
    if not can_admin(int(current_user.id), "professionals"):
        abort(403)
    return render_template("saas_professionals.html",pending=store.pending_professionals(),
                           professionals=store.list_professionals(),csrf_token=csrf())


@bp.route("/profissionais/<int:professional_id>/decidir",methods=["POST"])
@admin_only
def decide_professional(professional_id):
    if not can_admin(int(current_user.id), "professionals"):
        abort(403)
    check_csrf()
    decision=request.form.get("decision")
    if decision not in ("approve","reject"):
        abort(400)
    try:
        store.approve_professional(int(current_user.id),professional_id,
                                   request.form.get("reason",""),decision=="approve")
        if decision=="approve" and request.form.get("activate_trial")=="on":
            result=_attempt_trial(professional_id)
            flash("Cadastro aprovado. "+result, "success" if result.startswith("Trial ativo") else "warning")
        else:
            flash("Decisão registrada com auditoria. A licença BTA é verificada separadamente.","success")
    except (ValueError,PermissionError) as exc:
        flash(str(exc),"danger")
    return redirect(url_for("saas.professionals"))


def _attempt_trial(professional_id):
    tenant=store.own_tenant(professional_id)
    if not tenant:
        return "Espaço profissional não encontrado; nenhuma licença emitida."
    result=activate_tenant_trial(tenant["slug"],tenant["nome"])
    if result.status=="activated":
        message="Trial ativo na BTA até "+(result.expires_at or "prazo retornado pela BTA")
    else:
        message="Trial não emitido: "+(result.reason or result.status)
    with store.transaction() as cur:
        store.audit(cur,int(current_user.id),tenant["id"],"trial_"+result.status,
                    "tenant",tenant["id"],"allowed" if result.status=="activated" else "failed",
                    result.reason or result.expires_at or result.status)
    return message


@bp.route("/profissionais/<int:professional_id>/trial",methods=["POST"])
@admin_only
def trial_professional(professional_id):
    if not can_admin(int(current_user.id), "professionals"):
        abort(403)
    check_csrf()
    tenant=store.own_tenant(professional_id)
    if not tenant or not store.get_user(professional_id):
        abort(404)
    result=_attempt_trial(professional_id)
    flash(result,"success" if result.startswith("Trial ativo") else "warning")
    return redirect(url_for("saas.professionals"))


@bp.route("/pacientes", methods=["GET"])
@practitioner_only
def patients():
    tenant, license = licensed_tenant()
    if not license.allowed:
        return render_template("saas_status.html",
                               message="Acesso profissional aguardando licença BTA válida. "+
                                       "Seu cadastro continua preservado."), 403
    from uuid import uuid4
    clients = store.list_clients(int(current_user.id), tenant["id"])
    for patient in clients:
        patient["start_request_id"] = str(uuid4())
    summary = {
        "active": sum(p["status"] == "active" for p in clients),
        "today": sum(bool(p.get("today_at")) for p in clients if p["status"] == "active"),
        "portal": sum(p.get("portal_request_status") == "pending" for p in clients),
        "total": len(clients),
    }
    from flask import make_response
    response = make_response(render_template(
        "saas_patients.html", tenant=tenant, clients=clients,
        summary=summary, csrf_token=csrf()))
    response.headers["Cache-Control"] = "private, no-store"
    return response


@bp.route("/pacientes", methods=["POST"])  # Compatibility with older forms.
@bp.route("/pacientes/novo", methods=["GET", "POST"])
@practitioner_only
def patient_new():
    tenant, license = licensed_tenant()
    if not license.allowed:
        return render_template("saas_status.html",
                               message="Acesso profissional aguardando licença BTA válida. "+
                                       "Seu cadastro continua preservado."), 403
    if request.method == "POST":
        check_csrf()
        try:
            from saas_patient_intake import register_intake
            access = request.form.get("portal_access_mode", "later")
            register_intake(
                int(current_user.id), tenant["id"],
                mode=request.form.get("representation_mode", ""),
                name=request.form.get("nome", ""),
                birth_date=request.form.get("birth_date", ""),
                initial_report=request.form.get("initial_report", ""),
                guardian_name=request.form.get("guardian_name", ""),
                guardian_email=request.form.get("guardian_email", ""),
                email=request.form.get("email", ""),
                portal_access_mode=access,
            )
            if access == "prepare":
                flash("Paciente cadastrado. Solicitação de acesso ao portal registrada; "+
                      "a conta ainda exige verificação e ativação.", "success")
            else:
                flash("Paciente registrado no seu espaço profissional.", "success")
            return redirect(url_for("saas.patients"))
        except ValueError as exc:
            flash(str(exc), "danger")
    from flask import make_response
    response = make_response(render_template(
        "saas_patient_new.html", tenant=tenant, csrf_token=csrf()))
    response.headers["Cache-Control"] = "private, no-store"
    return response


@bp.route("/testes")
@practitioner_only
def tests():
    tenant,license=licensed_tenant()
    if not license.allowed:
        return render_template("saas_status.html",
                               message="Instrumentos indisponíveis sem licença BTA válida."),403
    return render_template("saas_tests.html",tenant=tenant,
                           tests=store.list_visible_tests(current_user.id,tenant["id"]))


from saas_profile_routes import register_profile_routes
register_profile_routes(bp)
from saas_test_governance_routes import register_test_governance_routes
register_test_governance_routes(bp)

from saas_neurocore_routes import register_neurocore_routes
register_neurocore_routes(bp)

from saas_care_routes import register_care_routes
register_care_routes(bp)
from saas_slot_routes import register_slot_routes
register_slot_routes(bp)

from saas_clinical_routes import register_clinical_routes
register_clinical_routes(bp)

from saas_patient_intake_routes import register_patient_intake_routes
register_patient_intake_routes(bp)

# A restricted POST route only: no public patient portal or automatic access.
import saas_portal_activation_routes
import saas_account_admin_routes
from saas_login_recovery_routes import register_recovery_routes
register_recovery_routes(bp)
from saas_email_routes import register_email_routes
register_email_routes(bp)

from saas_mfa_routes import register_mfa_routes
register_mfa_routes(bp)

# Superadmin-only credential setup lives inside the SaaS Blueprint.
from saas_smtp_admin_routes import register_smtp_routes
register_smtp_routes(bp)


@bp.route("/saude")
def health():
    from flask import jsonify
    try:
        store.one("SELECT 1 AS ok")
        # Fail release smoke if the NeuroCore additive schema was not applied.
        store.one("SELECT 1 FROM neurocore_evidence_reviews LIMIT 1")
        store.one("SELECT 1 FROM care_appointments LIMIT 1")
        store.one("SELECT 1 FROM care_schedule_slots LIMIT 1")
        store.one("SELECT 1 FROM care_encounters LIMIT 1")
        store.one("SELECT 1 FROM care_portal_grants LIMIT 1")
        store.one("SELECT 1 FROM care_patient_intakes LIMIT 1")
        store.one("SELECT 1 FROM care_portal_self_links LIMIT 1")
        store.one("SELECT 1 FROM care_portal_self_grants LIMIT 1")
        store.one("SELECT 1 FROM care_portal_consents LIMIT 1")
        store.one("SELECT 1 FROM care_portal_client_activations LIMIT 1")
        store.one("SELECT 1 FROM saas_account_rights LIMIT 1")
        store.one("SELECT 1 FROM saas_mfa_factors LIMIT 1")
        store.one("SELECT 1 FROM saas_mfa_recovery_codes LIMIT 1")
        store.one("SELECT 1 FROM saas_mfa_trusted_devices LIMIT 1")
        # Registration and login require these tables. Never report ready
        # before migrations reached the live production MySQL instance.
        store.one("SELECT 1 FROM saas_email_verifications LIMIT 1")
        store.one("SELECT 1 FROM saas_email_challenges LIMIT 1")
        return jsonify({"database":"mysql","status":"ready"})
    except (pymysql.MySQLError,RuntimeError):
        return jsonify({"database":"mysql","status":"not_ready"}),503
