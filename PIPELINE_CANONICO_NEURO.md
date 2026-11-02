# Neuro-Diagnosis — pipeline canônico de produção

**Estado verificado em 02/11/2026:** operacional. O runner executou uma release real de ponta a ponta e registrou `NEURO_PIPELINE_OK`. Esta é a documentação canônica para operação, auditoria e recuperação. A publicação normal não usa GitHub Actions nem SSH administrativo interativo.

## Fonte da verdade e referências

- Repositório: [Boanerges20297/sas_neuropsicopedagogia](https://github.com/Boanerges20297/sas_neuropsicopedagogia).
- Branch canônica: `main`. O SHA integral do commit é a identidade imutável de cada release.
- **Issue de observabilidade reservado:** [#2 — RUNNER STATUS](https://github.com/Boanerges20297/sas_neuropsicopedagogia/issues/2), mantido aberto como histórico de releases e incidentes. Não criar Issues duplicados para esse fim.
- Manifesto de versão: `release.json`; gatilho explícito: `.release/request.json`; contrato: `scripts/release_request.py`.
- Runner: `docker-compose.runner.yml` e `infra/runner/`. Aplicação Flask: `docker-compose.saas.yml`. Não usar o antigo `docker-compose.production.yml` para produção SaaS.
- Execução: `scripts/runner-watch.sh` → `scripts/runner-release.sh` → `scripts/runner-gates.sh` → SSH `infra/host/neuro-host-gateway` → `infra/host/deploy-neuro-diagnosis-saas.sh`.
- Resultado e observação: `scripts/runner-state.py` e `scripts/runner-observe.sh`.

## Arquitetura e isolamento

`GitHub main` → commit que **altera** `.release/request.json` → polling do `neuro-diagnosis-runner` (60 s) → validação do request e do SHA → gates Python/`unittest` → gateway SSH de comandos forçados → backup **MySQL** → migração aditiva → build e atualização **somente do web** → health checks e smoke HTTPS → estado persistente + comentário no Issue #2 *se o token de escrita estiver configurado*.

- O runner é processo separado, usuário UID/GID `10001`, filesystem somente leitura, limites de CPU/memória, sem privilégios e **sem `/var/run/docker.sock`**. Apenas `/work` e `/home/runner` são persistentes e graváveis.
- A conexão com o host usa `neuro-runner-host`, chave SSH exclusiva do Neuro-Diagnosis e `authorized_keys` com `restrict`/`command=...`. O gateway aceita somente `deploy <SHA40>` e `smoke <SHA40>`. Comandos arbitrários são negados (código 126).
- O deploy do host valida branch limpa, remoto esperado, SHA correspondente à `origin/main` e arquivo local de autorização `/etc/neuro-diagnosis/host-approved`.
- O Flask usa Gunicorn e MySQL 8, banco `neuro_diagnosis`. Os serviços `neuro-diagnosis-flask` e `neuro-diagnosis-db` não pertencem ao Compose do runner. Não modificar/recriar o banco, seu volume, outros projetos ou o Traefik em uma release ordinária.
- Segredos e credenciais permanecem fora do Git. Nunca gravar no Issue senhas, tokens, chaves privadas, dados clínicos, CPF ou conteúdo de backups.

## Operação: solicitar uma release

1. Validar o código na `main` e os testes; conferir o estado de `neuro-diagnosis-runner`, `neuro-diagnosis-flask` e `neuro-diagnosis-db`. O primeiro commit de código por si só **não** dispara deploy.
2. Criar um novo commit na `main` que **altere `.release/request.json`** com `schemaVersion=1`, `action=release`, `requestId` **único**, `versionName` e `versionCode` exatamente iguais aos do `release.json`. Ver `.release/README.md`.
3. O watcher detecta somente quando o HEAD atual modificou o arquivo de request em relação ao primeiro pai; por isso o pedido deve ser o último commit ao iniciar uma release.
4. O runner valida o request, sincroniza o SHA, registra `running`, instala/valida dependências e executa os testes da suíte. Em seguida chama `deploy SHA` e `smoke SHA` pelo gateway forçado.
5. O script do host faz backup do MySQL antes de migrar e atualizar o serviço web. Depois valida `/health/ready`, `/saas/saude` e `/saas/entrar` localmente, além do HTTPS externo.
6. O resultado fica em `/var/lib/neuro-pipeline/home/.local/state/neuro-diagnosis/processed/<requestId>.json`, com logs por requestId/SHA em `.../logs/`. O SHA aplicado fica em `/var/lib/neuro-pipeline/deployed-sha`. Registrar o resultado no Issue #2.

**Exemplo de conteúdo do request** (alterar `requestId` e usar valores reais de `release.json`):

```json
{
  "schemaVersion": 1,
  "requestId": "neuro-prod-YYYYMMDD-001",
  "action": "release",
  "versionName": "0.1.0",
  "versionCode": 1
}
```

Um novo push sem mudança nesse arquivo não dispara outra release. Um mesmo `requestId` não deve ser reutilizado, mesmo após falha. Se a `main` avançar durante o processamento, a validação estrita do SHA pode impedir o deploy: faça outro request após estabilizar o histórico.

## Observabilidade — Issue #2

O [Issue #2](https://github.com/Boanerges20297/sas_neuropsicopedagogia/issues/2) é o **único registro externo canônico** de histórico e status do pipeline. Mantenha-o aberto e acrescente comentários `RUNNING`, `SUCCESS` ou `FAILED` com `requestId`, SHA e resumo sanitizado. Não usar o Issue como disparador de deploy.

- `NEURO_STATUS_ISSUE`: número `2`, configurado como valor padrão no `docker-compose.runner.yml`. Para refletir alterações dessa variável em um container já existente, é necessário aplicar o Compose do runner na VPS de forma autorizada.
- Para comentários **automáticos** o runner exige token GitHub de escopo mínimo de escrita em Issues, restrito a este repositório, armazenado fora do Git em `/var/lib/neuro-pipeline/home/.config/neuro-diagnosis/issue-token` no host (mapeado para `/home/runner/.config/neuro-diagnosis/issue-token` no container). Proprietário UID 10001, modo 0600.
- **Situação em 02/11/2026:** o Issue existe e a observabilidade local foi validada, mas o token de escrita no Issue **não estava provisionado**; os eventos automáticos externos permanecem **pendentes**. `scripts/runner-observe.sh` faz fallback local se Issue/token faltarem, sem impedir o deploy.
- Não incluir o token no Compose, no repositório, em tickets ou logs. Após provisionar a credencial, testar a emissão de um comentário não sensível, checar o resultado no Issue e registrar essa validação.
- O status local prevalece como evidência da máquina; um comentário isolado no Issue **não prova** saúde atual nem execução de deploy.

## Monitoramento e diagnóstico na VPS

Executar os comandos abaixo **somente por acesso operacional autorizado** (sem segredos nos parâmetros):

```bash
cd /opt/neuro-diagnosis
docker compose -f docker-compose.runner.yml ps
docker logs --tail 80 neuro-diagnosis-runner
docker compose -f docker-compose.saas.yml ps
git rev-parse HEAD
cat /var/lib/neuro-pipeline/deployed-sha
ls -lt /var/lib/neuro-pipeline/home/.local/state/neuro-diagnosis/processed/
curl --fail https://neuro-diagnosis.tech/health/ready
curl --fail https://neuro-diagnosis.tech/saas/saude
```

Verificar `status=success` nos JSON do runner, `NEURO_DEPLOY_OK`, `NEURO_SMOKE_OK` e `NEURO_PIPELINE_OK` nos logs; o SHA do GitHub, o SHA implantado e o SHA do request devem coincidir. Conferir restart count, limites, ausência de Docker socket e saúde do MySQL.

## Backups, falhas e recuperação

- Antes de modificar o MySQL, o script do host executa `mysqldump --single-transaction --no-tablespaces` do banco `neuro_diagnosis`. Os arquivos ficam em `/var/lib/neuro-diagnosis/backups/`, com acesso restrito. Verificar o arquivo, tamanho e instruções de criação de tabelas. Backup validado **não substitui** teste de restauração em ambiente isolado.
- A migração SaaS atual usa `scripts/mysql_saas_profile_migration.sql` e é aditiva (`professional_details`). Revisar migrações futuras quanto a compatibilidade, transações e idempotência antes da release.
- Em falha após avançar o checkout, o script tenta restaurar o **código/container** anterior. **Não restaura automaticamente os dados MySQL.** Mudanças incompatíveis de schema exigem plano específico e avaliação humana.
- Se o runner falhar, olhar logs e estados `processed/` e `rejected/` antes de qualquer reexecução. Não executar diretamente o script com root ou reaproveitar o `requestId` para contornar gates; corrigir a causa, validar e emitir um novo pedido.
- Nunca realizar `docker compose down -v`, remover volumes, trocar o banco para SQLite, executar GitHub Actions ou reutilizar chaves de outros produtos.

## Evidência da primeira validação real

Em **02/11/2026**, foi realizado um release controlado para validar o caminho completo:

- `requestId`: `neuro-prod-pipeline-validation-20261102-01`
- Commit/SHA: `94058500a7bdeded7e97a97c30f3fc4998a0eb7a`
- Gates: **41 testes executados; 40 aprovados e 1 ignorado**.
- Runner local: registro `status=success` / `NEURO_PIPELINE_OK`.
- Gateway/host: `NEURO_DEPLOY_OK` e `NEURO_SMOKE_OK`, backup MySQL validado.
- Após deploy: Flask e MySQL `healthy`; HTTPS com HTTP 200 e TLS válido em `/health/live`, `/health/ready`, `/saas/saude`, `/saas/entrar` e `/saas/cadastro`.
- Hash da `main` no host coincidente com o remoto. Runner ativo sem reinicializações, UID 10001, filesystem somente leitura, sem Docker socket.

**Pendência conhecida:** automatizar comentários no Issue #2 após fornecimento seguro de credencial mínima e atualização controlada do ambiente do runner. O pipeline de deploy **já funciona sem essa integração**.
