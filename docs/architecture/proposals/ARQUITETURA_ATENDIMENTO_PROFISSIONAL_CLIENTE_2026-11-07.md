# Neuro-Diagnosis — Arquitetura do atendimento profissional / cliente
**Revisão:** 2026-11-07 | **Status:** arquitetura especificada; primeira fatia implementada **apenas no código do STI01**. Não publicada.
**Repositório:** Boanerges20297/sas_neuropsicopedagogia · branch main.
**Princípio:** primeiro garantir identidade, isolamento, agendamento e rastreabilidade; depois construir instrumentos, portal e inteligência assistiva.

## 1. Camadas e responsabilidades

```mermaid
flowchart TD
 U[Profissional / Administradora] --> W[Web Flask /saas]
 G[Cliente ou responsável legal] -. futuro: acesso verificado .-> P[Portal do cliente: ainda desativado]
 P -. autenticação e grants .-> W
 W --> A[Identidade, CSRF, autorização e BTA]
 A --> S[Serviços: clientes, agenda, sessões, instrumentos]
 S --> DB[(MySQL: tenants + pacientes + agenda + auditoria)]
 S --> N[NeuroCore: evidências TEA/TDAH e bibliografia]
 STI[STI01: testes + treinamento TF-IDF] -->|índice versionado, aprovado| N
 ```

- **Flask SaaS:** autenticação, perfis, rotas profissionais e apresentação.
- **Autorização clínica:** sempre (tenant ativo + profissional responsável + paciente próprio). Ser admin não dá acesso a fichas de outros.
- **BTA:** profissionais comuns precisam de licença válida; admin/superadmin autenticados têm isenção comercial, mas só acessam seu próprio espaço clínico explicitamente criado.
- **MySQL:** dados operacionais e clínicos autorizados; sem usar a camada legada SQLite.
- **NeuroCore:** recupera evidências e informa lacunas documentais. Não diagnostica, não pontua risco, não substitui profissional habilitado.
- **Treinamento:** scikit-learn somente no STI; execução leve na VPS, com índice versionado.

## 2. Ciclo de vida do atendimento

| Etapa | Responsável | Estado / contrato | Implementação |
|---|---|---|---|
| Cadastro de profissional | Profissional | pendente até aprovação da admin | já existente |
| Espaço profissional / licença | Admin + BTA | tenant ativo; trial 14 dias quando aprovado | já existente |
| Cadastro de cliente | Profissional | cliente próprio; sem acesso automático ao portal | já existente |
| Contato/responsável legal | Profissional e responsável | não verificado → verificado → revogado; exigir evidência de autoridade | **tabela pronta, fluxo pendente** |
| Agendamento | Profissional | agendado → confirmado → realizado / cancelado / não compareceu | **rotas, dados e UI implementados no STI** |
| Sessão | Profissional | rascunho gerado após presença; assinatura/registro clínico requer controles adicionais | **registro básico preparado, editor pendente** |
| Instrumentos | Profissional habilitado | versão aprovada → aplicação → envio → revisão | catálogo e schema existentes; aplicação pendente |
| NeuroCore TEA/TDAH | Profissional | documentação e pesquisa de referências sem diagnóstico automatizado | experimental no código |
| Devolutiva | Profissional | comunicação só de conteúdo explicitamente aprovado | fluxo pendente |
| Portal do cliente | Cliente/responsável verificado | acesso restrito por vínculo e permissões granulares | **não habilitado** |
| Encerramento | Profissional | motivo, data, retenção e auditoria, sem apagar histórico indevidamente | fluxo pendente |

### Máquina de estados de agendamento
- `scheduled` → `confirmed`, `completed`, `cancelled` ou `no_show`.
- `confirmed` → `completed`, `cancelled` ou `no_show`.
- `completed`, `cancelled` e `no_show`: terminais, sem transição posterior nesta etapa.
- Concluir ou registrar ausência de um evento futuro é bloqueado; evento realizado abre **uma** sessão documental `draft`.
- Cancelar libera o intervalo. Idempotência de criação por UUID evita duplo agendamento.
- Data/hora inserida em `America/Fortaleza`, persistida em UTC no MySQL.

## 3. Contratos de dados

**Entidades pré-existentes**: `users`, `tenants`, `tenant_members`, `clients`, `tests`, `test_versions`, `assessments`, `assessment_responses`, `audit_events`, `neurocore_evidence_reviews`.

**Novas entidades, por migração aditiva**:
- `care_client_contacts`: contatos e responsáveis com estado inicial NÃO verificado. Cadastrar não concede permissão no sistema.
- `care_appointments`: agendamento por tenant/cliente/profissional, tipo de atendimento, modalidade, intervalo UTC, fuso, status e UUID idempotente.
- `care_encounters`: registro de sessão criado com atendimento concluído, único por agendamento e inicialmente em rascunho. Não armazena narrativas clínicas nesta fase.

**Integridade e concorrência:** FKs tenant-compostas, índices de consulta por profissional e cliente, seleção transacional com `FOR UPDATE` no vínculo de membro antes de verificar conflitos, unicidade de UUID. Toda alteração de agenda passa por auditoria sem incluir narrativas clínicas.

## 4. Rotas no código do STI

| Método | Caminho | Público |
|---|---|---|
| GET | `/saas/agenda` | profissional autenticado, ativo e licenciado, no próprio tenant |
| GET/POST | `/saas/pacientes/<id>/agenda` | proprietário do cliente; POST exige CSRF |
| POST | `/saas/pacientes/<id>/agenda/<appointment_id>/acao` | proprietário do cliente; transições permitidas, CSRF |
| GET | `/saas/pacientes/<id>` | proprietário do cliente; atalhos NeuroCore e agenda |
| GET/POST | `/saas/pacientes/<id>/neurocore/<tea|tdah>` | proprietário; revisão documental |
| — | `/portal/...` | **não existe; não anunciar aos clientes ainda** |

### Permissões
- **Superadmin/admin**: administram contas e aprovações, mas **não** acessam prontuários alheios; só atendem no próprio tenant clínico após ativação explícita.
- **Profissional**: gerencia clientes, agenda, avaliações e registros de sua titularidade sob BTA válido.
- **Cliente/responsável**: não pode acessar dados pelo simples e-mail ou por associação nominal. Requer verificação de identidade/vínculo, convite expirável, autorização de acesso e revogação.
- **Paciente menor**: acesso por responsável legal deve ter verificação independente, tratamento proporcional à idade e finalidade; não herdar permissão genérica de contas familiares.
- **Compartilhamento interprofissional**: negar por padrão; futuramente conceder por escopo, propósito, validade e auditoria, com base legal apropriada.

## 5. Segurança, privacidade e conformidade
- HTTPS, CSRF, sessão autenticada, autorização **na rota e no SQL**, isolamento por tenant, auditoria com IDs e ações.
- Proteção específica para dados de saúde e de crianças: finalidade, minimização, acesso restrito, bases legais documentadas e revisão de LGPD.
- **Não enviar narrativas clínicas para modelos ou APIs externos por padrão.**
- Conduzir desenho de consentimentos, responsável legal, retenção, exclusão/anonimização quando cabível, exportação e recuperação de backup antes de operar com pacientes reais.
- Instrumentos psicológicos dependem da habilitação do usuário e de autorizações/licenças; não importar testes protegidos indiscriminadamente.
- Editor de notas clínicas e portal exigem modelo próprio de confidencialidade, imutabilidade de assinatura, histórico de alterações e proteção criptográfica em repouso; não improvisar como campo texto livre.

## 6. Infraestrutura e implantação
**STI01** edita/testa → **Git `origin/main`** é fonte de código → **pipeline canônico** coleta um novo `.release/request.json` autorizado → gateway restrito faz backup MySQL, migração, build Docker e smoke test.

**Gate de publicação obrigatório:** a cópia do script instalada na VPS (`/usr/local/sbin/deploy-neuro-diagnosis`) deve ser reconciliada e verificada com o script versionado, sob autorização; apenas editar `infra/host/deploy-neuro-diagnosis-saas.sh` no Git não altera a cópia instalada.

Migrações na ordem: `mysql_saas_profile_migration.sql` → `mysql_neurocore_review_migration.sql` → `mysql_care_workflow_migration.sql` → `mysql_care_portal_access_migration.sql`; confirmar backup, índices, tabelas e endpoint de saúde. **Sem release automática nesta etapa.**

## 7. Critérios de aceite pendentes para uso real
1. Migrações ensaiadas em MySQL de homologação descartável e backup/restauração verificados.
2. Dois profissionais + dois pacientes **sintéticos**, com testes de negação cruzada inclusive via URL direta, concorrência simultânea e duplo clique.
3. Validação visual mobile/desktop, calendário, tempo/fuso e estados, com revisão pela administradora.
4. Revisão de responsável legal, consentimento/autorizações específicas e proteção de dados antes de permitir portal ou relatos clínicos.
5. Aplicação e revisão de instrumentos versionados por papel/habilitação; não usar critérios do DSM como pontuação diagnóstica.
6. Teste de execução containerizada de produção e script instalado, seguido de release pelo pipeline canônico quando aprovado.

**Adendo 07/11/2026 — conta e paciente não são sinônimos:** leia DECISAO_PACIENTE_CONTA_RESPONSAVEL_2026-11-07.md. Adulto responde por si; menor é paciente com responsável titular de UMA conta, sem login próprio. O registro clínico usa nome, DOB/idade derivada e relato inicial criptografado. O autoatendimento de adultos e a vinculação/verificação de responsáveis ainda não estão liberados.

**Resumo:** o backend e as interfaces iniciais de agenda são uma primeira fatia executável. Portal, consentimento operacional, notas clínicas seguras, avaliações completas e compartilhamento ainda não estão prontos. Não apresentar o SaaS como serviço clínico integralmente implantado antes de cumprir esses critérios.
