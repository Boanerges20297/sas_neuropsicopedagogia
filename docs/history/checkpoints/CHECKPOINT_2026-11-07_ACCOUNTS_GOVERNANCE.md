# Checkpoint — Neuro-Diagnosis: contas, perfil e governança de testes

Data local: 2026-11-07 (America/Fortaleza)
Ambiente de execução: STI01 via NEXO Commander
Base Git: main (commit de produção anterior d69fe6e129bc2d8a67cb89a9358f2936b9e0f869)
Estado: alterações locais testadas; commit, push e release pendentes de aprovação/autorização.

## Escopo

1. Minha conta: painel compacto, dados pessoais separados de dados profissionais, senha e MFA em seções próprias. Dados pessoais são salvos sem exigir perfil profissional; formulário profissional separado e obrigatório apenas para profissional.
2. Papéis canônicos: patient (paciente/responsável), professional, admin, superadmin. Nenhum quinto papel "user". Administradores com clínica privada não precisam cadastrar credenciais profissionais, exceto se voluntariamente mantiverem um perfil técnico próprio.
3. Gestão de usuários: edição por conta, atualização de nome/e-mail/papel/estado/direitos, confirmação de senha de operador, MFA e sessão recente, CSRF, auditoria, bloqueio de auto-suspensão, proteção do último superadmin, não ativar BTA nem vínculos de paciente sem validação correspondente.
4. Lista de contas: busca nome/e-mail, filtro de perfil, paginação de 25 por vez, formulário de criação recolhível, atalhos para aprovação BTA e ativação de pacientes/responsáveis.
5. Superadmin: catálogo administrativo de definições e versões de instrumentos, acesso a parecer de publicação e pedido de ajustes mediante justificativa auditada, sem consultar avaliações, respostas, prontuários nem documentos de paciente.
6. Rotas clínicas centralizadas em licensed_tenant() negam superadmin (403). Rotas administrativas de ativação permanecem disponíveis conforme permissões, sem acesso a prontuários.
7. Dockerfile atualizado com novos módulos.

## Verificações

- `python -m unittest discover -s tests -q`: 177 testes, OK (1 skipped).
- Casos novos: administração/segurança, responsabilidade dos perfis, portal clínico superadmin, revisão de testes, busca e paginação, CSRF e MFA.
- `scripts/homologate_mysql_care.py`: MYSQL_HOMOLOGATION_OK, 33 tabelas em esquema descartável, esquema de teste descartado.
- `git diff --check`: sucesso. Sem mudança em segredos ou arquivos .env.

## Restrições confirmadas

- Superadmin pode administrar contas, permissões e definições dos testes, mas não prontuários nem dados clínicos individuais.
- Aprovação de publicação em catálogo não significa validação científica nem autorização para aplicar um instrumento regulamentado; exige revisão profissional apropriada.
- Publicação somente pelo pipeline canônico, após validação visual e autorização; este checkpoint não é release.
