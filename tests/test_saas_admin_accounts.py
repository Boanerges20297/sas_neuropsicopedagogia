"""Administrative provisioning cannot overgrant platform or clinical privileges."""
import unittest
from contextlib import contextmanager
from unittest.mock import patch

import saas_account_provision as provisioning
import saas_account_access as access
import saas_login_policy as passwords
import saas_store as store


class Cursor:
    def __init__(self, actor="superadmin", rights=None):
        self.actor=actor
        self.rights=rights
        self.queries=[]
        self.row=None
        self.lastrowid=0

    def execute(self, sql, args=()):
        self.queries.append((sql,args))
        if "SELECT id,global_role,active FROM users" in sql:
            self.row={"id":9,"active":1,"global_role":self.actor}
        elif "FROM saas_account_rights WHERE user_id=" in sql:
            self.row=self.rights
        else:
            self.row=None
        if "INSERT INTO users" in sql:
            self.lastrowid=101
        if "INSERT INTO tenants" in sql:
            self.lastrowid=201

    def fetchone(self):
        return self.row


@contextmanager
def tx(cursor):
    yield cursor


class AdminCreationTests(unittest.TestCase):
    def create(self,role,actor="superadmin",rights=None,**kwargs):
        cursor=Cursor(actor,rights)
        with patch.object(store,"transaction",return_value=tx(cursor)), \
             patch.object(store,"audit"):
            uid=provisioning.create_managed_account(
                9,nome="Synthetic Tester",email="synthetic@example.invalid",
                role=role,password_hash="synthetic-bcrypt-hash-placeholder-12345",
                **kwargs)
        return uid,cursor.queries

    def test_all_new_roles_require_email_ownership_proof(self):
        synthetic_details=dict(practice_area="psicologia",
                               cpf_digest="synthetic",cpf_encrypted=b"cipher",
                               birth_date="1990-03-01",phone="85999999999")
        with patch.object(provisioning,"validate_details",
                          return_value=synthetic_details):
            for role in ("patient","professional","admin","superadmin"):
                with self.subTest(role=role):
                    opts=(dict(cpf="synthetic",profession="psicologia",
                               birth_date="1990-03-01",phone="85999999999")
                          if role=="professional" else {})
                    uid,sql=self.create(role,**opts)
                    self.assertTrue(any(
                        "INSERT INTO saas_email_verifications" in statement
                        and args==(uid,)
                        for statement,args in sql),
                        "Email proof missing for "+role)

    def test_new_admin_gets_explicit_limits_and_mfa(self):
        uid,sql=self.create("admin")
        self.assertEqual(uid,101)
        self.assertTrue(any("INSERT INTO saas_mfa_factors" in q
                            for q,_ in sql))
        self.assertTrue(any("saas_account_rights" in q
                            and args[1:5]==(0,0,0,0) for q,args in sql))
        self.assertFalse(any("INSERT INTO tenants" in q for q,_ in sql))

    def test_patient_is_pending_and_never_gets_clinic(self):
        _,sql=self.create("patient")
        row=next(args for q,args in sql if "INSERT INTO users" in q)
        self.assertEqual(row[-1],0)
        self.assertTrue(any("care_portal_login_requests" in q for q,_ in sql))
        self.assertTrue(any("saas_mfa_factors" in q for q,_ in sql))
        self.assertFalse(any("INSERT INTO tenants" in q for q,_ in sql))

    def test_admin_can_have_private_clinical_workspace(self):
        details={"practice_area":"psicologia","cpf_digest":"synthetic",
                 "cpf_encrypted":b"ciphertext", "birth_date":"1990-01-01",
                 "phone":"85988888888"}
        with patch.object(provisioning,"validate_details",return_value=details):
            _,sql=self.create("admin",clinical_workspace=True,cpf="synthetic",profession="psicologia",birth_date="1990-01-01",phone="85988888888")
        self.assertTrue(any("INSERT INTO professional_profiles" in q for q,_ in sql))
        self.assertTrue(any("INSERT INTO tenants" in q for q,_ in sql))
        self.assertTrue(any("INSERT INTO tenant_members" in q for q,_ in sql))

    def test_admin_private_workspace_does_not_require_professional_profile(self):
        _,queries=self.create("admin",clinical_workspace=True)
        self.assertTrue(any("INSERT INTO tenants" in sql for sql,_ in queries))
        self.assertFalse(any("INSERT INTO professional_details" in sql for sql,_ in queries))
        self.assertFalse(any("INSERT INTO professional_profiles" in sql for sql,_ in queries))

    def test_professional_profile_is_required_only_for_professionals(self):
        with self.assertRaises(ValueError):
            self.create("professional")
        self.assertEqual(
            provisioning.ACCOUNT_ROLES,
            frozenset(("patient","professional","admin","superadmin")))

    def test_admin_cannot_escalate_privileges(self):
        limits={"allow_accounts":1,"allow_professionals":0,
                "allow_activations":0,"allow_clinic":0}
        with self.assertRaises(PermissionError):
            self.create("superadmin",actor="admin")
        with self.assertRaises(PermissionError):
            self.create("admin",actor="admin",rights=limits,
                        allow_professionals=True)

    def test_password_requirements(self):
        self.assertTrue(passwords.valid_credential("Ab1234!x"))
        for invalid in ("A1234!@#","Ab123!xy","Ab1234xy","Ab1234!"):
            self.assertFalse(passwords.valid_credential(invalid))
        for _ in range(30):
            self.assertTrue(passwords.valid_credential(
                passwords.temporary_credential()))


class BrowserSuggestionTests(unittest.TestCase):
    def test_policy_aligned_client_generator(self):
        """Execute actual shared-form JS and compare output to Python policy."""
        import json
        import shutil
        import subprocess
        from pathlib import Path

        if not shutil.which("node"):
            self.skipTest("Node not available in this runner")
        template=Path(__file__).resolve().parents[1] / "templates" / "saas_base.html"
        js = r"""
const fs=require('node:fs');
const vm=require('node:vm');
const crypto=require('node:crypto');
const text=fs.readFileSync(process.argv[1],'utf8');
const match=text.match(/<script>([\s\S]*?)<\/script>/);
if(!match) throw Error('missing shared form helper');
let callback=null;
const button={dataset:{passwordTarget:'p',confirmTarget:'c',noticeTarget:'n'},
  addEventListener:(event,fn)=>{if(event==='click')callback=fn;}};
const fields={p:{value:'',dispatchEvent(){}},
  c:{value:'',dispatchEvent(){}},n:{textContent:''}};
const document={
  querySelectorAll:selector=>selector==='[data-suggest-password]'?[button]:[],
  getElementById:id=>fields[id]||null
};
vm.runInNewContext(match[1], {
  document,window:{crypto:crypto.webcrypto},Uint32Array,Event:class{}
});
if(typeof callback!=='function') throw Error('not connected');
const results=[];
for(let i=0;i<250;i++){
  callback();
  if(fields.p.value!==fields.c.value) throw Error('different confirmation');
  if(!fields.n.textContent.includes('validada')) throw Error('invalid feedback');
  results.push(fields.p.value);
}
process.stdout.write(JSON.stringify(results));
"""
        run=subprocess.run(["node","-e",js,str(template)],
                           capture_output=True,text=True,timeout=30,check=True)
        suggestions=json.loads(run.stdout)
        self.assertEqual(len(suggestions),250)
        for proposed in suggestions:
            self.assertEqual(len(proposed),20)
            self.assertTrue(passwords.valid_credential(proposed))
            self.assertGreaterEqual(sum(c.isalpha() for c in proposed),4)
            self.assertGreaterEqual(sum(c.isdigit() for c in proposed),6)
            self.assertGreaterEqual(sum(not c.isalnum() for c in proposed),2)


class PermissionTests(unittest.TestCase):
    def test_new_admin_limited_superadmin_unlimited(self):
        row={"global_role":"admin","active":1,"rights_id":14,
             "allow_accounts":1,"allow_professionals":0,
             "allow_activations":0,"allow_clinic":1}
        with patch.object(store,"one",return_value=row):
            self.assertEqual(access.admin_permissions(9),
                             dict(accounts=True,professionals=False,
                                  activations=False,clinic=True))
        with patch.object(store,"one",return_value={**row,"global_role":"superadmin"}):
            self.assertTrue(all(access.admin_permissions(9).values()))


if __name__=="__main__":
    unittest.main()
