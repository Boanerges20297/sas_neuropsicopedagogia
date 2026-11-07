"""Render checks for the isolated SaaS dashboard visual upgrade."""
from pathlib import Path
from types import SimpleNamespace
import unittest

from jinja2 import Environment, FileSystemLoader, StrictUndefined


ROOT = Path(__file__).resolve().parents[1]


def render_dashboard(*, admin=False, tenant=None, license=None, stats=None):
    env = Environment(
        loader=FileSystemLoader(str(ROOT / "templates")),
        autoescape=True,
        undefined=StrictUndefined,
    )
    env.globals["url_for"] = lambda endpoint, **kwargs: (
        "/static/" + kwargs["filename"] if endpoint == "static" else "/" + endpoint
    )
    env.globals["get_flashed_messages"] = lambda **kwargs: []
    user = SimpleNamespace(
        nome="Usuário de teste",
        is_authenticated=True,
        is_admin=lambda: admin,
        is_practitioner=lambda: True,
    )
    return env.get_template("saas_dashboard.html").render(
        current_user=user,
        session={"saas_auth": True},
        tenant=tenant,
        license=license,
        stats=stats,
        csrf_token="test-csrf",
        has_saas_workspace=bool(tenant) if admin else True,
        can_manage_accounts=admin,
        can_manage_professionals=admin,
        can_manage_activations=True,
    )


class DashboardSaaSUiTests(unittest.TestCase):
    def test_admin_without_clinical_tenant_uses_correct_status(self):
        stats = dict(professionals=6, pending=2, active_tenants=4, total_clients=9)
        output = render_dashboard(
            admin=True,
            license=SimpleNamespace(status="exempt", allowed=True, state=None),
            stats=stats,
        )
        self.assertIn("Administração da plataforma", output)
        self.assertIn("Acesso administrativo permanente", output)
        self.assertNotIn("Aguardando ativação", output)
        self.assertIn('aria-valuenow="2"', output)
        self.assertIn('width: 33.3%', output)
        self.assertIn('href="/saas.professionals"', output)

    def test_licensed_professional_has_owned_workspace_shortcuts(self):
        output = render_dashboard(
            tenant=dict(nome="Clínica Exemplo", status="active"),
            license=SimpleNamespace(status="allowed", allowed=True, state="active"),
        )
        self.assertIn("Clínica Exemplo", output)
        self.assertIn("Licença BTA válida", output)
        self.assertIn("Acessar seus registros", output)
        self.assertNotIn("PANORAMA DA PLATAFORMA", output)
        self.assertNotIn("Gerenciar profissionais", output)

    def test_nonactivated_professional_has_no_action_shortcuts(self):
        output = render_dashboard()
        self.assertIn("Aguardando ativação", output)
        self.assertNotIn("Acessar seus registros", output)
        self.assertNotIn("Consultar testes disponíveis", output)
        self.assertNotIn("Gerenciar profissionais", output)

    def test_dashboard_stylesheet_is_present_and_scoped(self):
        css = (ROOT / "static" / "saas-dashboard.css").read_text(encoding="utf-8")
        self.assertIn(".nd-hero", css)
        self.assertIn(".nd-dashboard", css)
        self.assertIn("@media(max-width:600px)", css)


if __name__ == "__main__":
    unittest.main()
