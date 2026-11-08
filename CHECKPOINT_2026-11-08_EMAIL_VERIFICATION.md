# CHECKPOINT — Neuro-Diagnosis — Confirmação de e-mail e regularização assistida

Data local: 2026-11-08, America/Fortaleza.
Ambiente de execução: exclusivamente STI01 via NEXO (repositório sas_neuropsicopedagogia).
Base anterior: main e origin/main c9b6f31; git fetch retornou 0/0 antes do commit.
Estado: implementação local validada; commit, push e release pendentes.

## Contrato

- Toda conta criada pelo cadastro profissional ou pelo formulário administrativo (patient/responsavel, professional, admin e superadmin) recebe registro em saas_email_verifications como required=1, verified_at=NULL.
- Autenticação falha fechada até comprovação do e-mail; a aprovação do profissional pela administradora/BTA e a ativação do paciente/responsável continuam independentes. Não confundir verificação de e-mail com identidade clínica.
- Código aleatório de 6 dígitos válido por 10 minutos, 5 tentativas, até 3 envios por hora e mínimo 60 segundos entre envios; digest HMAC-SHA256 usando SECRET_KEY + id + e-mail + finalidade + nonce; não persistir o código em claro nem em logs.
- SMTP deve estar pronto; falha de envio deixa a conta pendente sem acesso. Reenvio público não revela se e-mail está cadastrado.
- O titular autenticado, com sessão fresca, MFA e senha atual pode pedir troca para novo e-mail. O endereço antigo permanece até confirmação do novo. Alteração revoga tokens de dispositivos confiáveis e OTPs de recuperação.
- Conta legada existente não é falsamente marcada como verificada. Na área Minha Conta o titular pode confirmar seu e-mail atual sem alterá-lo.
- A edição administrativa mostra os estados e-mail confirmado / aguardando código / legado não verificado.
- O SuperAdmin pode pedir regularização de endereço para um admin legado estritamente elegível: role admin, audit de bootstrap, ainda sem atos auditados, sem MFA habilitado e sem qualquer existência de clientes, avaliações, encontros ou admissões clínicas; sem acesso a prontuários. Exige senha do SuperAdmin, MFA, sessão fresca, CSRF. A operação não mostra OTP ao operador; novo endereço é confirmado pelo titular.
- Na confirmação de e-mail do administrador inicial, senha antiga é invalidada (hash aleatório descartado), must_change_password=1, dispositivos confiáveis e OTPs antigos são revogados; titular usa Recuperar senha no novo endereço confirmado. Contas com atividade/MFA não podem receber esse reset assistido, exigindo tratamento de identidade separado.
- O bloco de recuperação de senha no editor foi recolhido em details para UX mobile.

## Migração e pipeline

- Nova migração aditiva e idempotente scripts/mysql_saas_email_verification_migration.sql: tabelas saas_email_verifications e saas_email_challenges; índice único do endereço pendente.
- infra/host/deploy-neuro-diagnosis-saas.sh aplica a migração após backup e antes de iniciar nova imagem.
- Dockerfile copia novos módulos; sem configuração privilegiada extra.
- scripts/homologate_mysql_care.py aplica cada migração duas vezes em schema descartável e valida exclusividade.
- release canônica exige commit do código/push primeiro, seguido de commit separado em .release/request.json e observação do runner.

## Evidências verificadas no STI

- .venv/Scripts/python.exe, Python 3.14.
- unittest discover -s tests -q: 212 testes, OK (skipped=1), exit 0 (211 executados/aprovados).
- Testes direcionados de e-mail: 11 OK; incluem barreira no login, confirmação única, integridade HMAC, autorização para troca, bloqueio de contas com atividade e invalidação da senha legada.
- homologate_mysql_care.py: EMAIL_HOMOLOGATION_OK, MYSQL_HOMOLOGATION_OK tables=35, DISPOSABLE_HOMOLOGATION_SCHEMA_DROPPED, exit 0.
- git diff --check: 0; git fetch origin main: 0, divergência 0/0 antes do commit.
- Um ResourceWarning em SQLite durante unittest permanece sem falha (não confundir com falha de teste).

## Limitações e próximos passos

1. Ainda não houve prova de SMTP real de ponta a ponta com uma conta sintética/caixa efetivamente controlada pelo usuário: não afirmar que o e-mail chegou.
2. O fluxo administrativo legado é intencionalmente recusado se já houver atividade clínica ou MFA; não enfraquecer essa regra sem verificação humana formal da identidade.
3. Apenas contas criadas pelos canais normais são bloqueadas por verificação; o bootstrap de instalação inicial é operação privilegiada distinta e deve ser executado em ambiente de provisionamento controlado.
4. Não marcar cadastros antigos como verificados automaticamente; fornecer verificação individual.
5. Após push e release, confirmar commit no runner, saúde HTTP, migrations, controles e auditoria. Não operar em produção sem pipeline canônico.
6. Pasta local .visual_validation/ não faz parte deste commit.
