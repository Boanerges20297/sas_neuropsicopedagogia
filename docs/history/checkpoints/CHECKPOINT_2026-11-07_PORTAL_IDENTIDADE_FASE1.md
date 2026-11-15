# Checkpoint — Neuro-Diagnosis: portal identidade e consentimento (fase 1)
Data: 2026-11-07 (America/Fortaleza)
Bancada: STI01 via NEXO. Baseline: main/origin/main a8cc57b.
Estado: backend fail-closed implementado/testado. NENHUMA rota de portal habilitada. SEM deploy.

## O que avançou
- Adulto independente: tabelas aditivas care_portal_self_links e care_portal_self_grants para relacionar um usuário paciente EXISTENTE a um registro clínico, nunca criar conta duplicada automaticamente.
- Responsável por menor: o modelo legado de identity link/contact/grant permanece; a política agora exige intake 'guardian', contato exato e paciente menor de 18 anos no fuso de Fortaleza. Contas familiares podem vincular vários pacientes, mas autorização sempre individual.
- Consentimento específico por paciente + usuário + escopo: tabela care_portal_consents, inicialmente pendente. Um vínculo sem verificação, consentimento aceito e grant profissional ativo, válido e não expirado NÃO libera acesso.
- Verificação de adulto exige referência de evidência, registro de consentimento e profissional verificador. A concessão continua restrita a appointments e released_documents, não inclui anotações clínicas nem diagnóstico.
- saas_portal_policy.can_access consulta ambas as rotas exclusivamente por tenant, paciente, profissional e user ID, fail-closed para argumentos inválidos.
- Health /saas/saude verifica as 3 tabelas novas.
- Script de deploy versionado inclui migração após intake e antes de reiniciar a web. NÃO atualizar o script instalado em VPS sem autorização e conciliação prévia.

## Evidência de testes
- Suite no STI: python -m unittest discover -s tests -q => Ran 111 tests, OK (skipped=1), UNIT_EXIT=0. Ou seja: 110 aprovados, 1 ignorado, zero falhas.
- MySQL real do STI (WSL, esquema descartável): MYSQL_HOMOLOGATION_OK tables=24 tenants=2 blocked_invariants=5 guardian_unverified=1; HML_EXIT=0.
- Cenário sintético positivo de adulto com link, concessão e consentimento aceitos executado com sucesso; guardian sem verificação é negado por padrão; teste de revogação do contato do responsável passou.
- DISPOSABLE_HOMOLOGATION_SCHEMA_DROPPED confirmou descarte do esquema temporário. Não há dados clínicos reais em testes.
- Nota: não foi realizada validação UI desktop/mobile, sessões reais nem teste de concorrência simultânea.

## Pendente antes de habilitar o portal
1. Cadastro/ativação e recuperação de senha do titular de conta paciente ou responsável, com confirmação de e-mail e autenticação segura; não criar login do menor.
2. Fluxo verificável de identidade/vínculo legal, registro de consentimentos com texto/versão/finalidade, assinatura/autorização por profissional e política LGPD revisada.
3. Interface clínica de revisão, acesso por criança, auditoria de concessões/revogações e expiração.
4. Endpoint mínimo de agenda baseado em can_access; documentos requerem liberação individual antes de qualquer rota.
5. E2E de sessão real, inclusão de dois irmãos com o mesmo responsável, cross-tenant, concorrência e maioridade; validação da profissional administradora em desktop/mobile.
6. Produção: backup, reconciliação do script instalado na VPS, validação do pipeline canônico e publicação somente depois de aceite explícito. Não acionado release.json.

## Invariantes
- Um usuário de login pode representar vários pacientes, sem compartilhar prontuário entre irmãos.
- E-mail, nome ou contato coincidente NÃO comprovam identidade ou guarda.
- Administradores não herdam acesso ao conteúdo clínico de outros profissionais.
- BTA apenas para profissionais comuns; contas admin e superadmin têm isenção comercial no próprio espaço.
- NeuroCore é assistivo e não emite diagnóstico automático.
