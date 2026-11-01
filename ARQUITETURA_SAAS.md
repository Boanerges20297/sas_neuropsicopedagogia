# Neuro-Diagnosis — arquitetura SaaS multi-tenant
**Estado:** proposta técnica inicial, sem migração de dados de profissionais em execução.
**Ambiente de análise:** STI01, repositório `sas_neuropsicopedagogia`.
**Identidade visual:** login mobile e desktop aprovados; implementação mantida independente das regras de domínio.
## 1. Modelo de produto
Neuro-Diagnosis será um SaaS para profissionais de psicologia e neuropsicopedagogia, com ambientes isolados para cada profissional ou organização. A unidade de isolamento é o **tenant** (espaço profissional). Por padrão, cada profissional recebe um tenant; no futuro, uma clínica poderá ter mais de um profissional e regras de compartilhamento explícitas.
## 2. Papéis
| Papel | Capacidades |
| --- | --- |
| Superadmin | Gerencia a plataforma, todos os tenants, contas, permissões globais, configurações, auditoria e eventuais planos/cobrança. Não é um cadastro público. |
| Administrador | Visão e supervisão global, fila de revisão, aprovação e veto de cadastros, instrumentos e operações submetidas. Toda consulta a dados pessoais ou clínicos exige motivo e gera trilha de auditoria. Não pode criar superadmins nem alterar controles de segurança da plataforma. |
| Profissional | Psicólogo ou neuropsicopedagogo. Gerencia apenas os clientes, instrumentos autorizados, avaliações, respostas, documentos e relatórios do seu tenant, salvo compartilhamentos expressamente autorizados. |
| Cliente (futuro) | Acesso por convite e recursos delimitados pelo profissional. Não acessa área administrativa ou dados de terceiros. |
A profissão deve ser atributo separado do papel: `profession = psicologo | neuropsicopedagogo`, e o sistema não deve presumir habilitação legal a partir de autodeclaração. Instrumentos restritos a psicólogos habilitados precisam de verificação profissional específica.
## 3. Entidades propostas
- `tenants`: id, nome, owner_user_id, status (pending/active/suspended), created_at.
- `tenant_members`: tenant_id, user_id, membership_role, status, joined_at.
- `professional_profiles`: user_id, profession, registro_profissional_quando_aplicavel, verification_status.
- `clients`: id, tenant_id, professional_id, dados mínimos, consentimento/bases aplicáveis, status.
- `tests`: category_id, tenant_id nulo para instrumentos globais, autor, status de aprovação e versionamento.
- `assessments`: id, tenant_id, client_id, test_version_id, responsible_user_id, status, timestamps.
- `responses`: tenant_id, assessment_id, valores e referências a documentos; migrar respostas legadas com regras explícitas de autoria.
- `review_requests`: id, tenant_id, entity_type, entity_id, action, requested_by, status, decided_by, decided_at, reason.
- `audit_events`: actor_id, tenant_id, action, resource, resource_id, reason, timestamp, outcome, correlation_id.
- `subscriptions` (fase posterior): tenant_id, plan_id, status, payment_provider_reference.
Documentos/anexos devem possuir tenant_id, acesso autenticado e regra de retenção; nunca URL pública enumerável.
## 4. Regras invariantes de segurança
1. Em toda consulta, atualização, exclusão, exportação e download de clientes ou avaliações: validar `tenant_id` do usuário no servidor. Não confiar em IDs ou tenant_id fornecidos pelo navegador.
2. Em ações globais do administrador/superadmin: exigir papel global, motivo/contexto e auditoria. Jamais conceder acesso global a contas `user` por inferência.
3. Nunca misturar dados de tenants em dashboards, buscas, CSVs, gráficos, nomes de arquivos, background jobs e caches.
4. Questionários destinados a clientes devem usar convite/token exclusivo e expiração, associados a um tenant e avaliação. Os endpoints públicos atuais precisam revisão antes de conter dados clínicos reais.
5. Proteger sessões, redefinição de senha, uploads, logs e backups; não colocar dados sensíveis no Git.
6. Toda mudança deve ter testes negativos: um profissional tenta visualizar, alterar, excluir, pontuar e baixar registros de outro e recebe 403/404 sem vazamento.
7. O banco SQLite atual não oferece Row Level Security. A aplicação deve impor filtros e autorizações sistematicamente; considerar PostgreSQL com RLS antes de escalar ou atender instituições maiores.
8. Tratamento de dados pessoais sensíveis depende de governança e fundamento legal adequado; não declarar conformidade automática com a LGPD.
## 5. Fluxos de aprovação
- Cadastro profissional: `pending -> approved | rejected`; rejeição com justificativa, histórico imutável e comunicação ao interessado.
- Instrumentos e formulários: rascunho privado, submissão, aprovação/veto, versão publicada; alterações em versões aprovadas geram nova revisão.
- Acesso de administradores a prontuários/avaliações: somente quando necessário e autorizado, com auditoria reforçada; o profissional continua responsável pelas conclusões clínicas.
- Suspensão de usuário/tenant: ação auditada, preservando registros e políticas de retenção.
## 6. Plano de implantação sem regressões
**Fase A — login (em andamento):** aplicar UI aprovada sem modificar o backend de autenticação ou alterar contas.
**Fase B — fundação SaaS:** migração aditiva com tenants, membros, perfis, auditoria e status; testes do esquema, sem alterar respostas legadas de forma irreversível.
**Fase C — isolamento:** tela profissional, cadastro de clientes e autorização centralizada; migrar rotas, consultas e anexos gradualmente, com testes de IDOR e permissões.
**Fase D — aprovação:** fila administrativa, status, justificativas e trilhas de auditoria. Separação rigorosa de superadmin e admin.
**Fase E — privacidade/produção:** revisão de questionários públicos, dados sensíveis no repositório, backups e adequação jurídica/profissional; homologação e só então publicação por pipeline autorizado.
### Estado atual confirmado em código
A aplicação Flask atual usa `users.role` para `user`, `admin` e `superadmin`. O método `is_admin()` trata `admin` e `superadmin` de forma equivalente; não existem tenants, clientes/profissionais isolados ou uma fila de aprovação. Rotas administrativas globais acessam `responses` sem tenant. A fundação SaaS **ainda não está implementada**.
Este documento representa um **contrato de direção**, não a afirmação de que o SaaS já possui isolamento efetivo.
