# Documentação do Neuro-Diagnosis

Este índice separa **referências operacionais**, **decisões**, **propostas arquiteturais** e **histórico**. Arquivos históricos não são declarações do estado atual da aplicação.

## Operação vigente

- [Pipeline canônico de produção](../PIPELINE_CANONICO_NEURO.md) — fonte para releases, validação e rollback.
- [README principal](../README.md) — visão e localização dos componentes.

## Decisões de domínio

- [Instrumentos clínicos e compartilhamento](decisions/INSTRUMENTOS_CLINICOS_2026-11-15.md) — implementação técnica publicada na release `0720baf`; validação clínica e autorização de instrumentos oficiais continuam pendentes.
- [Relação entre conta, paciente e responsável](decisions/DECISAO_PACIENTE_CONTA_RESPONSAVEL_2026-11-07.md) — decisão aprovada, com status de implementação datado.

## Propostas e experimentos de arquitetura

- [SaaS multi-tenant](architecture/proposals/ARQUITETURA_SAAS.md) — proposta histórica; revisar contra o código atual.
- [Atendimento profissional e cliente](architecture/proposals/ARQUITETURA_ATENDIMENTO_PROFISSIONAL_CLIENTE_2026-11-07.md) — especificação de 07/11/2026.
- [NeuroCore experimental TEA/TDAH](architecture/experiments/NEUROCORE_TEA_TDAH_V0.md) — não interpretar como instrumento clínico validado.

## Histórico preservado

- `history/checkpoints/` — checkpoints datados para auditoria e recuperação.
- `history/legacy/` — documentos de fases anteriores, incluindo os READMEs originais e antigos guias.
- `history/legacy/assets/` — PDF, texto extraído e planilha do antigo questionário, preservados apenas como histórico; ferramentas correspondentes em `scripts/legacy/`.

## Disciplina documental

Atualizar as referências canônicas quando uma decisão mudar; registrar decisões novas em `decisions/`; evitar criar novos `CHECKPOINT_*.md` na raiz. O histórico de código e releases continua sob controle de versão e pipeline.
