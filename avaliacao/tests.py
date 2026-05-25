from django.test import TestCase
from django.urls import reverse

from .models import (
    PerfilUsuario,
    Paciente,
    AnotacaoAtendimento,
    ConsultaIAClinica,
    FeedbackConsultaIA,
)


class ClinicalFlowTests(TestCase):
    def setUp(self):
        self.admin = PerfilUsuario.objects.create_user(
            username="admin",
            email="admin@test.com",
            password="SenhaForte1",
            role="admin",
            first_name="Admin",
        )
        self.client.force_login(self.admin)

        self.paciente = Paciente.objects.create(
            nome="Paciente Teste",
            data_nascimento="10/10/2016",
            telefone="85999999999",
        )
        self.paciente.decrypt_sensitive()

    def test_admin_pages_load(self):
        urls = [
            reverse("dashboard"),
            reverse("pacientes_list"),
            reverse("admin_avaliacoes"),
            reverse("admin_users"),
            reverse("ia_consulta"),
        ]
        for url in urls:
            resp = self.client.get(url)
            self.assertEqual(resp.status_code, 200)

    def test_create_clinical_note(self):
        resp = self.client.post(
            reverse("paciente_detail", kwargs={"paciente_id": self.paciente.id}),
            data={
                "data_consulta": "2026-05-25",
                "tipo": "sessao",
                "titulo": "Sessão inicial",
                "conteudo": "Paciente colaborou bem durante a sessão.",
            },
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(AnotacaoAtendimento.objects.count(), 1)

    def test_feedback_ia_weight(self):
        consulta = ConsultaIAClinica.objects.create(
            paciente=self.paciente,
            profissional=self.admin,
            pergunta="Pergunta de teste",
            contexto="Contexto de teste",
            resultado_json='{"ok": true}',
        )
        resp = self.client.post(
            reverse("feedback_consulta_ia", kwargs={"consulta_id": consulta.id}),
            data={"julgamento": "acerto", "comentario": "Resposta clinicamente correta"},
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        fb = FeedbackConsultaIA.objects.get(consulta=consulta)
        self.assertEqual(fb.peso, 2)
