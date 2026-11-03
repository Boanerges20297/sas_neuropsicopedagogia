# Checkpoint — integração experimental NeuroCore TEA/TDAH ao SaaS
Data: 02/11/2026 (America/Fortaleza)
Fonte canônica: Boanerges20297/sas_neuropsicopedagogia, main.
Ambiente: STI01 via NEXO, conciliação com origin/main confirmada antes de editar.

## Entregas no código (NÃO PUBLICADAS)
- /saas/pacientes: navegação para espaço individual de cada paciente próprio.
- /saas/pacientes/<id>: visão dos roteiros documentais de TEA e TDAH.
- /saas/pacientes/<id>/neurocore/<tea|tdah>: GET/POST para revisão de 8 áreas por tema, com CSRF e salvamento estruturado no MySQL.
- Nenhuma pontuação diagnóstica: registra somente estado da documentação, e motivos curtos para não aplicável.
- Tabela neurocore_evidence_reviews: SQL aditivo, idempotente, chave única tenant/paciente/profissional/tema, FKs compostas de tenant e membro.
- Auditoria de gravação e verificação dupla de titularidade antes de ler ou escrever; negado acesso a outro paciente/tenant (404) e licença não permitida (403).
- Administradores sem espaço clínico próprio podem criá-lo mediante POST + CSRF explícitos; isso NÃO libera dados clínicos de outros tenants.
- Consultas administrativas ao espaço clínico são estritamente por owner_user_id, sem usar simples associação de membro como permissão clínica.
- Menu administrativo não exibe atalhos clínicos antes da ativação do espaço pessoal.
- Dockerfile incorpora os novos arquivos e o pacote neurocore/, sem instalar scikit-learn na imagem.
- Endpoint /saas/saude verifica a tabela neurocore_evidence_reviews; falha fechada se migração ausente.
- A migração foi anexada no script fonte infra/host/deploy-neuro-diagnosis-saas.sh APÓS o backup MySQL.

## Validação no STI
72 testes completos; 71 passaram, 1 ignorado; 0 falhas.
Testes novos: rotas autenticadas, CSRF, limite tenant, escrita documental, versão, schema/migração, ativação administrativa.
Correção adicional: Dockerfile antes não copiava novos módulos e o teste de empacotamento detectou a falha.
git diff --check: sem problemas relevantes.

## PENDÊNCIAS OBRIGATÓRIAS antes de produção
1. A versão operacional do deploy é uma CÓPIA instalada em /usr/local/sbin/deploy-neuro-diagnosis na VPS. Alterar o script versionado no repositório NÃO atualiza automaticamente a cópia instalada. Antes de emitir release, instalar/validar a nova versão sob autorização apropriada, preservando backup, hash e contrato de execução do gateway.
2. Aplicar migração via pipeline canônico e verificar tabela no MySQL em ambiente controlado; backup e teste de restauração devem ser considerados. Nunca executar alterações improvisadas no banco de produção.
3. Testar fluxo completo com dois profissionais sintéticos em MySQL de homologação, inclusive isolamento e reavaliação após POST. Os testes unitários com mocks não substituem esse teste.
4. A especialista administradora precisa revisar textos, campos, materiais e limites de uso antes de qualquer utilização clínica.
5. Testar visualmente (desktop/celular), autenticação, perfis e licenciamento BTA. Verificar controles de retenção, consentimento e auditoria de dados sensíveis.
6. Somente após gates completos emitir NOVO requestId em .release/request.json e monitorar Issue #2; não utilizar deploy manual nem GitHub Actions.

## Precauções
- O sistema continua sendo auxílio documental experimental, NÃO ferramenta diagnóstica/triagem com desempenho clínico validado.
- Sem DSM integral, instrumentos protegidos, prontuários reais ou treinamento de IA com pacientes.
- Nenhuma mudança em regras de aprovação de profissionais, trial de 14 dias ou isenção de licença BTA para administradores.
- NÃO houve publicação ou uso real de pacientes nesta etapa.
