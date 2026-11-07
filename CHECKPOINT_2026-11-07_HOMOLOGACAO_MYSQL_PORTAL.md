# Checkpoint — homologação MySQL e arquitetura de acesso do responsável
**Data:** 2026-11-07 | **Máquina:** STI01, via NEXO Commander
**Repositório:** Boanerges20297/sas_neuropsicopedagogia
**Baseline conciliada:** main/origin/main = 4feaccdbe694ccccf0787c3b1faf24c5d37e0397.
**Status:** implementado e validado em homologação; NÃO PUBLICADO.

## Resultado da homologação REAL, não simulado
- STI possui Ubuntu WSL com MySQL **8.4.8** por socket Unix, apesar de não escutar TCP/3306 no host Windows. Não foi necessário instalar MySQL ou Docker.
- Script reproduzível `scripts/homologate_mysql_care.py` executado via Python Windows do próprio STI.
- Criou banco exclusivo `neuro_hml_<12 hexadecimal>`, verificou nome livre antes da criação e descartou o banco ao final, inclusive após erro.
- Aplicou SQL canônico completo (bootstrap SaaS sem CREATE USER/GRANT, perfil profissional, NeuroCore, atendimento e portal), repetindo migrações aditivas.
- **20 tabelas** resultantes; **dois profissionais**, **três pacientes fictícios**, um contato fictício, um agendamento e uma sessão em rascunho.
- MySQL rejeitou 5 violações: paciente de outro tenant; paciente errado no mesmo tenant; profissional errado na sessão; UUID duplicado; intervalo de término anterior ao início.
- Portal de responsável: negado por padrão; exige verificação explícita, autorização com escopo e prazo, vínculo com paciente e profissional; rejeita vínculo cruzado; revogação do contato cancela imediatamente o acesso.
- Saída observada: `PORTAL_POLICY_HOMOLOGATION_OK ...`, `MYSQL_HOMOLOGATION_OK tables=20 tenants=2 blocked_invariants=5 guardian_unverified=1` e `DISPOSABLE_HOMOLOGATION_SCHEMA_DROPPED`. Exit code 0.
- Foram usados apenas dados sintéticos, sem chamados externos, segredos ou prontuários.

## Novos arquivos
- `scripts/homologate_mysql_care.py`: validação SQL real e automatizada no STI.
- `scripts/mysql_care_portal_access_migration.sql`: `care_portal_identity_links` e `care_portal_grants` inicialmente pendentes; chaves FK compostas impedem mudança de vínculo entre pacientes/tenants.
- `saas_portal_policy.py`: consulta fail-closed, exige principal SaaS do tipo paciente, responsável legal verificado, permissão explícita (agenda ou documentos liberados), revisão profissional e não expiração.
- `tests/test_saas_portal_policy.py`: proteção contra inputs inválidos, acesso negado por padrão, checagem SQL, contrato de migração e ausência de rotas de portal.
- `scripts/mysql_care_workflow_migration.sql`: chave única adicional necessária para FK composta contato ↔ identidade.
- `infra/host/deploy-neuro-diagnosis-saas.sh`: adiciona migração do portal após a migração de atendimento, no fluxo após backup.
- `Dockerfile`: inclui `saas_portal_policy.py`.
- `saas_routes.py`: health/readiness verifica estrutura de grants.

## Testes
Suíte completa: **96 testes, 95 aprovados, 1 ignorado, 0 falhas**.
Homologação real de banco MySQL: passou integralmente, inclusive repetição de migrações.
Nenhum endpoint de portal foi disponibilizado; nenhuma concessão real de acesso foi feita.

## Pendências para seguir
1. Validar autenticação + sessão do responsável, comprovação de identidade/guarda e política de autorização/revogação, com revisão de LGPD e crianças.
2. Criar fluxo explícito de liberação por profissional; `released_documents` não implica acesso a documentos sem revisão/liberação individual.
3. Integrar portal somente depois de teste E2E com usuários fictícios e aprovação profissional; sem expor prontuário automaticamente.
4. Testar visualmente em desktop/mobile e instrumentar auditoria de leituras e operações do futuro portal.
5. Para produção: confirmar script instalado em `/usr/local/sbin/deploy-neuro-diagnosis` antes da release, executar backups e novas migrations pelo pipeline canônico. Nenhum deploy foi solicitado.
6. Testes de homologação são fortes para FK, mas **não** validam ainda concorrência real simultânea de múltiplas transações nem aplicação completa com navegador. Não declarar tudo validado até esses testes.

## Regras inegociáveis
Administradora não herda registros clínicos de terceiros. Profissionais comuns seguem BTA. Portal não acessa dados clínicos por igualdade de e-mail ou simples cadastro. NeuroCore não diagnostica automaticamente. Não usar dados sensíveis em treinamento.
