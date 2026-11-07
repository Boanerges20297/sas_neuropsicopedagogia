# Checkpoint — hierarquia de ativação dos clientes
Data: 2026-11-07 | Ambiente: STI01 via NEXO
Base anterior: a8cc57b (main/origin/main); alterações locais de portal fase 1 ainda não commitadas.
Status: lógica de ativação implementada e homologada com dados sintéticos; sem release.

## Decisão do usuário
- Cada profissional libera as contas de seus próprios clientes.
- Administrador e superadministrador podem liberar clientes de QUALQUER profissional/tenant.
- Esse poder é de gestão da ativação. NÃO permite ler dados clínicos, criar laudos, aprovar documentos clínicos sem revisão ou assumir o paciente.
- Aprovação/ativação é individual por vínculo paciente + usuário de login + profissional, mesmo se um único responsável possuir vários filhos.
- Conta de menor não é criada: o responsável usa seu único login.

## Implementação STI
- saas_portal_activation.py: verifica o papel do ator na base, o pertencimento do cliente, status do tenant/profissional, verificação de identidade do adulto ou guarda legal de menor, maioridade e controle transacional. Administradores ignoram só o filtro de propriedade, não provas de vínculo.
- saas_portal_activation_routes.py: POST autenticado com CSRF; profissional exige BTA válido; admin/superadmin isentos do gate comercial; falha de escopo retorna 403.
- scripts/mysql_care_client_activation_migration.sql: duas tabelas novas: care_portal_client_activations (por paciente) e care_portal_login_requests (ciclo de ativação global pending/active/suspended). Ativação de conta suspensa é negada, sem reativação indireta.
- saas_portal_policy.py: o portal exige conta ativa e ativação explícita PARA CADA paciente antes de sequer considerar grants, identidade e consentimento. E-mail ou vínculo verbal NÃO habilita acesso.
- saas_routes.py /saas/saude valida as novas tabelas; infra/host/deploy-neuro-diagnosis-saas.sh aplica migração após backup e após portal_self. Dockerfile inclui os novos módulos.
- Testes da matriz de permissão, ausência de prova, pai/mãe, adulto independente, CSRF, BTA, proteção de tenant e idempotência de ativação existentes.

## Evidências
- python -m unittest tests.test_saas_portal_activation tests.test_saas_portal_policy -q: 19 testes, zero falhas.
- scripts/homologate_mysql_care.py no STI: MYSQL_HOMOLOGATION_OK tables=26 tenants=2 blocked_invariants=5; HML_EXIT=0; esquema descartável removido.
- Suíte completa após a regra de ativação: 124 testes executados, 123 aprovados, 1 ignorado e 0 falhas; UNIT_EXIT=0. git diff --check passou.
- Este checkpoint NÃO significa que as interfaces de auto cadastro, convites, provas de identidade, recuperação de senha e botões de aprovação já estão prontas.

## Próximos gates
1. Implementar solicitação/registro de conta paciente ou responsável com validação de email, senha e proteção de dados, criando care_portal_login_requests em pending; sem login do menor.
2. Tela de fila de ativações: profissional vê somente os seus; admin/superadmin veem todos, com metadados mínimos necessários à avaliação, nunca narrativas clínicas.
3. Fluxo auditado de submissão/revisão de evidências de identidade e guarda, consentimentos LGPD, revogação e suspensão; não ativar por e-mail coincidente.
4. E2E real com duas crianças do mesmo responsável, profissionais distintos, suspensão, maioridade e concorrência.
5. Validar produção: script instalado na VPS, backup, pipeline canônico, smoke de login, jamais release sem autorização.
