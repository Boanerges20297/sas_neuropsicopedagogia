# CHECKPOINT - Neuro-Diagnosis - 2026-11-08 (pos-release)

## Resultado can├┤nico
- Repositorio: Boanerges20297/sas_neuropsicopedagogia, branch main.
- Release aprovada pelo pipeline: 7765fc376519cf89fbd0d99e0236f2504a7b04e9.
- Request: neuro-prod-bluegreen-password-20261108-01, versao 0.1.0 (code 1).
- Runner confirmou NEURO_RUNNER_SUCCESS e NEURO_PIPELINE_OK na issue #2 do repositorio.
- Checagem na VPS: git HEAD, origin/main e /var/lib/neuro-pipeline/deployed-sha iguais ao SHA da release; repositorio sem alteracoes.
- Publicacao passou, sem necessidade de nova release para este checkpoint documental.

## Arquitetura e execucao verificada
- Traefik: provider file com watch, arquivo exclusivo neuro-diagnosis-bluegreen.yml; nao alterar arquivo do Somos o Enigma.
- Bootstrap realizado na porta 8781, HTTPS 200 e cabecalho X-Neuro-Deploy-Slot=primary.
- Blue/green: canario neuro-diagnosis-flask-stage abriu na porta local 8782 e ficou healthy; Flask primary foi recriado com nova versao enquanto canario atendia.
- Trafego retornou para primary na porta 8781, e container stage foi removido.
- Flask e MySQL healthy; Flask com zero restarts apos release.
- 49 probes HTTPS apos deploy responderam HTTP 200; este conjunto nao mede indisponibilidade durante TODA a janela de troca.
- Backup root do script anterior preservado em /var/lib/neuro-diagnosis/backups/.

## Correcoes e evidencias
- Sugerir senha: WebCrypto, 20 caracteres, pelo menos 4 letras + 6 digitos + 2 simbolos; validacao da politica antes de preencher e confirmar.
- Backend: feedback distinto para senha invalida, confirmacao divergente e repeticao da senha anterior.
- 250 senhas geradas pelo JS real foram conferidas contra o validador Python.
- Suite STI01: 228 testes, OK (227 executados e 1 ignorado); git diff --check=0.
- Erro na primeira ativacao: heredoc Bash expandiu crases das regras Host/Path do Traefik e executou comandos involuntarios.
- Rollback automatico removeu arquivo defeituoso e manteve Flask healthy; correcao versionada no commit 23fa223.
- Teste de regressao novo executa de verdade a renderizacao Bash para 8781/8782 com stderr vazio; bash -n isoladamente nao detectava o erro.
- Container obsoleto nexo-maintenance-broker removido apos constatado parado/exited(127), sem rede, sem vinculo com os servicos ativos. Imagem e volumes preservados.

## Seguranca, limites e pendencias reais
- O superadmin nao deve acessar prontuarios. Nao alterar politica multi-tenant, licenciamento BTA ou controle de acesso sem testes apropriados.
- Testar manualmente no navegador Sugerir senha nas telas de alteracao e recuperacao; testes automatizados passaram, mas UX manual ainda nao foi comprovada.
- Registrar e monitorar disponibilidade durante futuras releases para medir taxa de 502; nao declarar zero downtime absoluto apenas por probes pos-deploy.
- Memoria operacional: experiences.csv e strategies.csv gravados e verificados na main de Boanerges20297/chatgpt-memory, incluindo falha heredoc e estrategia de teste real.
- Copias dos CSVs no Google Drive e conciliacao STI de memoria ainda nao verificadas. Nao afirmar sincronizacao do Drive.
- Pasta .visual_validation/ permaneceu fora do Git.

## Evidencias verificaveis
- Runner: https://github.com/Boanerges20297/sas_neuropsicopedagogia/issues/2#issuecomment-6728261064
- Repositorio can├┤nico: https://github.com/Boanerges20297/sas_neuropsicopedagogia
- Registro anterior de arquitetura e implementacao: commit 3adb52e, fix 23fa223, release 7765fc3.
- Este arquivo e documental; .release/request.json nao deve ser modificado pelo checkpoint.
