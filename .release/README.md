# Solicitações de release — Neuro-Diagnosis

O pipeline **está operacional** desde 02/11/2026; guia e evidências:
[PIPELINE_CANONICO_NEURO.md](../PIPELINE_CANONICO_NEURO.md).

A branch canônica é `main`. Um push comum **não faz deploy**. O watcher lê o HEAD da `main` e somente dispara uma execução quando esse commit **altera** `.release/request.json`. O `requestId` deve ser **novo** a cada tentativa (inclusive após falha), e `versionName`/`versionCode` precisam coincidir com `release.json`.

Exemplo (substitua `requestId` por identificador único e valide os campos de versão):

```json
{
  "schemaVersion": 1,
  "action": "release",
  "requestId": "neuro-prod-YYYYMMDD-001",
  "versionName": "0.1.0",
  "versionCode": 1
}
```

Fluxo: `main` → validação do request → gates de testes → gateway SSH restrito → backup MySQL → migração aditiva → atualização Flask → smoke HTTPS → estado persistente.

Issue exclusivo de acompanhamento e histórico: [#2 — RUNNER STATUS](https://github.com/Boanerges20297/sas_neuropsicopedagogia/issues/2). O comentário **automático** no Issue exige credencial mínima de escrita em Issues no volume seguro do runner e configuração ativa de `NEURO_STATUS_ISSUE=2`; caso contrário, o status é registrado apenas localmente.

**Não** usar GitHub Actions, executar deploy manual para contornar gates, incluir segredos no repositório ou documentos clínicos no Issue. Antes de nova release, ler o runbook, validar os containers e conferir backup e plano de rollback.
