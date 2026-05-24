# Stack de Tecnologia

Este documento detalha o conjunto de tecnologias utilizadas no projeto.

## 🛠️ Componentes do Sistema

### 1. Backend Web Principal
* **Framework**: Django (v4.2+)
  * **Configuração**: `sas_project/settings.py`
  * **App Principal**: `avaliacao/`
  * **Recursos**: Django ORM, Sistema de Autenticação Customizado (`PerfilUsuario`), CSRF Protection, Whitenoise para arquivos estáticos.
* **Legacy/Alternative**: Flask (`app.py`)
  * Atualmente o Dockerfile e docker-compose iniciam o Django. O arquivo `app.py` é um backend Flask alternativo que compartilha os mesmos templates, mas usa SQLite puro e não está ativo na VPS.

### 2. Microsserviço de Inteligência Artificial (Edge AI)
* **Framework**: FastAPI (v0.95.0+)
  * **Localização**: `ai_service/`
  * **Servidor**: Uvicorn (v0.20.0+)
  * **Recursos**: Pydantic para validação, Motor de análise clínica heurística (`EdgeAIDiagnosticEngine`), "Palácio da Memória" (`MemoryPalace`) usando SQLite para busca semântica, integração com PDF parser (`PyMuPDF`) para o DSM-5-TR.

### 3. Banco de Dados
* **Produção (VPS)**: MySQL (v8.0)
  * Gerenciado via contêiner Docker `neuro-diagnosis-db`.
* **Desenvolvimento (Local)**: SQLite (`db.sqlite3` para Django, `app_database.db` e `responses.db` para Flask).
  * Ativado via flag `USE_SQLITE=True` no `.env`.

### 4. Servidor Web, Proxy e Infraestrutura
* **Orquestração**: Docker & Docker Compose (`docker-compose.yml`)
* **Proxy Reverso & SSL**: Traefik (v3.0/latest)
* **Servidor WSGI**: Gunicorn (v22.0.0) para Django
* **Servidor ASGI**: Uvicorn para FastAPI

### 5. Frontend
* **Estrutura**: HTML5 Semântico
* **Estilização**: CSS3 Vanilla (sem Tailwind/Bootstrap no núcleo, com design personalizado)
* **Interatividade**: JavaScript Moderno (ES6+), Chart.js (para gráficos de radar de dimensões de Renzulli).

### 6. Scripts de Automação e Deployment
* **Bibliotecas**: `paramiko` para execução SSH remota, `cryptography` (Fernet) para criptografia transparente de campos sensíveis de pacientes (LGPD).
