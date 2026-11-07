# Checkpoint — Neuro-Diagnosis, arquitetura profissional ↔ cliente
Data: 2026-11-07 | Ambiente: STI01 via NEXO
Repositório: Boanerges20297/sas_neuropsicopedagogia, main
Ponto de partida sincronizado com origin/main: ca3c366956439e1b134f9981b3db45e6e2cd5b0c.

## Entregas implementadas no STI (sem release)
- Módulo saas_care_store.py: agenda transacional, fusos America/Fortaleza → UTC, bloqueio de sobreposição, UUID idempotente, máquina de estados, autorização por tenant + profissional + paciente e auditoria.
- Módulo saas_care_routes.py: GET /saas/agenda, GET/POST /saas/pacientes/<id>/agenda, POST /saas/pacientes/<id>/agenda/<id>/acao. CSRF e licença obrigatórios.
- Templates e CSS para agenda geral, agenda do paciente, formulários e histórico; atalhos na navegação e na área do paciente.
- Migração SQL aditiva scripts/mysql_care_workflow_migration.sql: care_client_contacts, care_appointments, care_encounters. Contato/responsável inicia como UNVERIFIED; não habilita portal.
- Dockerfile atualizado com os dois módulos; tzdata incluída somente como dependência leve necessária ao servidor.
- Script fonte do pipeline alterado para migrar após o backup e antes de iniciar novo web container; health endpoint verifica tabelas novas.
- Documento completo ARQUITETURA_ATENDIMENTO_PROFISSIONAL_CLIENTE_2026-11-07.md, com fronteiras clínicas, papéis, ciclo e critérios de aceite.
- Testes automatizados com casos sintéticos: GET/POST/CSRF, tenant e profissional, calendário, timezone, repetição de requisição, conflito, estados, sessão em rascunho, negação de acesso e migração.

## Verificações já executadas
- Suite completa no STI: 90 testes, OK (1 skipped; 89 aprovados), tempo ~10 s.
- Python compileall: exit 0.
- git diff --check: exit 0.
- Dependência tzdata 2026.6 instalada na venv do STI, necessária para ZoneInfo em Windows.
- Teste de login antigo passou após evitar query de tenant durante troca obrigatória de senha.
- Docker e serviço MySQL não foram encontrados no STI pela checagem de comandos e serviços; **nenhum teste MySQL real ou docker build foi executado**.

## Pendências/gates
1. Validar migração e concorrência em MySQL descartável com dois profissionais/pacientes sintéticos; testes de mock NÃO substituem homologação.
2. Reconciliação autorizada da cópia instalada na VPS em /usr/local/sbin/deploy-neuro-diagnosis com o script fonte versionado, antes de qualquer request de release.
3. Revisão visual mobile/desktop e validação funcional autenticada pela administradora.
4. Cadastro/verificação de responsável legal, portal cliente, confirmação de consentimentos e grants de acesso, compartilhamento restrito; NÃO implementados.
5. Editor e assinatura de evolução clínica, criptografia, retenção e instrumentos versionados para aplicação real; NÃO implementados.
6. Não utilizar instrumentos protegidos/DSM integral sem direitos e validação por profissionais habilitados.
7. Publicação somente por pipeline canônico após todas as validações; não alterei .release/request.json.

## Interpretação correta
Arquitetura operacional definida e primeira fatia de atendimento programada/testada no STI. Não equivale a atendimento clínico integral nem a produção pronta.

## Atualização posterior — 07/11/2026
O MySQL 8.4.8 foi localizado dentro do Ubuntu/WSL do próprio STI (via socket, sem porta 3306 do Windows). O checkpoint seguinte `CHECKPOINT_2026-11-07_HOMOLOGACAO_MYSQL_PORTAL.md` confirma homologação REAL das migrações, 20 tabelas, bloqueios de integridade, política do portal e 96 testes (95 aprovados, 1 ignorado). As afirmações acima sobre indisponibilidade de MySQL são registro histórico do primeiro diagnóstico, não o estado atual. Concorrência real, E2E e produção continuam pendentes.
