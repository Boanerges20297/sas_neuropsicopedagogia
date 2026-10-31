import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from contextlib import closing
from unittest.mock import patch
import app as project
class NeuroDiagnosisSmokeTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).resolve().parent.parent
        self.tmp = tempfile.TemporaryDirectory(prefix=".neuro-test-", dir=self.root)
        self.original_db = project.DB_PATH
        project.DB_PATH = str(Path(self.tmp.name) / "test.sqlite3")
        self.env = patch.dict(os.environ, {
            "ADMIN_EMAIL": "test.admin@example.invalid",
            "ADMIN_PASSWORD": "LocalTestAdminPassphrase123",
            "SUPERADMIN_EMAIL": "test.superadmin@example.invalid",
            "SUPERADMIN_PASSWORD": "LocalTestSuperPassphrase123",
        })
        self.env.start()
        project.app.config["TESTING"] = True
        project.init_db()
        self.client = project.app.test_client()
    def tearDown(self):
        self.env.stop()
        project.DB_PATH = self.original_db
        self.tmp.cleanup()
    def login(self, account="test.admin@example.invalid", password="LocalTestAdminPassphrase123"):
        return self.client.post("/login", data={"email": account, "senha": password})
    def test_schema_migration_repeatable_and_legacy_data_preserved(self):
        with closing(sqlite3.connect(project.DB_PATH)) as con:
            con.execute("INSERT INTO responses(nome) VALUES ('amostra-local')")
            first_id = con.execute("SELECT max(id) FROM responses").fetchone()[0]
            con.commit()
        project.init_db()
        project.init_db()
        with closing(sqlite3.connect(project.DB_PATH)) as con:
            names = {row[0] for row in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )}
            self.assertTrue({"users", "test_types", "responses", "tests",
                             "test_categories", "questions", "question_responses"} <= names)
            self.assertEqual(con.execute("SELECT nome FROM responses WHERE id=?", (first_id,))
                             .fetchone()[0], "amostra-local")
            self.assertEqual(con.execute("SELECT COUNT(*) FROM users WHERE role='superadmin'")
                             .fetchone()[0], 1)
    def test_public_and_admin_routes_render(self):
        self.assertEqual(self.client.get("/login").status_code, 200)
        self.assertEqual(self.client.get("/select-test").status_code, 200)
        self.assertEqual(self.login().status_code, 302)
        for url in ("/dashboard", "/admin/usuarios", "/admin/testes",
                    "/admin/categorias", "/admin/testes/novo"):
            self.assertEqual(self.client.get(url).status_code, 200, url)
    def test_superadmin_must_change_password_before_access(self):
        response = self.login("test.superadmin@example.invalid",
                              "LocalTestSuperPassphrase123")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/alterar-senha", response.location)
        self.assertEqual(self.client.get("/alterar-senha").status_code, 200)
        self.assertIn("/alterar-senha", self.client.get("/dashboard").location)
        self.client.post("/alterar-senha", data={
            "senha_atual": "LocalTestSuperPassphrase123",
            "nova_senha": "curta",
            "confirmar_senha": "curta",
        })
        self.assertIn("/alterar-senha", self.client.get("/dashboard").location)
        new_password = "NovaSenhaForteParaTeste123!"
        changed = self.client.post("/alterar-senha", data={
            "senha_atual": "LocalTestSuperPassphrase123",
            "nova_senha": new_password,
            "confirmar_senha": new_password,
        })
        self.assertEqual(changed.status_code, 302)
        self.assertIn("/dashboard", changed.location)
        self.assertEqual(self.client.get("/dashboard").status_code, 200)
        with closing(sqlite3.connect(project.DB_PATH)) as con:
            row = con.execute("SELECT senha_hash, must_change_password FROM users WHERE role='superadmin'").fetchone()
            self.assertEqual(row[1], 0)
            self.assertTrue(project.bcrypt.check_password_hash(row[0], new_password))
        self.client.get("/logout")
        self.assertNotIn("/dashboard", self.login("test.superadmin@example.invalid",
                                                 "LocalTestSuperPassphrase123").location or "")
        self.assertIn("/dashboard", self.login("test.superadmin@example.invalid",
                                              new_password).location)
    def test_complete_dynamic_assessment_flow(self):
        self.login()
        created = self.client.post("/admin/categorias/adicionar", data={
            "nome": "Categoria de teste", "descricao": "Cenario automatizado",
            "cor": "#315b61", "icone": "T",
        })
        self.assertEqual(created.status_code, 200)
        category_id = created.json["id"]
        created_test = self.client.post("/admin/testes/criar", data={
            "category_id": str(category_id), "titulo": "Teste automatizado",
            "descricao": "Instrumento ficticio", "instrucoes": "Responder",
            "tempo_estimado": "5",
        })
        self.assertEqual(created_test.status_code, 302)
        with closing(sqlite3.connect(project.DB_PATH)) as con:
            test_id = con.execute("SELECT id FROM tests ORDER BY id DESC LIMIT 1").fetchone()[0]
        question = self.client.post(
            f"/admin/testes/{test_id}/questoes/adicionar",
            data={"test_id": str(test_id), "tipo": "text",
                  "enunciado": "Pergunta ficticia", "pontos": "1"},
        )
        self.assertEqual(question.status_code, 200)
        self.assertTrue(question.json["success"])
        with closing(sqlite3.connect(project.DB_PATH)) as con:
            question_id = con.execute("SELECT id FROM questions WHERE test_id=?", (test_id,)).fetchone()[0]
        self.assertEqual(self.client.get(f"/teste/{test_id}").status_code, 200)
        self.assertEqual(self.client.get("/select-test").status_code, 200)
        submitted = self.client.post(f"/teste/{test_id}/enviar", data={
            "nome": "Pessoa de teste", "idade": "20",
            f"question_{question_id}": "Resposta ficticia",
        })
        self.assertEqual(submitted.status_code, 200)
        with closing(sqlite3.connect(project.DB_PATH)) as con:
            self.assertEqual(con.execute(
                "SELECT nome_pessoa FROM responses WHERE test_id=?", (test_id,)
            ).fetchone()[0], "Pessoa de teste")
            self.assertEqual(con.execute(
                "SELECT resposta FROM question_responses WHERE question_id=?", (question_id,)
            ).fetchone()[0], "Resposta ficticia")
    def test_regular_user_stays_out_of_admin_area(self):
        registered = self.client.post("/register", data={
            "nome": "Usuario ficticio", "email": "person@example.invalid",
            "senha": "FictitiousPassword123", "data_nascimento": "2000-01-01",
            "escolaridade": "", "telefone": "",
        })
        self.assertEqual(registered.status_code, 302)
        logged = self.login("person@example.invalid", "FictitiousPassword123")
        self.assertIn("/area-do-usuario", logged.location)
        home = self.client.get("/")
        self.assertIn("/area-do-usuario", home.location)
        restricted = self.client.get("/admin/testes")
        self.assertEqual(restricted.status_code, 302)
        self.assertEqual(self.client.get("/area-do-usuario").status_code, 200)
    def test_no_implicit_admin_when_env_has_no_bootstrap(self):
        original = project.DB_PATH
        with tempfile.TemporaryDirectory(prefix=".neuro-blank-", dir=self.root) as scratch:
            project.DB_PATH = str(Path(scratch) / "empty.sqlite3")
            try:
                with patch.dict(os.environ, {
                    "ADMIN_EMAIL": "", "ADMIN_PASSWORD": "",
                    "SUPERADMIN_EMAIL": "", "SUPERADMIN_PASSWORD": "",
                }):
                    project.init_db()
                with closing(sqlite3.connect(project.DB_PATH)) as con:
                    self.assertEqual(con.execute("SELECT COUNT(*) FROM users").fetchone()[0], 0)
            finally:
                project.DB_PATH = original
if __name__ == "__main__":
    unittest.main()
