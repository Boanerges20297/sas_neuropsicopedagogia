# Checkpoint — Agenda profissional e solicitações no portal
Data: 2026-11-10 | Projeto: Neuro-Diagnosis | Ambiente: STI01 via NEXO
Repositório: Boanerges20297/sas_neuropsicopedagogia, main

## Entregue em código
- UX de pacientes: busca com campo de 52px, padding e foco acessível; filtros adaptados ao mobile.
- Agenda profissional: marcar diretamente paciente próprio, escolher data/hora/duração/tipo/modalidade; editar consulta futura ativa, cancelar com preservação histórica.
- Disponibilidade: publicar vagas por período de até 31 dias, dias da semana, janela diária, duração, intervalo, tipo e modalidade; editar e retirar horários livres.
- Solicitações: paciente vinculado/identificado com grant `appointments` vê vagas do próprio profissional e pode solicitar/cancelar. O horário fica `pending` para impedir duplicidade; profissional confirma (cria `care_appointments`) ou rejeita (libera vaga).
- Segurança: escopo por tenant, profissional e paciente; controle de consentimento adulto/guardião existente; CSRF, POST, transações com bloqueio da filiação profissional, auditoria e ausência de exposição de prontuários.
- Migração aditiva `care_schedule_slots` em `mysql_care_workflow_migration.sql`. Não altera a cópia do script root instalada na VPS.
- Dockerfile inclui `saas_slot_booking.py` e `saas_slot_routes.py`; verificação de readiness exige tabela nova.
- Portal de agenda apenas para contas `patient` já ativadas e com vínculos/grants/consentimentos verificados. Sem convite automático, novos logins ou liberação de testes.

## Verificações no STI
- `python -m unittest discover -s tests -q`: 279 testes, OK, 1 ignorado.
- Testes focados: 33 OK.
- MySQL 8 em esquema descartável: 42 tabelas, migrações repetidas, `SCHEDULE_MYSQL_HOMOLOGATION_OK`, FK/estados e transição open/pending/booked; esquema descartável apagado.
- `scripts/pipeline_contract.py`: OK; `git diff --check`: OK.
- Sem dados clínicos reais alterados.

## Operação e limitações
- Não disparar deploy manual; releases apenas pelo gatilho versionado `.release/request.json` na `main`.
- A implementação só estará em produção após um release explícito concluído e smoke HTTPS.
- A área do paciente respeita habilitação e consentimento prévios. Não confundir solicitação de acesso ao portal com conta autorizada.
- Agendamentos cancelados e horários retirados são preservados em banco/auditoria, nunca apagados fisicamente.
- Listagens limitadas para desempenho: profissional até 250 slots futuros e paciente até 100 vagas. Paginação/filtragem avançada poderá ser adicionada posteriormente.
- Pasta local `.visual_validation/` preservada, fora do commit.
