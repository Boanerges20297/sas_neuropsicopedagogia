# CHECKPOINT — Neuro-Diagnosis: fila de ativações homologada
Data: 2026-11-07 (America/Fortaleza). STI01 via NEXO Remote.
Base Git antes das mudanças: a8cc57bb8a68c21d32a3280a7d1dcb2735ed9550, main/origin/main.
Produção: INALTERADA; nenhum deploy executado.

## Regra aprovada
Profissional ativa as contas de seus próprios clientes; admin e superadmin podem ativar contas vinculadas a pacientes de qualquer profissional. A ativação se limita ao par paciente/conta e não concede acesso automático a prontuários. Um responsável utiliza um único login mesmo ao representar mais de um menor, mas os vínculos são aprovados separadamente.

## Mudanças no STI
- saas_portal_activation.py: papel e propriedade verificados dentro da transação, exigência de identidade ou guarda verificada, conta não suspensa, idade/representação, auditoria.
- saas_portal_activation_queue.py: SELECT com escopo profissional versus global, estados elegíveis, verificação de identidade/guarda; apenas nome, identificação de conta, vínculo com profissional e estado da solicitação; sem relato clínico. Limitado a 100 linhas.
- saas_portal_activation_routes.py: GET /saas/ativacoes e POST ativação; autenticação, CSRF e BTA para profissionais, isenção comercial para administradores; no-store no GET.
- templates/saas_portal_activation_queue.html e templates/saas_base.html: fila visual e atalho no menu.
- Dockerfile copia os módulos necessários para execução no container.
- scripts/homologate_mysql_care.py: cobertura SQL da fila em banco descartável MySQL.
- tests/test_saas_portal_activation_queue.py: cobertura de escopo, suspensão, verificação, CSRF e rota.

## Evidências
ACTIVATION_QUEUE_HOMOLOGATION_OK guardian=1 adult=1 scoped=1 hidden_after_activation=1
MYSQL_HOMOLOGATION_OK tables=26 tenants=2 blocked_invariants=5 guardian_unverified=1
DISPOSABLE_HOMOLOGATION_SCHEMA_DROPPED; MYSQL_EXIT=0.
Suíte integral: Ran 131 tests; OK (skipped=1), UNIT_EXIT=0 — 130 aprovados.
Warning legado de conexão sqlite3 não fechada, sem falha de teste.

## Pendências
- Git commit e push: NOVA autorização NEXO necessária; request_id 55df269e-9487-4f68-9c26-625c25908048, command_sha256 b42679ee81010d5ee4eca3757df0069702ac01978132fdc4bc11b44e1429b5. Comando NÃO enviado ao terminal.
- Ainda faltam convites/cadastro de conta do paciente ou responsável, pedido de ativação, revisão de identidade e guarda, consentimento e recuperação de acesso.
- E2E com sessão real, dois menores de um responsável, profissionais distintos, maioridade, suspensão e concorrência.
- Antes de qualquer deploy: reconciliar script de produção instalado, backup, migrations, pipeline canônico e smoke. Não publicar automaticamente.
