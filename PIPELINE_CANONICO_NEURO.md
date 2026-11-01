# Neuro-Diagnosis: pipeline canonico (fase de construcao)
## Fonte da verdade
- Repositorio: Boanerges20297/sas_neuropsicopedagogia
- Branch publicavel: main (historico Django preservado; nao aplicar o Flask sem integracao aprovada).
- Alteracoes funcionais ficam em branches; a main so recebe codigo validado.
- Nao usar GitHub Actions.
- Nao usar acesso direto a VPS para publicacao normal.
## Sequencia projetada
GitHub main -> .release/request.json -> runner persistente ->
gates locais (contrato + Python + unittest) -> forced SSH gateway ->
checkout do SHA exato -> build Docker -> backup SQLite + migration ->
web -> readiness -> smoke por SHA -> Issue de status no GitHub.
Cada requestId e imutavel e de uso unico; falha requer novo request.
O arquivo .release/request.json NAO existe por padrao.
Nao criar esse arquivo enquanto o bootstrap do host nao for testado.
O watcher nao deve reagir a um push comum.
## Identidade de execucao
- Container: neuro-diagnosis-runner, UID 10001, sem docker.sock, read-only.
- GitHub: deploy key somente leitura do repositorio (segredo fora do Git).
- Host: usuario neuro-runner-host, chave SSH dedicada, forced command.
- Gateway: aceita APENAS deploy <SHA40> e smoke <SHA40>.
- Host: somente o script de deploy tem privilegios controlados de Docker.
- Segredos ficam fora do Git (host /etc/neuro-diagnosis/production.env,
  runner /home/runner/.ssh e arquivo de token no volume do runner).
- Registro externo: Issue dedicado de estado RUNNING/SUCCESS/FAILED.
- Qualquer ausencia de chave, token ou arquivo de autorizacao
  deve bloquear o runner.
## Ambiente Flask
- Branch nao publica. Nenhuma instalacao da infraestrutura ocorreu ainda.
- App executado por Gunicorn; /health/live e /health/ready sem dados clinicos.
- Dados ficam em volume persistente Docker; imagens nao incluem bancos,
  planilhas, PDFs, .env ou outros arquivos pessoais.
- SQLite inicializador adiciona schema; nao assume conversao de pacientes.
- O dominio neuro-diagnosis.tech atualmente responde Gunicorn com /login/.
  ANTES de qualquer primeiro deploy, verificar qual servico/container esta
  respondendo, sua base de dados, backup, proxy/TLS e autenticacao.
  Nao trocar dominio ou router por simples atualizacao de codigo.
## Bootstrap ??? nao executado
1. Auditoria do servico de producao atual, dominio, portas e dados.
2. Inventario de backups e teste de restauracao em homologacao.
3. Instalar checkout /opt/neuro-diagnosis, com origin fixo e branch main.
4. Criar volume de dados com UID 10001. Migrar banco existente apenas
   com aprovacao tecnica, comprovacao de integridade e backup verificado.
5. Criar arquivo de ambiente externo ao Git (0600), sem defaults de senha.
6. Criar usuario de deploy restrito e forced-command no host.
7. Criar chave de deploy separada, known_hosts pinado e volume do runner.
8. Registrar credencial minima para Issue de observabilidade, fora do Git.
9. Testar gateway negando qualquer comando fora de deploy/smoke SHA40.
10. Validar Compose, criar imagem em homologacao e testar falha simulada.
11. Habilitar runner e Issue de status; release so depois de pedido expresso.
12. Nunca acionar Traefik do Neuro-Diagnosis antes da revisao do dominio.
## Rollback
- Registrar SHA anterior e backup consistente do SQLite ANTES da migracao.
- Em falha de build/smoke: restaurar o container/codigo do SHA anterior.
- NUNCA restaurar o banco automaticamente sem verificar a compatibilidade
  e o impacto de alteracoes recebidas apos o backup.
- Registrar resultado da falha e bloquear tentativas repetidas pelo mesmo ID.
- A primeira ativacao precisa de plano especifico para dados existentes.
## Testes minimos
- Validador rejeita requestId malformado, versoes divergentes e campos extras.
- Sem request.json, nenhum gatilho de producao.
- Rotas de saude devolvem resposta sem dados pessoais.
- Todas as suites Flask existentes passam em ambiente temporario.
- Shell scripts passam em bash -n.
- Inspecao estrutural impede Docker socket e GitHub Actions.
- Teste real de forced-command, smoke e rollback apenas em homologacao.
## Situacao do trabalho
Esta branch e um conjunto de arquivos em preparacao e NAO significa que
existe runner instalado, gateway habilitado ou deploy publicado.
Revisar codigo e permissoes antes de mergear na main.
