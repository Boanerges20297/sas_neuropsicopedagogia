# CHECKPOINT — Configuração SMTP do Neuro-Diagnosis

**Data:** 2026-11-07 (America/Fortaleza)
**Ambiente de desenvolvimento:** STI01 via NEXO
**Remetente autorizado:** neuro-diagnosis47@gmail.com
**Produção:** NENHUM deploy ou restart efetuado nesta etapa.

## Decisão

O usuário decidiu configurar diretamente os arquivos `.env` do STI01 e da VPS, usando inicialmente a senha de app do Gmail atual. A senha já havia sido divulgada na conversa e deverá ser trocada posteriormente. Nenhuma credencial é registrada neste checkpoint ou nos commits.

## Verificações objetivas

- STI01: existem as sete chaves `NEURO_EMAIL_OTP_ENABLED`, `NEURO_SMTP_HOST`, `NEURO_SMTP_PORT`, `NEURO_SMTP_USER`, `NEURO_SMTP_FROM`, `NEURO_SMTP_SECURITY`, `NEURO_SMTP_PASSWORD` no `.env` ignorado pelo Git.
- VPS `/etc/neuro-diagnosis/flask.env`: mesmas sete chaves presentes; modo `600`, proprietário `root`.
- VPS: `NEURO_EMAIL_OTP_ENABLED=true`; servidor `smtp.gmail.com`, porta `465`, modo `ssl`, usuário/remetente correto e senha com formato esperado (16 letras após remover espaços). Nenhum valor de senha foi exibido.
- VPS: TCP/TLS estabelecido nas portas 465 e 587; EHLO/NOOP concluídos com código 250 e suporte AUTH anunciado. A primeira autenticação real SMTP na porta 465 terminou com `SMTPServerDisconnected`; não houve aceite de mensagem pelo servidor. Uma nova tentativa foi bloqueada pelas configurações de segurança da ferramenta. Não contornar o bloqueio.
- VPS: `neuro-diagnosis-flask` saudável, porém a execução atual **não carregou** `NEURO_EMAIL_OTP_ENABLED` nem as credenciais SMTP. A versão de código implantada permanece anterior ao fluxo de recuperação por e-mail. Apenas atualizar `.env` não injeta variáveis em container existente.
- Não foi enviado nenhum OTP real; serviço de recuperação de senha **não está operacional em produção**.

## Código no STI01

- `saas_email_otp_transport.py`: lê credenciais `.env` por padrão; o modo de gerenciamento de senha via painel é opcional e só é habilitado explicitamente com `NEURO_SMTP_WEB_CONFIG_ENABLED=true`.
- `docker-compose.saas.yml`: removida a habilitação forçada do modo web, que ignoraria o `.env` já preenchido.
- `saas_smtp_admin_routes.py`, `saas_smtp_settings.py`, `templates/saas_smtp_admin.html`: blueprint de administração futura, inativo no modo direto `.env`. Exige superadmin, sessão recente, TOTP ativo, CSRF e reautenticação; dados criptografados no MySQL quando modo web explicitamente ligado.
- `scripts/mysql_saas_smtp_settings_migration.sql`: tabela aditiva para configuração opcional.
- `Dockerfile`, `infra/host/deploy-neuro-diagnosis-saas.sh` e `scripts/homologate_mysql_care.py`: empacotamento e migrações.
- `templates/saas_base.html`: link web de SMTP visível apenas quando o modo web estiver habilitado.

## Testes

- `python -m unittest discover -s tests -q`: **Ran 156 tests, OK (skipped=1)**; 155 aprovados, 1 ignorado, nenhum erro.
- `scripts/homologate_mysql_care.py`: **MYSQL_HOMOLOGATION_OK tables=33**; esquema descartável removido.
- `git diff --check`: sem erros (apenas avisos esperados de conversão LF/CRLF).

## Pendências antes de deploy

1. Obter autenticação SMTP comprovada e mensagem aceita pelo servidor Gmail. Investigar o fechamento durante `AUTH` por meio do console de segurança da própria Conta Google e/ou teste autorizado após liberação; não presumir senha correta pelo formato.
2. Só após o teste SMTP: executar pipeline canônico de produção com migrações, backup e smoke; sem `docker compose down -v`, sem reiniciar MySQL.
3. Após deploy, verificar ambiente carregado no container, rota de recuperação e ponta a ponta: 5 senhas incorretas, limitação, solicitação de OTP, recebimento, expiração, tentativa incorreta, redefinição, invalidação de aparelho confiável e TOTP preservado.
4. Revogar a senha de app divulgada no chat e gerar outra após estabilização; manter fora do Git e dos registros de auditoria.
