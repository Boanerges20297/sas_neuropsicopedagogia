# Neuro-Diagnosis

Plataforma SaaS de apoio ao atendimento profissional, com autenticação, gestão de pacientes, agenda e instrumentos de avaliação. A aplicação utiliza Flask; o ambiente SaaS de produção utiliza MySQL.

## Navegação

- **Código de entrada:** `app.py`, `schema.py` e integrações de entrada na raiz.
- **Módulos SaaS:** `saas/core/`, `saas/auth/`, `saas/accounts/`, `saas/clinical/`, `saas/patients/` e `saas/neurocore/`.
- **Motor experimental de indicadores:** `neurocore/` (separado do fluxo SaaS).
- **Interface:** `templates/` e `static/`.
- **Scripts operacionais:** `scripts/`; ferramentas legadas em `scripts/legacy/`.
- **Testes automatizados:** `tests/`.
- **Operação e publicação:** [PIPELINE_CANONICO_NEURO.md](PIPELINE_CANONICO_NEURO.md). É a referência obrigatória para releases, rollback e runner; não disparar deploy manual.
- **Documentação de arquitetura, decisões e histórico:** [docs/README.md](docs/README.md).

## Atenção à documentação histórica

Documentos antigos sobre o questionário de altas habilidades e checkpoints datados foram preservados em `docs/history/`. Eles registram estados anteriores e **não** substituem as regras atuais do código, os testes e o pipeline canônico.

Antes de alterar rotas, autenticação, permissões ou isolamento de pacientes, consultar os testes existentes e validar regressões. Não usar documentos históricos como comprovação de implantação atual.
