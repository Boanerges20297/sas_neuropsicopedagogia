# CHECKPOINT — 2026-11-08 — Correção do HTTP 500 pós-release e e-mail do administrador

Contexto: release neuro-prod-email-verify-20261108-01 commit 3ff59619c24b2dc4de67cb24c3fce1f4b21ddaad, pipeline indicou NEURO_PIPELINE_OK apesar de erros 500 autenticados em produção.

## Causa comprovada
- Traceback Docker Flask: pymysql.err.ProgrammingError (1146), tabela neuro_diagnosis.saas_email_verifications inexistente.
- Aplicação e runner haviam sido atualizados para 3ff5961, mas /usr/local/sbin/deploy-neuro-diagnosis (root:root 755) preservava hash antigo 73394cde...; a cópia versionada em /opt/neuro-diagnosis/infra/host/deploy-neuro-diagnosis-saas.sh tinha hash f46d1343... e adicionava a migração.
- A diferença entre os scripts instalados era precisamente o comando que aplicaria a migração. O healthcheck /saas/saude não verificava essas duas tabelas, portanto falso positivo no smoke.
- A documentação ARQUITETURA_ATENDIMENTO_PROFISSIONAL_CLIENTE_2026-11-07.md já avisava que o script instalado deve ser reconciliado explicitamente, não é atualizado automaticamente pelo checkout Git. Erro de procedimento foi desconsiderar esta advertência.

## Correção operacional executada na VPS (root autorizado via passkey)
- Backup SQL existente pre-release-3ff59619c24b-20261108T190853.sql verificado com 55.962 bytes.
- Migração aditiva scripts/mysql_saas_email_verification_migration.sql executada em MySQL real neuro_diagnosis, tabelas saas_email_verifications e saas_email_challenges criadas e listadas, ambas inicialmente vazias.
- Cópia instalada de script de deploy conciliada com fonte versionada f46d1343..., backup anterior root:root 600 em /var/lib/neuro-diagnosis/backups/deploy-neuro-diagnosis-before-email-20261108.sh. Comparação cmp e bash -n passaram; novo host script root:root 755.
- HTTP 200 local para /saas/entrar, /saas/verificar-email, /saas/saude e /health/ready. Nenhum restart manual nem deploy alternativo.

## Alteração explícita do e-mail do administrador inicial
- Solicitação do proprietário: trocar admin id=1 de admin@admin.com para liajpfort@gmail.com.
- Verificado: apenas um admin id=1, uma conta superadmin distinta, endereço novo livre, nenhum paciente/avaliação/atendimento/intake da administradora; já havia auditoria histórica de mudança de senha, aprovação profissional e trial, portanto não elegível ao caminho automático de bootstrap.
- Executado UPDATE transacional com filtros pelo id, papel, e-mail antigo, ativo e ausência de dados clínicos; um registro atualizado. Preservados password_hash, must_change_password, role, active e direitos. Tokens de recuperação existentes limpos e dispositivos confiáveis ativos revogados (se existentes).
- Backup SQL integral criado e validado: /var/lib/neuro-diagnosis/backups/pre-admin-email-fix-20261108T2004.sql (58.555 bytes, modo 0600).
- Resultado confirmado: id=1, email=liajpfort@gmail.com, role=admin, active=1, must_change_password=0; verificação via e-mail não foi artificialmente marcada como feita (COUNT=0). Uma auditoria admin_initial_email_repair foi registrada.
- Uma primeira tentativa de UPDATE falhou com MySQL 1093 por subquery no mesmo target users; nenhuma linha foi modificada na tentativa. Corrigido o SQL removendo subquery no próprio users e usando checagem de unicidade separada; segunda tentativa transacional passou.
- Não houve acesso a prontuários e não foram usadas senhas/OTP reais.

## Correção de código no STI01 (AINDA NÃO PUBLICADA)
- saas_routes.py: /saas/saude consulta ambas as tabelas de verificação de e-mail, retornando 503 se faltarem.
- infra/host/deploy-neuro-diagnosis-saas.sh: impede publicação se o executável root instalado /usr/local/sbin/deploy-neuro-diagnosis diferir da versão do script do SHA Git solicitado. **IMPORTANTE**: uma alteração neste próprio script deve ser pré-instalado de forma auditada no host antes da release; não acionar o runner antes de conciliar a cópia root.
- tests/test_neuro_runner_contract.py: teste do gate de hash e do health schema.
- tests/test_saas_schema_readiness.py: prova que cada tabela faltante causa HTTP 503 e a presença de ambas permite HTTP 200.
- Teste no STI: unittest discover -s tests -q: Ran 217 tests, OK(skipped=1), exit 0. git diff --check: exit 0.
- Repositório STI antes desta correção: main e origin/main 3ff5961 em sincronia, pasta .visual_validation/ não versionada.

## Lições duráveis
- NEURO_PIPELINE_OK só prova que os gates EXISTENTES passaram; não prova cobertura de novas migrações. Incluir em readiness toda tabela de que login/cadastro depende.
- Deploy versionado não atualiza script root independente. Antes de qualquer próxima release, comparar hashes do script do commit alvo com o host instalado e exigir conciliação autorizada; não executar mudanças root implícitas pelo runner.
- Sempre conferir schema real e rota representativa, não só liveness.
