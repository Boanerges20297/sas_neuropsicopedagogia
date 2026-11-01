"""Opt-in production-staging smoke test. Creates only synthetic test professional.

Intended for Flask container on loopback with SaaS MySQL/BTA test catalog.
Fails closed unless SAAS_SMOKE_ALLOW=1. No patient records or clinical data.
"""
import os
import secrets
import sys
from uuid import uuid4

if os.getenv("SAAS_SMOKE_ALLOW") != "1":
    raise SystemExit("SMOKE_ABORTED: set SAAS_SMOKE_ALLOW=1 explicitly")

from app import app, bcrypt
import saas_store as store
from bta_license_client import resolve_tenant_license

admins = store.all_rows(
    "SELECT id,global_role FROM users WHERE global_role IN ('admin','superadmin') AND active=1")
if len(admins) != 1:
    raise SystemExit("SMOKE_ABORTED: expected exactly one active SaaS administrator")
admin_id = admins[0]["id"]
mail = "smoke-" + uuid4().hex[:20] + "@example.invalid"
password = secrets.token_urlsafe(32)
pid = store.register_professional(
    "Profissional Sintético de Homologação",
    mail, bcrypt.generate_password_hash(password).decode(),
    "neuropsicopedagogo", "TEST-NO-REGISTRY")
if store.own_tenant(pid) is not None:
    raise SystemExit("SMOKE_FAIL: pending professional got active workspace")
with app.test_client() as c:
    assert c.get("/health/ready").status_code == 200, "legacy readiness"
    assert c.get("/saas/saude").status_code == 200, "mysql readiness"
    assert c.get("/saas/cadastro").status_code == 200, "registration page"
    assert c.get("/saas/entrar").status_code == 200, "login page"
    with c.session_transaction() as session:
        session["_user_id"] = "saas:" + str(admin_id)
        session["_fresh"] = True
        session["saas_auth"] = True
        session["saas_csrf"] = "test-smoke-csrf"
    assert c.get("/saas/profissionais").status_code == 200, "admin approval page"
    result = c.post(
        "/saas/profissionais/" + str(pid) + "/decidir",
        data={"csrf_token":"test-smoke-csrf","decision":"approve",
              "reason":"Teste automatizado de homologação SaaS/BTA",
              "activate_trial":"on"},
        follow_redirects=False)
    assert result.status_code == 302, "admin approval POST"
row = store.user_by_email(mail)
if not row or not row["active"]:
    raise SystemExit("SMOKE_FAIL: professional not activated")
tenant = store.own_tenant(pid)
if not tenant:
    raise SystemExit("SMOKE_FAIL: workspace not activated")
decision = resolve_tenant_license(tenant["slug"], tenant["nome"])
if not decision.allowed:
    raise SystemExit("SMOKE_FAIL: BTA trial activation or resolution failed: " + decision.reason)
with app.test_client() as c:
    with c.session_transaction() as session:
        session["_user_id"] = "saas:" + str(pid)
        session["_fresh"] = True
        session["saas_auth"] = True
    assert c.get("/saas/painel").status_code == 200, "professional panel"
    assert c.get("/saas/pacientes").status_code == 200, "licensed professional area"
    assert c.get("/saas/testes").status_code == 200, "licensed instruments area"
print("SMOKE_OK | synthetic professional approved | BTA trial active | scoped pages accessible")
