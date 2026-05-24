# Estado do Projeto - SaS_NeuroPsicopedagogia

Este arquivo registra evolucao, decisoes de design, status de execucao e memoria ativa do projeto.

## Status Geral
- Milestone Atual: Milestone 1 (Seguranca, LGPD e Auditoria)
- Fase Atual: Fase 1.1 em execucao (CSRF e hardening de sessao)
- Ultima Atualizacao: 2026-05-24

## Decisoes de Arquitetura (ADRs)
1. IA de Borda local:
   - O analisador clinico permanece local em Python com visualizacao no frontend, garantindo privacidade e operacao offline.
2. Criptografia de dados sensiveis:
   - Campos pessoais identificaveis de menores serao protegidos com Fernet, com chave em variavel de ambiente.
3. Migracao para ORM:
   - A transicao para SQLAlchemy permanece prevista para o Milestone 2.

## Progresso de Execucao
- [x] Estrutura `.planning` criada
- [x] `PROJECT.md` criado
- [x] `config.json` criado
- [x] `REQUIREMENTS.md` criado
- [x] `ROADMAP.md` criado
- [x] `IMPLEMENTATION_PLAN.md` criado
- [ ] Fase 1.1 concluida
- [ ] Fase 1.2 concluida
- [ ] Fase 1.3 concluida
