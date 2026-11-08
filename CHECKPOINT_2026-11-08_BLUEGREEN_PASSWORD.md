# CHECKPOINT - Neuro-Diagnosis: blue/green e sugestao de senha
Data: 2026-11-08. Edicao pelo STI01 via NEXO; main.

## Incidente e causa
Deploy anterior recria o unico Flask (8781) antes do healthcheck, provocando Bad Gateway temporario.
Traefik inspecionado na VPS com permissao root: host network; providers Docker e File com watch.
Nova porta loopback 8782 disponivel; redes e volumes existentes preservados.

## Correcao de senha
Frontend WebCrypto: 20 caracteres; >=4 letras, >=6 digitos, >=2 simbolos; valida antes de preencher.
Backend agora distingue regra de complexidade, confirmacao divergente e senha igual a anterior.
250 amostras JS validaram no mesmo validador Python. Testes completos aprovados.

## Novo deploy
Stage isolado docker-compose.saas.stage.yml na porta 8782, sem labels Traefik e com mesmas protecoes.
Helper root bluegreen grava por rename atomico um arquivo dedicado de Traefik, preservando TLS, limites, prioridade e rotas.
Deploy testa o candidato 8782 antes de trocar a rota, recria 8781 somente com o stage atendendo, retesta e volta.
Rollback antes da primeira troca nao derruba primary; depois da troca conserva stage enquanto restaura primary.
Nao modifica outros produtos, nem recria MySQL ou remove dados.

## Evidencias
STI: 227 testes, OK (skipped=1); contratos bluegreen 4/4, runner 8/8; 250 geracoes JS conformes.
PyYAML validou stage. git diff --check=0. ResourceWarning SQLite anterior sem falha.
Excluir .visual_validation/ do commit.

## Pendencias operacionais
Commit e push da alteracao no STI, sem alterar .release/request.json antes do bootstrap.
Com root autorizado: conferir SHA remoto, bash -n dos scripts e docker compose config; instalar executaveis root com backup.
Criar roteador Traefik dedicado apontando para primary 8781 e conferir marker HTTPS, sem interferir no Somos o Enigma.
Depois commit separado do pedido de release; confirmar runner, marker deployed-sha e provas HTTPS de troca stage->primary.
Nao declarar zero downtime antes da validacao pratica.
