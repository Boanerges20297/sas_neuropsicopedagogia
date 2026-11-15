# CHECKPOINT — Segurança gratuita, proteção DDoS e recuperação de senha

Data: 2026-11-07 — Neuro-Diagnosis
Ambiente de desenvolvimento: STI01 exclusivamente via NEXO.
Produção: NÃO modificada; sem release ou alteração de DNS.

## Solicitações aprovadas

- Priorizar soluções gratuitas de defesa contra ataques DDoS.
- Após 5 senhas incorretas para um mesmo e-mail normalizado, pausar novas tentativas por 10 minutos (janela deslizante de contagem de 15 minutos); não tornar possível bloqueio definitivo induzido por terceiros.
- Encaminhar o usuário à recuperação de senha por OTP de e-mail; envio SOMENTE após a solicitação explícita do usuário para não transformar o sistema em ferramenta de spam.
- OTP por e-mail: 4 dígitos, expira em 3 minutos, no máximo 3 tentativas por desafio, uso único e limites de envio de no máximo 3/h por conta e 60 segundos entre envios. Armazenamento de HMAC+nonce, jamais código em texto claro.
- TOTP de autenticador (6 dígitos/30 s) continua separado e obrigatório em contas novas. Redefinição por e-mail NÃO desbloqueia TOTP e invalida aparelhos confiáveis.
- E-mail remetente reservado: neuro-diagnosis47@gmail.com. Conta Gmail criada pelo responsável; senha de app AINDA NÃO instalada. Envio e verificação de código permanecem desativados até teste completo.

## Camadas técnicas

1. CDN/WAF gratuito (Cloudflare Free como opção): configuração de DNS e origem protegida dependem de ação futura expressa e validação prévia da infraestrutura. NÃO foi ativado.
2. Traefik: labels específicas do Neuro-Diagnosis em docker-compose.saas.yml, sem tocar no Traefik de outras aplicações: rate limiting geral 120 requisições/minuto com burst 60 e limite adicional para login/cadastro/recuperação 30/minuto com burst 15 por origem IPv4 ou prefixo IPv6 /64. Covers apex e www; não confiar em X-Forwarded-For sem configurar IPs de proxies confiáveis. Estes são valores conservadores iniciais, a calibrar após métricas reais.
3. Flask + MySQL: contador de login independente da sessão e do navegador, por HMAC de e-mail, cooldown de 10 minutos após 5 erros, sem armazenar IP nem identidade em claro na tabela de limites. Recuperação opcional gated por SMTP seguro com CSRF e respostas anti-enumeração.

## Novos arquivos

- saas_login_recovery.py: contador e OTP persistentes.
- saas_login_recovery_routes.py: páginas públicas CSRF-protegidas e reset sem login automático.
- scripts/mysql_saas_login_recovery_migration.sql: saas_login_attempt_limits e saas_password_recovery_otp, aditivas e idempotentes.
- templates/saas_recover_request.html e templates/saas_recover_confirm.html.
- tests/test_saas_login_recovery.py: testes isolados do quinto erro, HMAC, OTP desativado, CSRF e respostas.
- Modificados: saas_routes.py, templates/login.html, Dockerfile, docker-compose.saas.yml, infra/host/deploy-neuro-diagnosis-saas.sh, scripts/homologate_mysql_care.py, tests/test_saas_account.py, tests/test_saas_mfa.py.

## Gmail — preparação SEM CREDENCIAIS

Conta: neuro-diagnosis47@gmail.com.
O responsável precisa ativar verificação em duas etapas em https://myaccount.google.com/security
e gerar uma senha de app "Neuro-Diagnosis SMTP" em https://myaccount.google.com/apppasswords.
NUNCA compartilhar senha no chat, em arquivos versionados ou logs.

Parâmetros para o /etc/neuro-diagnosis/flask.env protegido da VPS:
  NEURO_EMAIL_OTP_ENABLED=false
  NEURO_SMTP_HOST=smtp.gmail.com
  NEURO_SMTP_PORT=465
  NEURO_SMTP_USER=neuro-diagnosis47@gmail.com
  NEURO_SMTP_FROM=neuro-diagnosis47@gmail.com
  NEURO_SMTP_SECURITY=ssl
  NEURO_SMTP_PASSWORD=<instalar SOMENTE em configuração secreta do servidor>

Somente após instalar a senha e comprovar handshake TLS + envio + recebimento:
  NEURO_EMAIL_OTP_ENABLED=true

Gmail exige 2FA para senha de app; se indisponível, avaliar OAuth2/transporte alternativo.
Não utilizar senha principal do Gmail em SMTP.

## Evidências de homologação no STI01

- 150 testes executados: 149 aprovados, 1 ignorado; SUITE_EXIT=0.
- scripts/homologate_mysql_care.py: MYSQL_HOMOLOGATION_OK tables=32, MYSQL_HML_EXIT=0; esquema descartável removido.
- YAML docker-compose.saas.yml parseado: COMPOSE_LABELS_OK 25, YAML_EXIT=0.
- git diff --check: DIFF_EXIT=0 (somente avisos CRLF/LF).
- Nenhum envio SMTP ou teste de produção realizado, uma vez que o usuário ainda não instalou a senha de app.

## Pendências para continuidade

1. Consolidar alterações em commit na main e push; não alterar .release/request.json.
2. Testar fluxo real de cinco senhas erradas, cooldown, OTP e recuperação com SMTP provisionado, em homologação isolada.
3. Definir e ativar Cloudflare Free no DNS sob autorização explícita; validar IP real no Traefik e restringir acesso direto à origem para evitar bypass. Revalidar limites após ativação do proxy.
4. Testar Traefik no runtime real via docker compose config e smoke canônico sem alterar outras aplicações.
5. Planejar expurgo periódico das tabelas de tentativas/códigos expirados e alertas de abuso.
6. Não realizar deploy sem autorização de release.
