# 🗺️ Roadmap - SaS_NeuroPsicopedagogia (Versão 2.1.0)

Roadmap estruturado em ondas sequenciais para trazer segurança regulatória (LGPD), resiliência operacional, escalabilidade de nuvem e inteligência de diagnóstico clínico para a aplicação.

---

## 🔒 Milestone 1: Segurança, LGPD & Auditoria (Fase 1)
*Foco: Proteger dados sensíveis de menores, evitar ataques de hijacking e garantir conformidade jurídica.*

### Fase 1.1: Proteção CSRF & Hardening de Sessão (Em andamento - 2026-05-24)
- [ ] Instalar e configurar `Flask-WTF` e `CSRFProtect` em `app.py`.
- [ ] Adicionar tags `csrf_token` em todos os templates HTML contendo formulários (`login.html`, `register.html`, `form.html`, `edit_test_questions.html`, etc.).
- [ ] Configurar cookies de sessão com atributos de segurança (`HTTPOnly`, `SameSite='Lax'`, `Secure`).

### Fase 1.2: Criptografia de Dados Pessoais Sensíveis
- [ ] Criar módulo utilitário de criptografia (`security_utils.py`) com suporte a Fernet (criptografia autenticada simétrica).
- [ ] Mapear colunas sensíveis em `responses` (Nome, Nome dos Pais, Fones, Endereço, Celular, Observações).
- [ ] Implementar criptografia automática ao salvar e descriptografia ao exibir os dados no Dashboard e Excel.
- [ ] Adicionar instrução para geração automática de `FIELD_ENCRYPTION_KEY` no `.env.example`.

### Fase 1.3: Trilha de Auditoria & Política de Senhas
- [ ] Criar a tabela `audit_logs` no banco de dados.
- [ ] Adicionar decoradores/funções de auditoria automática (ex: registrar acessos a questionários de pacientes e exportação de dados).
- [ ] Implementar regex de validação de senha segura no backend (`app.py`, rota `/register`) e dicas de segurança na UI.

---

## 🛡️ Milestone 2: Resiliência, ORM & Escalabilidade (Fase 2)
*Foco: Preparar a arquitetura para múltiplos usuários simultâneos, nuvem e recuperação rápida de falhas.*

### Fase 2.1: Migração para SQLAlchemy & Migrations
- [ ] Integrar `Flask-SQLAlchemy` e `Flask-Migrate`.
- [ ] Definir modelos declarativos (`User`, `TestType`, `Response`, `Question`, `QuestionResponse`, `AuditLog`, `TestCategory`).
- [ ] Criar scripts de migração iniciais e migrar dados do banco antigo SQLite para o novo esquema SQLAlchemy.
- [ ] Substituir consultas de banco SQLite diretas em `app.py` pelas chamadas do ORM.

### Fase 2.2: Tratamento de Erros, Logs & Backups
- [ ] Criar manipuladores globais de erro para 404 e 500 com templates personalizados elegantes (`templates/errors/404.html`, `500.html`).
- [ ] Configurar o logger do Python para gravar avisos/erros em `logs/app.log` com rotação diária de arquivo.
- [ ] Escrever script de backup automático `backup_db.py` que gera cópias seguras e compactadas do SQLite e apaga cópias com mais de 30 dias.

### Fase 2.3: Dockerização & WSGI de Produção
- [ ] Criar arquivo `Dockerfile` otimizado para Python e Flask.
- [ ] Criar `docker-compose.yml` pré-configurado com suporte a volumes para o banco de dados.
- [ ] Criar script `run_prod.py` usando `Waitress` para servir a aplicação de forma segura e resiliente no ambiente Windows.

---

## 🧠 Milestone 3: IA de Borda & Diagnóstico Cognitivo Visual (Fase 3)
*Foco: Empoderar a neuropsicopedagoga com análise estatística, visualização de perfis e detecção de marcos de desenvolvimento precoce.*

### Fase 3.1: Edge AI - Mecanismo Heurístico de Diagnóstico
- [ ] Desenvolver classe `DiagnosticEngine` (`edge_ai.py`) para categorizar as 24 características marcantes em 5 dimensões intelectuais.
- [ ] Implementar validador de Marcos de Desenvolvimento (marcha, fala, escrita, leitura, cálculo) contra tabelas normativas, destacando precocidades significativas.
- [ ] Criar gerador de insights textuais e sugestões pedagógicas locais para o relatório clínico.

### Fase 3.2: Dashboard Cognitivo & Gráfico de Radar
- [ ] Integrar dados da IA de Borda na rota `/admin/resposta/<id>`.
- [ ] Renderizar gráfico de radar interativo (`Chart.js`) em `view_response.html` detalhando a afinidade do estudante com as dimensões de AH/SD.
- [ ] Exibir caixa de insights clínicos gerados localmente e sugestões de intervenção com layout premium (glassmorphism, cores harmônicas).
