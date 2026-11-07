"""Self-registration, owner-controlled workspaces and BTA license gate.

Mounted on the existing Flask application under /saas. MySQL is the
authoritative store here; no SQLite fallback or implicit BTA activation.
"""
from datetime import timedelta
from functools import wraps
from hmac import compare_digest
import secrets
import time

import pymysql
from flask import Blueprint,abort,flash,redirect,render_template,request,session,url_for
from flask_login import current_user,login_required,login_user,logout_user

import saas_store as store
from saas_admin_workspace import own_admin_workspace
from bta_license_client import LicenseDecision, resolve_tenant_license, activate_tenant_trial

bp=Blueprint("saas",__name__,url_prefix="/saas")


@bp.context_processor
def saas_workspace_navigation():
    available = False
    if (is_saas_account() and current_user.is_practitioner()
            and not current_user.must_change_password):
        available = (bool(own_admin_workspace(current_user.id))
                     if current_user.is_admin() else True)
    return {"has_saas_workspace": available}


def is_saas_account():
    return (current_user.is_authenticated
            and isinstance(current_user._get_current_object(),store.SaaSUser)
            and bool(session.get("saas_auth")))


@bp.before_request
def guard_saas_identity():
    if request.endpoint in ("saas.login", "saas.register", "saas.health"):
        return None
    if current_user.is_authenticated and not is_saas_account():
        abort(403)
    if (is_saas_account() and current_user.must_change_password
            and request.endpoint not in ("saas.profile", "saas.profile_password", "saas.logout")):
        return redirect(url_for("saas.profile"))
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
        if len(password)<12 or password!=confirmation:
            flash("Use senha de pelo menos 12 caracteres e confirme corretamente.","danger")
        else:
            try:
                from app import bcrypt
                store.register_professional(name,email,bcrypt.generate_password_hash(password).decode(),profession,registry,cpf,birth_date,phone)
                flash("Cadastro recebido. A administradora deverá aprovar seu acesso; a licença será verificada separadamente.","success")
                return redirect(url_for("saas.login"))
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
        if session.get("login_blocked_until",0)>time.time():
            abort(429)
        from app import bcrypt
        row=store.user_by_email(request.form.get("email",""))
        password=request.form.get("senha","")
        if row and row["active"] and bcrypt.check_password_hash(row["password_hash"],password):
            user=store.SaaSUser(row)
            login_user(user,fresh=True)
            session["saas_auth"]=True
            session.pop("login_failures",None)
            session.pop("login_blocked_until",None)
            return redirect(url_for("saas.profile" if user.must_change_password else "saas.dashboard"))
        failures=int(session.get("login_failures",0))+1
        session["login_failures"]=failures
        if failures>=8:
            session["login_blocked_until"]=time.time()+300
            session["login_failures"]=0
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
    if not is_saas_account() or not current_user.is_practitioner():
        return render_template("saas_status.html",message="Área do paciente disponível por convite do profissional.")
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
    return render_template("saas_professionals.html",pending=store.pending_professionals(),
                           professionals=store.list_professionals(),csrf_token=csrf())


@bp.route("/profissionais/<int:professional_id>/decidir",methods=["POST"])
@admin_only
def decide_professional(professional_id):
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
    check_csrf()
    tenant=store.own_tenant(professional_id)
    if not tenant or not store.get_user(professional_id):
        abort(404)
    result=_attempt_trial(professional_id)
    flash(result,"success" if result.startswith("Trial ativo") else "warning")
    return redirect(url_for("saas.professionals"))


@bp.route("/pacientes",methods=["GET","POST"])
@practitioner_only
def patients():
    tenant,license=licensed_tenant()
    if not license.allowed:
        return render_template("saas_status.html",
                               message="Acesso profissional aguardando licença BTA válida. "+
                                       "Seu cadastro continua preservado."),403
    if request.method=="POST":
        check_csrf()
        try:
            store.create_client(current_user.id,tenant["id"],request.form.get("nome",""),
                                request.form.get("email",""))
            flash("Paciente registrado no seu espaço profissional.","success")
            return redirect(url_for("saas.patients"))
        except ValueError as exc:
            flash(str(exc),"danger")
    return render_template("saas_patients.html",tenant=tenant,
                           clients=store.list_clients(current_user.id,tenant["id"]),
                           csrf_token=csrf())


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

from saas_neurocore_routes import register_neurocore_routes
register_neurocore_routes(bp)

from saas_care_routes import register_care_routes
register_care_routes(bp)


@bp.route("/saude")
def health():
    from flask import jsonify
    try:
        store.one("SELECT 1 AS ok")
        # Fail release smoke if the NeuroCore additive schema was not applied.
        store.one("SELECT 1 FROM neurocore_evidence_reviews LIMIT 1")
        store.one("SELECT 1 FROM care_appointments LIMIT 1")
        store.one("SELECT 1 FROM care_encounters LIMIT 1")
        return jsonify({"database":"mysql","status":"ready"})
    except (pymysql.MySQLError,RuntimeError):
        return jsonify({"database":"mysql","status":"not_ready"}),503
