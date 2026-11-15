# CHECKPOINT — Recuperação de senha: entrada com código e redirecionamento SaaS

Data: 2026-11-08 (America/Fortaleza).
Ambiente: STI01 via NEXO. Repositório: sas_neuropsicopedagogia, branch main.
Base de origem da correção: f6aa3ec31249a973b750c119bc8e8033906dc955.

## Relato de produção
- Às 17h37, após solicitar a recuperação da senha da administradora pelo SuperAdmin, o código de quatro dígitos chegou no e-mail da titular. Porém, a página de administração exibiu Bad Gateway.
- Screenshot do usuário às 17h37 mostrou 502 no endereço /saas/cont... e outro screenshot da raiz do domínio com "Acesso exclusivo ao espaço SaaS".
- Logs do container Flask/Gunicorn: nova inicialização em 2026-11-08 20:37:12 UTC, equivalente a 17h37 de Fortaleza. Portanto, o 502 é temporalmente consistente com uma indisponibilidade transitória durante a recriação do container na release. Não há prova de que o POST SMTP por si só causou o 502: logs recentes do Gunicorn não mostram traceback desse POST.
- Diagnóstico verificável do segundo screenshot: app.py bloqueava rotas legadas para usuários MySQL SaaS ANTES de redirecionar a raiz do domínio e /login ao painel SaaS. O bloqueio 403 era inadequado para GET / de uma sessão válida.
- Descoberta UX: já existia a rota /saas/recuperar-senha/confirmar, mas o login ocultava seu acesso. "Esqueci minha senha" conduzia a solicitar novo OTP (separado do fluxo de digitar OTP recebido), gastando a janela de 3 min.

## Correções no STI01
- app.py: para SaaSUser autenticado e GET/HEAD de / ou /login legado, redireciona ao painel SaaS, que continua aplicando MFA, sem autorizar nenhuma rota SQLite legada. Outras rotas legadas seguem retornando 403.
- templates/login.html: link "Esqueci minha senha" direto para solicitação, mais "Já recebeu um código de recuperação? Informar código e definir nova senha" visível no formulário de login SaaS.
- static/login-v2.css: estilo acessível e compacto da nova opção.
- templates/saas_recover_request.html: botão direto para confirmação quando já possui OTP, sem solicitar outro.
- templates/saas_recover_confirm.html: fluxo explícito "Já recebi um código", exige e-mail, código de quatro dígitos, nova senha e confirmação; link de retorno ao login e nova solicitação.
- saas_email_otp_transport.py: e-mail de recuperação contém URL direta https://neuro-diagnosis.tech/saas/recuperar-senha/confirmar, sem código, credenciais ou tokens na URL.
- saas_account_admin_routes.py: feedback ao SuperAdmin explica claramente que o titular usa "Já recebi um código" no login; operador não recebe OTP, mantém autorização, senha atual, MFA e CSRF existentes.
- tests/test_saas_recovery_entry.py: 5 testes para UI de ambos caminhos, página que não reenvia OTP no GET, conteúdo do e-mail, raiz autenticada e isolamento de rotas legadas.

## Evidências locais
- Testes direcionados: 5/5 novos, 5/5 login recovery, exit 0.
- Suíte completa: 222 testes, OK (skipped=1), exit 0 => 221 executados/aprovados.
- git diff --check: exit 0. Pasta .visual_validation/ não será incluída no commit.
- Nenhuma mudança de schema, senha, identidade, permissões, MFA ou limite do OTP; validade de 3 minutos e 3 tentativas preservadas.

## Restrições
- O código OTP serve exclusivamente para redefinição de senha; não é código de login, não elimina TOTP.
- Usuário autenticado em outra conta, como o SuperAdmin, deve sair ou usar janela privada para realizar recuperação em nome da titular.
- Ainda não há validação de entrega SMTP com OTP novo nesta alteração, mas o usuário confirmou que recebeu o código na operação relatada.
- Bad Gateway coincidente com restart de container não é resolução arquitetural zero-downtime; considerar blue/green de forma separada, sem publicar mudança de arquitetura improvisada.
- Publicação posterior pelo pipeline canônico e evidência do runner + SHA remoto + saúde, sem reivindicar produção antes da confirmação.
