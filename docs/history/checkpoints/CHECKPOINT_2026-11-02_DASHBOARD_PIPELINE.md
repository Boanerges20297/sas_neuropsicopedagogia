# Checkpoint — Neuro-Diagnosis SaaS: dashboard e pipeline canônico

**Data:** 2026-11-02 (America/Fortaleza)
**Estado:** release do dashboard concluída com sucesso no pipeline canônico; validação visual autenticada pendente.
**Fonte canônica:** `Boanerges20297/sas_neuropsicopedagogia`, branch `main`.
**Commit implantado pela release:** `af9ec2e7ded71714bd62893b5c764e7befd2d695`.
**Release (requestId):** `neuro-prod-dashboard-modern-retry-20261102-02`, versão `0.1.0`, build `1`.

## Entregas e evidências

- Reconciliação segura do STI01 com `origin/main` antes de editar: fast-forward até `9c56548`; alterações anteriores de Docker/testes já presentes no remoto foram preservadas em stash de segurança (não aplicar cegamente o stash).
- Dashboard SaaS modernizado: `templates/saas_dashboard.html`, bloco de estilo em `templates/saas_base.html`, CSS específico `static/saas-dashboard.css`. Indicadores usam dados reais: profissionais, pendentes, tenants ativos, pacientes cadastrados.
- Condições específicas de papéis respeitadas: superadmin/admin sem tenant clínico próprio aparece como administração ativa, não como cadastro pendente; atalhos para pacientes e instrumentos dependem de tenant/licença permitidos; isolamento de tenants e regras BTA não foram alterados.
- Teste de renderização de dashboard acrescentado em `tests/test_saas_dashboard_ui.py`.
- Commit do dashboard: `5e74d74`; request inicial: `f0dd9c0`.
- Primeiro deploy falhou (`neuro-prod-dashboard-modern-20261102-01`): os 46 testes do runner passaram (1 ignorado), o build Docker passou, mas o smoke público HTTPS recebeu HTTP 404 transitório logo depois da recriação do Flask. Pipeline executou rollback do código/container ao commit `53a5a83`; banco MySQL permaneceu saudável.
- Diagnóstico confirmado no log persistido do runner: `curl: (22) The requested URL returned error: 404`, seguido de `NEURO_ROLLBACK_CODE`. As rotas locais e HTTPS ficaram saudáveis após o rollback.
- Correção: smoke HTTPS público com até **12 tentativas**, espera de 5 segundos e prazo de conexão de 5 segundos por tentativa; mantém falha e rollback se o roteamento não estabilizar. Código `infra/host/deploy-neuro-diagnosis-saas.sh`, teste de contrato `tests/test_neuro_runner_contract.py`. Commit `d6b8000`.
- Script operacional instalado com backup na VPS: `/usr/local/sbin/deploy-neuro-diagnosis`; SHA-256 verificado `b0a1dcea09da5b77731418d336d334bc00b865e3e65c5d0960fa4bb24de88e9c`. Backup anterior `/usr/local/sbin/deploy-neuro-diagnosis.backup-20261102`. Não alterar manualmente container/DB fora do pipeline canônico.
- Novo request na `main` (`af9ec2e`). O runner confirmou **NEURO_RUNNER_SUCCESS / NEURO_PIPELINE_OK** no Issue #2: https://github.com/Boanerges20297/sas_neuropsicopedagogia/issues/2#issuecomment-6591570030.
- Validação final efetuada: `/static/saas-dashboard.css` HTTP 200 (10.088 bytes); `/health/ready`, `/saas/saude` e `/saas/entrar` HTTP 200. `neuro-diagnosis-flask` e `neuro-diagnosis-db` healthy; runner ativo, 0 reinicializações na inspeção.
- Suíte de testes no STI01 **47 executados, OK (1 ignorado)**, antes da release final. `git diff --check` OK. Nenhuma mudança nas regras de autenticação, licenciamento BTA ou isolamento clínico.

## Arquitetura e operação a preservar

- **Desenvolver e executar testes no STI01 via NEXO; conciliar Git antes de editar; `main` remota como fonte de verdade.**
- Stack: Flask/Gunicorn, MySQL 8, BTA Licenças; produção sob Traefik. Acesso de administrador/superadmin é permanente e independente de licença BTA, **sem quebrar autorização nem isolamento entre tenants**.
- Publicação somente com commit específico que altera `.release/request.json` com novo `requestId`; watcher 60 s, gates, backup MySQL, migração aditiva, atualização web, smoke e registro no Issue #2. Commit apenas de documentação **não aciona release**.
- Não usar GitHub Actions, deploy manual para contornar gates, recriar MySQL, `docker compose down -v` ou mudar serviços de outros projetos.
- Monitorar pelo Issue #2 e pela evidência local do runner; o Issue isoladamente não prova a saúde em tempo real.
- Segredos e credenciais não devem constar no checkpoint, commits, Issues nem logs.

## Pendências / próximo ponto de retomada

1. **Validação visual autenticada** do dashboard (desktop e celular), incluindo responsividade, contrastes, navegação e diferenças entre superadmin, admin e profissional.
2. **Validar fluxos reais de login e gestão de perfil** (troca de senha/e-mail) em produção com contas autorizadas; HTTP 200 no login não prova autenticação funcional.
3. Conferir por via operacional, quando necessário, o SHA do arquivo `/var/lib/neuro-pipeline/deployed-sha` com o SHA da release e a integridade/retorno de backups; `NEURO_PIPELINE_OK` já foi observado.
4. Em caso de próximos ajustes, iniciar pela conciliação `STI main` vs. `origin/main` e preservar alterações humanas. Novo deploy requer outro `requestId`; nunca reutilizar os dois anteriores.

**Nota:** este checkpoint registra evidências obtidas e limites de validação. Não representa aprovação visual humana nem comprovação de login com dados reais.
