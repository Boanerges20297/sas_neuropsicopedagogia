# 📋 Requisitos do Sistema - SaS_NeuroPsicopedagogia (Segurança, Resiliência, Escalabilidade & IA)

## 🔐 1. Segurança & Conformidade LGPD

### REQ-SEC-01: Proteção CSRF
- **Descrição**: Integrar proteção CSRF (Cross-Site Request Forgery) em todos os formulários da aplicação utilizando `Flask-WTF` / `CSRFProtect`.
- **Critério de Aceitação**: Todas as submissões POST/PUT/DELETE devem exigir um token CSRF válido, impedindo submissões externas não autorizadas.

### REQ-SEC-02: Criptografia de Dados Pessoais Sensíveis (LGPD)
- **Descrição**: Criptografar dados sensíveis de menores (nome, nomes dos pais, telefone, e-mail, observações clínicas) no banco de dados usando criptografia simétrica forte (`cryptography.fernet.Fernet` ou AES-256).
- **Critério de Aceitação**: Se o banco de dados for exposto, os dados identificáveis devem estar ilegíveis sem a chave secreta (`FIELD_ENCRYPTION_KEY`) definida no `.env`.

### REQ-SEC-03: Trilha de Auditoria (Audit Log)
- **Descrição**: Registrar no banco de dados (tabela `audit_logs`) todas as ações administrativas críticas.
- **Campos do Log**: `timestamp`, `user_id`, `action` (ex: "Visualizou Resposta ID 12", "Exportou Respostas para Excel", "Cadastrou Usuário"), `ip_address`.
- **Critério de Aceitação**: Registros de auditoria gerados automaticamente a cada ação do admin e protegidos contra modificação direta pela interface.

### REQ-SEC-04: Endurecimento de Sessões e Cookies
- **Descrição**: Configurar cookies de sessão com atributos de segurança (`SESSION_COOKIE_SECURE`, `SESSION_COOKIE_HTTPONLY`, `SESSION_COOKIE_SAMESITE`).
- **Critério de Aceitação**: Cookies não acessíveis por scripts JS e transmitidos apenas via HTTPS (em produção).

### REQ-SEC-05: Políticas de Senha e Validação
- **Descrição**: Adicionar validação de senhas seguras no registro (mínimo de 8 caracteres, pelo menos uma letra maiúscula, uma minúscula e um número).
- **Critério de Aceitação**: Formulário de registro recusa senhas fracas com mensagens informativas claras.

---

## 🛡️ 2. Resiliência & Estabilidade

### REQ-RES-01: Migração para Flask-SQLAlchemy (ORM)
- **Descrição**: Migrar a persistência do banco de dados de `sqlite3` puro para `Flask-SQLAlchemy` com suporte a pooling de conexões e tratamento automático de erros.
- **Critério de Aceitação**: Remoção de conexões manuais ad-hoc, prevenção de `Database is locked` do SQLite e código limpo e manutenível.

### REQ-RES-02: Gerenciamento Centralizado de Erros (Graceful Degradation)
- **Descrição**: Criar manipuladores globais para erros 404 e 500 com páginas de erro personalizadas e seguras (sem expor tracebacks).
- **Critério de Aceitação**: Em caso de falha, o usuário vê uma tela elegante e o erro é gravado localmente em arquivos de log rotativos (`app.log`).

### REQ-RES-03: Utilitário de Backups Automáticos
- **Descrição**: Criar um script/serviço que realiza backup datado do banco de dados SQLite para a pasta `backups/` e mantém um histórico rotativo dos últimos 10 backups.
- **Critério de Aceitação**: Script de backup executável manualmente ou via agendamento local.

---

## ⚡ 3. Escalabilidade

### REQ-ESC-01: Abstração de Banco de Dados e Migrações
- **Descrição**: Integrar `Flask-Migrate` para versionamento do esquema do banco de dados.
- **Critério de Aceitação**: Mudanças na modelagem de dados são feitas via arquivos de migração. O banco é agnóstico (fácil de trocar SQLite por PostgreSQL apenas mudando a URL no `.env`).

### REQ-ESC-02: Suporte a Servidor de Produção (Waitress / Gunicorn)
- **Descrição**: Configurar e documentar a execução do sistema em produção utilizando `Waitress` (servidor de produção WSGI leve nativo para Windows) ou `Gunicorn` via Docker.
- **Critério de Aceitação**: Script `run_prod.py` criado para inicializar com Waitress em vez de usar `app.run(debug=True)`.

### REQ-ESC-03: Dockerização
- **Descrição**: Criar `Dockerfile` e `docker-compose.yml` para facilitar a implantação escalável e isolada do sistema.
- **Critério de Aceitação**: Sistema sobe com um único comando `docker-compose up`.

---

## 🧠 4. IA de Borda (Edge AI Diagnostic Assistant)

### REQ-AI-01: Heuristic Cognitive Profiler (IA de Borda Super Leve)
- **Descrição**: Desenvolver um analisador neuropsicopedagógico local (100% privado, offline e com latência zero) baseado no modelo de Renzulli (Três Anéis) e no relatório Marland.
- **Mapeamento de Habilidades**: Categorizar os comportamentos descritos nas 24 caixas de seleção em 5 dimensões intelectuais/cognitivas:
  1. *Capacidade Intelectual Geral*
  2. *Pensamento Criativo (Criatividade)*
  3. *Talento Artístico*
  4. *Habilidade Psicomotora*
  5. *Habilidade de Liderança*
- **Análise de Marcos de Desenvolvimento**: Comparar idades de fala, marcha e escrita informadas com os marcos normativos da pediatria brasileira, alertando sobre desenvolvimento precoce (indicativo de AH/SD).
- **Critério de Aceitação**: A análise deve ser executada localmente no backend ou no frontend, gerando um resumo e insights estruturados para a Neuropsicopedagoga.

### REQ-AI-02: Gráfico de Radar Interativo (Visualizador de Perfil Cognitivo)
- **Descrição**: Renderizar um gráfico de radar (`Chart.js`) detalhado na tela de visualização de respostas (`view_response.html`), mostrando o percentual de afinidade do estudante com cada uma das 5 dimensões de superdotação.
- **Critério de Aceitação**: Gráfico de radar elegante, responsivo e com tooltips interativos para fácil interpretação clínica.
