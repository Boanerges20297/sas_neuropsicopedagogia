# Checkpoint — correção paciente ≠ responsável, Neuro-Diagnosis
Data: 2026-11-07 (America/Fortaleza)
Ambiente: STI01 via NEXO Commander. Branch main, reconciliada com origin/main antes das alterações, baseline b6c173f.

## Decisão aprovada
Titular de conta e paciente não são necessariamente a mesma pessoa.
Adulto: ele próprio é titular da futura conta; menor: paciente é criança/adolescente, e responsável legal mantém conta única. Não criar contas duplicadas para um menor.
Uma conta pode representar mais de um filho, cada qual com seu registro clínico e autorização independente.

## Implementado no STI (sem publicar)
- Formulário profissional /saas/pacientes agora recebe modalidade adulto/menor, nome e DOB do paciente, idade calculada e relato inicial de sinais/dificuldades.
- Modalidade menor solicita nome do responsável e e-mail opcional no MESMO formulário; não cria usuário/login do menor nem usuário do responsável.
- Registro do responsável é vínculo interno ainda NÃO verificado; e-mail coincidente nunca gera autorização.
- Nova tabela care_patient_intakes com relação 1:1 ao paciente, FK do contato do próprio paciente/profissional/tenant, modo self/guardian e notas criptografadas BLOB. O DOB canônico permanece somente em clients.
- saas_patient_intake.py implementa validação de maioridade, limites, criptografia Fernet com derivação HKDF separada e cadastro atômico.
- A idade usa data de nascimento e calendário de Fortaleza, não atributo fixo.
- Visão autenticada /saas/pacientes/<id>/dados-iniciais expõe notas somente ao profissional titular, sem cache; pacientes legados continuam disponíveis.
- Dockerfile copia módulos; script fonte de deploy aplica migração aditiva e endpoint de saúde verifica tabela.
- Portal de autosserviço NÃO aberto. Adulto próprio e menor responsável ainda precisam login único, comprovação de vínculo, grants e auditoria E2E; a política guardian pré-existente não libera adulto automaticamente.

## Evidências de validação
- MySQL WSL 8.4.8 real com base única descartável: 21 tabelas, 2 profissionais e pacientes sintéticos de adulto e menor.
- MySQL bloqueou 4 violações adicionais: menor sem responsável, adulto com vínculo indevido, responsável de outro paciente e profissional fora do tenant.
- Suite completa: 108 testes executados; 107 aprovados, 1 ignorado, 0 erros. Testes unitários de criptografia, falta de autorização, CSRF e UI dos dois modos.
- Homologação terminou com DISPOSABLE_HOMOLOGATION_SCHEMA_DROPPED; nenhum dado de produção usado.

## Pendências antes de produzir
1. Confirmar interface responsiva com a profissional administradora; notas iniciais são relatos, não diagnósticos.
2. Implementar portal autoatendimento com login único, vinculação verificada para adulto e para responsável, permissões por criança e escopo, consentimentos LGPD, revisão de maioridade.
3. Testar fluxo completo com sessões reais e concorrência de criação de paciente em ambiente de homologação; testes SQL e mocks não substituem E2E completo.
4. Não girar SECRET_KEY sem planejamento da recriptografia do material clínico.
5. Atualizar/validar sob autorização a cópia do script de deploy instalada na VPS antes de emitir nova release, manter backup MySQL e pipeline canônico.
6. Nenhum request de release acionado; sem publicação em produção.
