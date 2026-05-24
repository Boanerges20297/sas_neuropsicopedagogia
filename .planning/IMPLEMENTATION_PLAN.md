# Plano de Implementação - Milestone 1 (Segurança, LGPD & Auditoria)

Data: 2026-05-24  
Escopo: Executar as fases 1.1, 1.2 e 1.3 do roadmap com validação incremental e rollback seguro.

## Estratégia de Execução
- Ordem: Fase 1.1 -> Fase 1.2 -> Fase 1.3.
- Entregas pequenas por commit (uma subfase por vez).
- Validação manual e técnica ao final de cada subfase.
- Sem quebra de compatibilidade com dados já existentes no SQLite.

## Fase 1.1 - Proteção CSRF e Hardening de Sessão
Objetivo: mitigar CSRF/session hijacking em todas as rotas POST e autenticação.

### Tarefas
1. Adicionar dependência `Flask-WTF`.
2. Configurar `CSRFProtect` no bootstrap da aplicação (`app.py`).
3. Configurar cookies de sessão:
   - `SESSION_COOKIE_HTTPONLY=True`
   - `SESSION_COOKIE_SAMESITE='Lax'`
   - `SESSION_COOKIE_SECURE` por variável de ambiente (produção: `True`).
4. Revisar formulários HTML e incluir token CSRF em todos os POST.
5. Revisar POST via JavaScript (AJAX/fetch) para enviar cabeçalho de CSRF.
6. Criar handler amigável para erro CSRF (HTTP 400) com mensagem de reenvio.

### Critérios de aceite
- Todo POST sem token válido retorna bloqueio CSRF.
- Login, cadastro, envio de questionário e ações administrativas continuam funcionais.
- Cookies de sessão aparecem com flags de segurança corretas.

## Fase 1.2 - Criptografia de Dados Sensíveis
Objetivo: proteger PII de menores em repouso no banco.

### Tarefas
1. Criar `security_utils.py` com API:
   - `get_fernet()`
   - `encrypt_value(value)`
   - `decrypt_value(value)`
   - fallback seguro para valores vazios.
2. Definir lista de campos sensíveis no backend.
3. Criptografar ao persistir dados do formulário.
4. Descriptografar para exibição em telas administrativas.
5. Descriptografar para exportação (Excel/relatórios).
6. Adicionar `FIELD_ENCRYPTION_KEY` em `.env.example` e instruções de geração.

### Critérios de aceite
- Dados sensíveis ficam ilegíveis em leitura direta do SQLite.
- UI administrativa continua legível para usuário autorizado.
- Exportações mantêm consistência e não quebram estrutura.

## Fase 1.3 - Auditoria e Política de Senhas
Objetivo: rastreabilidade de acesso e reforço de credenciais.

### Tarefas
1. Criar tabela `audit_logs`.
2. Criar utilitário `log_audit_event(user_id, action, target, metadata)`.
3. Registrar eventos críticos:
   - login/logout
   - visualização de resposta
   - pontuação
   - exportação
   - gestão de usuários/categorias/testes.
4. Validar senha forte no cadastro com regex (mínimo 8, maiúscula, minúscula e número).
5. Exibir feedback claro de política de senha na UI de cadastro.

### Critérios de aceite
- Eventos críticos geram trilha auditável com timestamp e usuário.
- Cadastros com senha fraca são recusados.
- Mensagens de erro orientam correção pelo usuário.

## Riscos e Mitigações
- Risco: templates misturados (sintaxe Flask vs Django).  
  Mitigação: padronizar templates usados em runtime antes de fechar Fase 1.1.
- Risco: dados antigos sem criptografia.  
  Mitigação: script de migração progressiva por lote com backup prévio.
- Risco: regressão em rotas administrativas.  
  Mitigação: checklist funcional por rota e usuário admin.

## Plano de Verificação
- Teste manual guiado por fluxo:
  1. cadastro
  2. login
  3. preenchimento de questionário
  4. visão admin
  5. pontuação
  6. exportação.
- Verificação técnica:
  - tentativa de POST sem CSRF
  - leitura direta do banco para validar criptografia
  - inspeção de cookies de sessão
  - consulta da tabela de auditoria.

## Definição de Conclusão do Milestone 1
- Fase 1.1, 1.2 e 1.3 concluídas e marcadas no roadmap.
- `STATE.md` atualizado com status "Execução concluída".
- README e guia de operação atualizados com segurança e variáveis de ambiente.
