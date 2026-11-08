# Checkpoint — Neuro-Diagnosis | SuperAdmin: edição de contas e recuperação de senha

Data: 2026-11-08 (America/Fortaleza)
Ambiente de execução: STI01 via NEXO, `sas_neuropsicopedagogia`.
Base: commit `c4d3b13771953b254df6628774da714bb4f03bf7` (main/origin/main).
Estado: implementação e homologação local concluídas; commit, push e release desta etapa ainda pendentes.

## Solicitação e limite de confidencialidade

SuperAdmin deve editar cadastros e iniciar redefinição de senhas, sem poder ler prontuários. A edição já existente cobre nome, papel, status e direitos administrativos; a nova ação é exclusiva do SuperAdmin.

## Fluxo implementado

- Formulário de edição em `/saas/contas/<id>/editar`, com ação `POST /saas/contas/<id>/recuperar-senha` visível apenas para SuperAdmin.
- Autorização exige sessão de administrador, perfil SuperAdmin, MFA concluído, sessão de login fresca, CSRF e reentrada da própria senha do operador.
- O SuperAdmin NÃO recebe código OTP nem senha de terceiro. Serviço existente `saas_login_recovery.request_reset(email_cadastrado)` envia código de 4 dígitos para o titular por SMTP, respeitando cooldown (mínimo 60s, máximo 3/h), expiração 3min e no máximo 3 tentativas. O titular conclui a redefinição na tela existente.
- Se SMTP estiver indisponível ou limite excedido, nenhuma senha é alterada e a interface não declara envio bem-sucedido.
- A conclusão da troca revoga tokens de dispositivos confiáveis; TOTP não é removido.
- Operação bem-sucedida de solicitação é auditada como `admin_password_recovery_requested` sem código nem senha.
- Conta inativa não recebe recuperação. Outros administradores não têm essa operação.

## Segurança adicional necessária

Como a edição administrativa permitia substituir diretamente o e-mail de recuperação e depois solicitar um OTP para si mesmo, `saas_account_management.update_managed_account` agora proíbe mudança de e-mail de conta existente pelo operador, seja ativa ou suspensa. A tela sinaliza que o titular deve alterar o endereço com autenticação própria. Fluxo de correção administrativa com verificação de identidade fica pendente de implementação futura; não contornar por SQL manual.

## Evidência local

- Testes focalizados `test_saas_account_management_actions.py`: 26 testes, OK.
- Suíte completa: 198 testes, OK, 1 skipped (197 aprovados), exit code 0.
- MySQL 8 de homologação no STI: 33 tabelas; `MYSQL_HOMOLOGATION_OK`, `MFA_HOMOLOGATION_OK`, `DISPOSABLE_HOMOLOGATION_SCHEMA_DROPPED`, exit code 0.
- `git diff --check`: exit code 0.
- Nenhum segredo, OTP real, senha em claro ou prontuário manipulado na homologação.

## Pendências de release

1. Revisar diff; commit e push via STI na main sem alterar `.release/request.json` no commit do código.
2. Em commit separado, atualizar `.release/request.json` com requestId único e versão de `release.json` depois de confirmar saúde do runner e rollback; publicar somente pelo pipeline canônico.
3. Conferir runner, SHA implantado, migrações, health HTTPS e Issue #2.
4. Validar login SuperAdmin com dispositivo desconhecido/confiável e recuperação real por e-mail de conta sintética em navegador HTTPS, sem expor credenciais.
5. Não declarar que envio SMTP ou fluxo completo E2E estão validados até evidência real de envio e recebimento.

## Limitação residual

A revogação de tokens de dispositivo confiável não implica revogação instantânea de todas as sessões web antigas; avaliar versionamento/revogação de sessões em etapa de hardening.
