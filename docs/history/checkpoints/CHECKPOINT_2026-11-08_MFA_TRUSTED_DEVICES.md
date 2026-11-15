# Checkpoint — Neuro-Diagnosis | MFA de administradores e dispositivos confiáveis

Data: 2026-11-08 (America/Fortaleza)
Ambiente: STI01 via NEXO Commander, pasta `Desktop/Projetos/sas_neuropsicopedagogia`.
Base inspecionada: `main` e `origin/main` em `ab7f3c56c19c60c1fabb46f7ac9742bc542170a7` antes da consolidação.
Estado: implementação local validada, ainda sem release/deploy de produção.

## Requisitos retomados do chat “Continuar próximos passos”

- Admin e superadmin não devem entrar em ambiente administrativo apenas com senha em dispositivo desconhecido quando TOTP está habilitado.
- Aparelho reconhecido mediante TOTP e escolha explícita do usuário: acesso posterior por senha por até 30 dias; máximo de cinco dispositivos; revogação possível.
- Aparelho temporário: sem token persistente; sessão expira após 15 minutos de inatividade.
- Primeiro cadastro TOTP: oferecer QR Code, chave manual copiável para quem não consegue escanear o QR e confirmação por código de seis dígitos.
- Contas administrativas legadas sem TOTP precisam concluir a configuração antes de usar a área protegida.
- Superadmin governa contas, direitos e catálogo de instrumentos, mas nunca consulta prontuários, respostas ou avaliações de pacientes.
- Catálogo administrativo com busca, filtro de situação e paginação; SQL parametrizado.

## Evidências executadas no STI01

- Usado `.venv/Scripts/python.exe`, não o `python` global sem dependências.
- `.venv/Scripts/python.exe -m unittest discover -s tests -q`: 192 testes, OK, um skipped. Exit code 0.
- `.venv/Scripts/python.exe scripts/homologate_mysql_care.py`: banco isolado `neuro_hml_<id aleatório>` no MySQL 8 via WSL; `MYSQL_HOMOLOGATION_OK tables=33 tenants=2 blocked_invariants=5 guardian_unverified=1`; `MFA_HOMOLOGATION_OK`; `DISPOSABLE_HOMOLOGATION_SCHEMA_DROPPED`; exit code 0.
- `git diff --check`: exit code 0 (apenas avisos LF/CRLF).
- `git fetch origin main`: exit code 0; main e origin/main sem divergência antes de commit.
- Testes específicos novos: fluxo TOTP desconhecido vs. reconhecido, adesão explícita à confiança, primeiro cadastro, cookie seguro, expiração da sessão temporária e opção de chave manual.

## Limitações e pendências

- Os testes de integração são locais/sintéticos; o fluxo de autenticação **ainda deve ser verificado por navegador real no endpoint de produção após implantação controlada**.
- Não houve alteração de banco de produção, DNS, Traefik, `.release/request.json` nem envio de OTP real nesta etapa.
- As imagens de validação visual já existentes em `.visual_validation/` permaneceram fora do commit.
- Antes de publicar: revisar diff final, efetuar commit/push na main com saída comprovada, seguir pipeline canônico e executar smoke em produção com conta de teste e dispositivo reconhecido/desconhecido.
