# Neuro-Diagnosis — Checkpoint de fluxo de atendimento clínico
**Data local:** 2026-11-09 | **Ambiente de implementação:** STI01 via NEXO
**Repositório:** Boanerges20297/sas_neuropsicopedagogia, main
**Âmbito:** atendimento profissional e dados clínicos do tenant próprio, sem publicação automática.

## Implementações
- Dashboard privado em `/saas/atendimentos`: filtros dia/mês/ano, atendimentos iniciados, pacientes únicos, instrumentos indicados e questionários respondidos; distribuição temporal e diagnósticos confirmados exclusivamente por ato profissional. Entrada também no painel e na navegação.
- `Novo atendimento` seleciona paciente próprio e cria sessão idempotente sem agendamento obrigatório; sessões anteriormente originadas na agenda são preservadas. Formulário abre dados iniciais, relato/representação, histórico e evolução clínica.
- Editor web rico de observações com formatação allowlist, revisão otimista por número, histórico de revisões sem apagar versões anteriores, criptografia em repouso via Fernet/HKDF e auditoria sem texto clínico.
- Registro profissional de hipóteses, confirmações e descartes. Diagnóstico não é derivado de pontuação, IA ou reconhecimento automático; confirmação precisa de registro manual.
- Seleção por paciente de instrumentos/versões **aprovados** do catálogo, incluindo qualquer instrumento autoral com definição de anamnese (`kind: anamnesis`).
- Motor único de perguntas `single`, `multiple`, `yes_no`, `text`, `number` com opções estritas, perguntas obrigatórias e revisões. Modo profissional preenche o mesmo questionário, com observações da sessão ao lado. Respostas são criptografadas numa tabela clínica própria; não reutiliza `assessment_responses.answer_json` legado.
- Modo portal registra indicação como `awaiting_portal_access`. **Não envia convite, não cria URL pública e não permite respostas do paciente nesta fatia.** Exige implementar vínculo/identidade do adulto ou representante, consentimento específico, autorização clínica, expiração/revogação, rota de questionário e E2E antes de liberar.
- Migração SQL `mysql_care_encounters_assessments_migration.sql`: 5 novas tabelas clínicas, chaves compostas e alteração controlada de campo de agendamento para início direto. Integração na cópia versionada do pipeline *após backup*.
- `Dockerfile` inclui os três módulos Python do fluxo.

## Verificações reais no STI
- 11 testes unitários de contrato do fluxo: OK.
- 5 testes HTTP sintéticos para rotas, CSRF, isolamento de paciente e questionário: OK.
- Suite completa anterior às últimas alterações de UX: 246 testes, OK, com 1 skipped. Reexecutar no fechamento.
- Homologação real MySQL 8.4 WSL com esquema descartável, migrações repetidas, 40 tabelas: OK. Verifica início direto, documento privado, FK de escopo e respostas privadas, com saída `CLINICAL_MYSQL_HOMOLOGATION_OK`. Banco de homologação apagado ao término.
- Nenhuma escrita em prontuários reais, nenhum push de release, nenhuma modificação de VPN.

## Pendências e controle de publicação
1. **Portal interativo:** rota do paciente/responsável, acesso e consentimento por questionário, verificação de vínculo, token/convite expiráveis e auditoria; não anunciar funcionalidade pronta.
2. **Anamnese:** disponibilizar conteúdo autoral clínico revisado no catálogo e submeter à governança; nenhum instrumento protegido ou questionário psicométrico pode ser inserido sem direitos/validação.
3. **Habilitação:** restringir instrumentos por qualificações/escopo profissional quando a categoria exigir.
4. **UI:** revisão manual desktop/mobile e teste E2E com contas sintéticas, inclusive recuperação de rascunho, navegação entre observação e formulário, duplo clique e duas abas.
5. **LGPD e clínica:** política de retenção/exportação e rotação de chave, consentimento, histórico de versões, integridade/assinatura profissional, avaliação de bases legais e proteção de menores antes de dados reais.
6. **Deploy:** script instalado na VPS `/usr/local/sbin/deploy-neuro-diagnosis` deve ser reconciliado com a versão Git e auditado antes de criar `.release/request.json`. Não publicar sem essa etapa, backup e smoke test.

## Acesso
Superadmin/administradora acessam as funções administrativas e **somente seu próprio tenant clínico ativado**; prontuários alheios continuam invisíveis. Profissionais comuns dependem de licença BTA. Rotas exigem sessão, CSRF e escopo do profissional/paciente.
