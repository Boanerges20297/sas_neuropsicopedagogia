"""Regression tests for the account, profile and test-catalog boundaries."""
import unittest
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import patch

from app import app, bcrypt
import saas_store as store
import saas_account_management as management
import saas_test_governance as governance
import saas_account_admin_routes as account_routes


class Recorder:
    def __init__(self,actor_role="superadmin",target_role="admin",target_active=1,
                 target_status="pending",version_status="draft"):
        self.actor_role=actor_role
        self.target_role=target_role
        self.target_active=target_active
        self.target_status=target_status
        self.version_status=version_status
        self.sql=[]
        self.row=None
        self.rows=[]
    def execute(self,query,args=()):
        self.sql.append((query,args))
        if "SELECT id,global_role,active FROM users" in query or "SELECT global_role,active FROM users" in query:
            self.row={"id":9,"global_role":self.actor_role,"active":1}
        elif "SELECT id,nome,email,global_role,active FROM users" in query:
            self.row={"id":50,"nome":"Before","email":"before@example.invalid","global_role":self.target_role,"active":self.target_active}
        elif "SELECT id,status,active,tenant_id FROM tests" in query:
            self.row={"id":40,"status":self.target_status,"active":1,"tenant_id":None}
        elif "SELECT id,version_number,status FROM test_versions" in query:
            self.row={"id":100,"version_number":2,"status":self.version_status}
        elif "SELECT id FROM users WHERE global_role='superadmin'" in query:
            self.rows=[{"id":9}]
            self.row=None
        else:
            self.row=None
    def fetchone(self):
        return self.row
    def fetchall(self):
        return self.rows


@contextmanager
def fake_tx(cursor):
    yield cursor


class AdminManagementBoundaryTests(unittest.TestCase):
    def update(self, cursor, **kwargs):
        with patch.object(store,"transaction",return_value=fake_tx(cursor)), \
             patch("saas_account_management.actor_can_grant",return_value=True), \
             patch.object(store,"audit") as audit:
            result=management.update_managed_account(
                9,50,nome="After",email="after@example.invalid",
                role=kwargs.get("role","admin"),
                active=kwargs.get("active",True),
                rights=kwargs.get("rights",{"accounts":True} if kwargs.get("role","admin")=="admin" else {}))
        return result,cursor.sql,audit

    def test_non_superadmin_cannot_promote_or_manage_superadmin(self):
        c=Recorder(actor_role="admin")
        with self.assertRaises(PermissionError):
            self.update(c,role="superadmin")
        c=Recorder(actor_role="admin",target_role="superadmin")
        with self.assertRaises(PermissionError):
            self.update(c,role="admin")

    def test_edit_creates_audited_rights_and_never_reads_patient_records(self):
        c=Recorder()
        result,queries,audit=self.update(c)
        self.assertEqual(result,50)
        self.assertTrue(any("UPDATE users SET" in q for q,_ in queries))
        self.assertTrue(any("INSERT INTO saas_account_rights" in q for q,_ in queries))
        self.assertFalse(any("assessment" in q.lower() or "care_encounters" in q.lower() for q,_ in queries))
        audit.assert_called_once()

    def test_professional_reactivation_cannot_skip_bta(self):
        c=Recorder(target_role="professional",target_active=0)
        with self.assertRaisesRegex(ValueError,"homologacao"):
            self.update(c,role="professional",active=True)

    def test_account_id_and_role_are_validated(self):
        c=Recorder()
        with self.assertRaises(ValueError):
            self.update(c,role="unexpected")

    def test_last_superadmin_cannot_be_disabled(self):
        c=Recorder(target_role="superadmin")
        with self.assertRaises(PermissionError):
            self.update(c,role="admin")


class TestGovernanceBoundaryTests(unittest.TestCase):
    def decide(self,c,decision="approve",reason="Revisao de conteudo completo"):
        with patch.object(store,"transaction",return_value=fake_tx(c)), \
             patch.object(store,"audit") as audit:
            governance.decide_catalog_item(9,40,decision,reason)
        return c.sql,audit

    def test_only_superadmin_can_decide(self):
        with self.assertRaises(PermissionError):
            self.decide(Recorder(actor_role="admin"))

    def test_cannot_approve_unsubmitted_test(self):
        with self.assertRaisesRegex(ValueError,"pendentes"):
            self.decide(Recorder(target_status="draft"))

    def test_cannot_approve_without_draft_version(self):
        with self.assertRaisesRegex(ValueError,"rascunho"):
            self.decide(Recorder(version_status="approved"))

    def test_approve_is_audited_and_does_not_query_patient_records(self):
        queries,audit=self.decide(Recorder())
        self.assertTrue(any("UPDATE test_versions" in q for q,_ in queries))
        self.assertTrue(any("UPDATE tests SET status='approved'" in q for q,_ in queries))
        self.assertFalse(any("assessments" in q or "assessment_responses" in q for q,_ in queries))
        audit.assert_called_once()

    def test_catalog_filters_and_pagination_are_parameterized(self):
        with patch.object(store,"all_rows",return_value=[]) as query:
            self.assertEqual(
                governance.list_catalog_for_review(
                    page=3,search="instrumento",status="pending"),[])
        sql,args=query.call_args.args
        self.assertIn("LIMIT %s OFFSET %s",sql)
        self.assertNotIn("assessments",sql)
        self.assertNotIn("assessment_responses",sql)
        self.assertEqual(args,("%instrumento%","%instrumento%","pending",26,50))
        with self.assertRaises(ValueError):
            governance.list_catalog_for_review(page=0)
        with self.assertRaises(ValueError):
            governance.list_catalog_for_review(status="invalid")

    def test_request_changes_returns_catalog_to_draft(self):
        queries,audit=self.decide(Recorder(),decision="request_changes")
        self.assertTrue(any("UPDATE tests SET status='draft'" in q for q,_ in queries))
        self.assertFalse(any("UPDATE test_versions" in q for q,_ in queries))
        audit.assert_called_once()

    def test_catalog_listing_uses_only_catalog_tables(self):
        with patch.object(store,"all_rows",return_value=[]) as query:
            self.assertEqual(governance.list_catalog_for_review(),[])
        sql=query.call_args.args[0]
        self.assertIn("test_versions",sql)
        self.assertNotIn("assessment_responses",sql)
        self.assertNotIn("care_encounters",sql)


class AdminAccountRouteTests(unittest.TestCase):
    def setUp(self):
        self.old=app.config["TESTING"]
        app.config["TESTING"]=True
        self.client=app.test_client()
        self.user=store.SaaSUser(dict(
            id=9,nome="Superadmin",email="sa@example.invalid",global_role="superadmin",
            active=1,must_change_password=False,mfa_required=True,mfa_enabled=True))
        self.loader=patch.object(store,"get_user",return_value=self.user)
        self.loader.start()
        with self.client.session_transaction() as sess:
            sess["_user_id"]="saas:9"
            sess["_fresh"]=True
            sess["saas_auth"]=True
            sess["saas_mfa_passed"]=True
            sess["saas_csrf"]="safe-csrf"
    def tearDown(self):
        self.loader.stop()
        app.config["TESTING"]=self.old

    def test_superadmin_sees_edit_action_in_user_list(self):
        sample=dict(id=50,nome="Synthetic",email="target@example.invalid",global_role="admin",active=1,
                    clinical_workspace=0,must_change_password=0)
        with patch.object(account_routes,"can_admin",return_value=True), \
             patch.object(account_routes,"list_managed_accounts",return_value=[sample]):
            r=self.client.get("/saas/contas")
        self.assertEqual(r.status_code,200)
        self.assertIn("/saas/contas/50/editar",r.get_data(as_text=True))

    def test_edit_requires_csrf_even_for_superadmin(self):
        sample=dict(id=50,nome="Synthetic",email="target@example.invalid",
                    global_role="admin",active=1,rights_id=12,
                    allow_accounts=1,allow_professionals=0,allow_activations=0,allow_clinic=0)
        with patch.object(account_routes,"can_admin",return_value=True), \
             patch.object(account_routes,"account_detail",return_value=sample), \
             patch.object(account_routes,"update_managed_account") as update:
            page=self.client.get("/saas/contas/50/editar")
            self.assertEqual(page.status_code,200)
            self.assertIn("Salvar altera",page.get_data(as_text=True))
            bad=self.client.post("/saas/contas/50/editar",data={"csrf_token":"invalid"})
            self.assertEqual(bad.status_code,400)
            update.assert_not_called()

    def test_admin_cannot_open_superadmin_account(self):
        sample=dict(id=50,nome="Target",email="target@example.invalid",
                    global_role="superadmin",active=1)
        self.user.role="admin"
        with patch.object(account_routes,"can_admin",return_value=True), \
             patch.object(account_routes,"account_detail",return_value=sample):
            self.assertEqual(self.client.get("/saas/contas/50/editar").status_code,403)

    def test_superadmin_cannot_browse_patient_workspace(self):
        self.assertEqual(self.client.get("/saas/pacientes").status_code,403)

    def test_test_catalog_is_superadmin_only(self):
        with patch.object(governance,"list_catalog_for_review",return_value=[]):
            self.assertEqual(self.client.get("/saas/admin/testes").status_code,200)
            self.user.role="admin"
            self.assertEqual(self.client.get("/saas/admin/testes").status_code,403)

    def test_personal_update_does_not_send_professional_fields(self):
        pwd="SyntheticPassword1234!"
        sample={"password_hash":bcrypt.generate_password_hash(pwd).decode(),"active":1}
        with patch.object(store,"user_by_email",return_value=sample), \
             patch.object(store,"update_account_profile") as update:
            r=self.client.post("/saas/perfil",data={
                "csrf_token":"safe-csrf","profile_action":"personal",
                "nome":"New Name","email":"changed@example.invalid","senha_atual":pwd,
                "profession":"psicologia","cpf":"99999999999"})
        self.assertEqual(r.status_code,302)
        update.assert_called_once_with(9,"New Name","changed@example.invalid")



class AccountPaginationTests(unittest.TestCase):
    def test_filters_use_parameters_and_never_query_patient_records(self):
        import saas_account_provision as provisioning
        with patch.object(provisioning,"can_admin",return_value=True), \
             patch.object(store,"all_rows",return_value=[]) as fetch:
            self.assertEqual(provisioning.list_managed_accounts(
                9,page=3,search="synthetic@example.invalid",role="patient"),[])
        sql,args=fetch.call_args.args
        self.assertIn("LIMIT %s OFFSET %s",sql)
        self.assertNotIn("assessment_responses",sql)
        self.assertNotIn("care_encounters",sql)
        self.assertEqual(args,("%synthetic@example.invalid%","%synthetic@example.invalid%","patient",26,50))

    def test_invalid_filter_and_page_rejected(self):
        import saas_account_provision as provisioning
        with patch.object(provisioning,"can_admin",return_value=True):
            with self.assertRaises(ValueError):
                provisioning.list_managed_accounts(9,page=0)
            with self.assertRaises(ValueError):
                provisioning.list_managed_accounts(9,role="unexpected")

if __name__=="__main__":
    unittest.main()
