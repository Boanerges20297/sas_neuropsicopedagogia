# CHECKPOINT — Neuro-Diagnosis | Contas administrativas, senhas e TOTP de primeiro acesso

Data: 2026-11-07 (America/Fortaleza)
Execução: STI01 exclusivamente via NEXO.
Base da etapa: fd855f2fd243b71761ac8a880c103f9eeacaa0a4 (main/origin/main).
Produção: NÃO MODIFICADA. Nenhum deploy ou release solicitado.

## Decisões confirmadas

- Superadmin e admin podem criar contas com permissões administrativas delimitadas; somente superadmin pode criar outro superadmin.
- Papel administrativo e atuação clínica são capacidades acumuláveis. O espaço clínico pertence ao próprio profissional; administração global NÃO concede acesso a prontuários de outros profissionais.
- Profissionais comuns permanecem sujeitos a licença BTA; admin/superadmin continuam isentos.
- Toda conta criada por administração exige troca da senha temporária na primeira entrada.
- Senha pessoal: 8 a 128 caracteres; pelo menos 2 letras, 4 números e 1 símbolo. Botão Sugerir senha na criação administrativa e na alteração pelo próprio usuário. Sugestão aleatória criptográfica local ao navegador, 16 caracteres; permite edição.
- Contas novas precisam escolher qualquer aplicativo autenticador TOTP compatível (Google, Microsoft, Aegis, 2FAS ou outro), escanear QR local ou cadastrar chave manual, confirmar primeiro código de seis dígitos antes de chegar ao painel. Escolha do fornecedor não é armazenada.
- Contas legadas não são bloqueadas automaticamente pelo novo requisito. Transição futura dependerá de planejamento.
- TOTP: SHA1 / 30 s / 6 dígitos, tolerância de um intervalo, proteção antirreplay e rate limit. Chaves criptografadas e vinculadas ao usuário. Oito códigos de recuperação de uso único e senha exigida para configurar.
- Dispositivo confiável opcional por até 30 dias: cookie Secure/HttpOnly/SameSite Strict, token opaco cujo hash fica no servidor, registro revogável, no máximo cinco dispositivos; troca de senha revoga os confiáveis.
- OTP por e-mail, distinto do TOTP, previsto com quatro dígitos e SMTP TLS, mas DESATIVADO. A conta remetente Neuro-Diagnosis não foi fornecida; nem um envio é autorizado antes da configuração. O transporte permanece desligado com NEURO_EMAIL_OTP_ENABLED=false.

## Implementação

- saas_account_provision.py, saas_account_access.py, saas_account_admin_routes.py: contas, direitos globais explicitamente limitados, criação auditada e capacidade de clínica privada.
- saas_login_policy.py: política de senhas unificada; saas_store.py: MFA obrigatório no provisionamento de contas novas, carregamento de direitos e estado MFA no login, invalidação de dispositivos após trocar senha.
- saas_mfa.py, saas_mfa_store.py, saas_mfa_routes.py: RFC 6238, login em duas etapas, configuração e recuperação. QR Code gerado no servidor com qrcode + PyPNG, sem serviço externo.
- templates/saas_accounts.html, saas_profile.html, saas_base.html, saas_mfa_challenge.html, saas_mfa_settings.html: interface de contas, botões de sugestão, primeiro acesso e dispositivos confiáveis.
- saas_email_otp_transport.py: integração SMTP preparatória, inativa por falta de credenciais/configuração.
- scripts/mysql_saas_account_rights_migration.sql e scripts/mysql_saas_mfa_migration.sql: quatro tabelas adicionais, aditivas e repetíveis. Dockerfile e deploy canônico incluem módulos e migrações após backup, antes do serviço web. requirements.txt inclui qrcode e pypng.
- scripts/homologate_mysql_care.py e novos testes de conta/MFA: isolamento, limitações e primeiro acesso.

## Evidências verificadas no STI01

- python -m unittest discover -s tests -q: Ran 145 tests, OK (skipped=1), ALL_UNIT_EXIT=0. São 144 aprovados e 1 ignorado.
- scripts/homologate_mysql_care.py: MFA_HOMOLOGATION_OK first_login_required=1 trusted_devices=0 explicit_rights=0.
- MYSQL_HOMOLOGATION_OK tables=30 tenants=2 blocked_invariants=5 guardian_unverified=1.
- DISPOSABLE_HOMOLOGATION_SCHEMA_DROPPED, MYSQL_HML_EXIT=0. Não houve conexão ao banco de produção.
- git diff --check: DIFF_EXIT=0 (apenas avisos de conversão CRLF/LF).
- QR Code gerado e testado localmente sem PIL; cryptografia RFC validada por vetor conhecido.

## Pendências

1. Confirmar git commit e sincronização origin/main; nenhuma ação em produção.
2. Validar visualmente no navegador e executar E2E com autenticação real em ambiente isolado; nunca inserir dados ou segredos reais em testes.
3. Integrar conta SMTP quando os dados forem fornecidos (segredos somente em .env seguro), com política de expiração, limites por IP/conta e auditoria para o OTP de quatro dígitos.
4. Planejar a habilitação gradual obrigatória de MFA para contas antigas, recuperação assistida e políticas de rotação de SECRET_KEY.
5. Após liberação futura específica: usar pipeline canônico e teste de smoke em produção.
