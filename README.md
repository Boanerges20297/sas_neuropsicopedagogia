# 🎯 SaS_NeuroPsicopedagogia (Versão 2.1.0 - Django, MySQL & IA de Borda)

Sistema de prontuário, aplicação de questionários de diagnóstico de **Altas Habilidades/Superdotação (AEE-AH/SD)** e auxílio diagnóstico inteligente baseados no modelo de Renzulli e no **DSM-5-TR**.

---

## ✨ Novidades da Versão 2.1 (Upgrade Arquitetural)

### 🔒 1. Segurança & Conformidade LGPD
- **Criptografia Simétrica Transparente**: O sistema encripta automaticamente todos os dados sensíveis identificáveis de menores de idade (nomes, telefones, endereço e anotações médicas) no banco utilizando **Fernet (AES-128 GCM)**, descriptografando-os em memória apenas na exibição do admin logado.
- **Proteção CSRF**: Middleware ativo barrando submissões de sites terceiros não autorizados.
- **Cookies e Sessões Endurecidas**: Configurações de cookies de sessão HTTPOnly e SameSite impedindo sequestro de sessão (Session Hijacking).
- **Trilha de Auditoria (Audit Log)**: Registro persistente de quem acessou, editou ou exportou os prontuários dos pacientes para conformidade legal completa.

### 💾 2. Banco MySQL & Fallback SQLite (Desenvolvimento)
- **Persistência MySQL**: Suporte a banco de dados robusto MySQL 8.0 para suportar picos de acessos e concorrência na VPS.
- **SQLite Fallback**: Para testes locais ágeis sem necessidade do MySQL rodando em sua máquina, o sistema automaticamente detecta o ambiente e ativa um fallback local SQLite em `db.sqlite3`.
- **Versionamento com Django ORM**: Remoção de queries direct sqlite3 em favor do robusto Django ORM e suas migrações.

### 🧠 3. Microsserviço de IA Independente & Palácio da Memória
- **Arquitetura de Microsserviços**: O motor da IA foi isolado em seu próprio container independente (`FastAPI`), permitindo que outros projetos consumam sua inteligência via requisições REST JSON.
- **Palácio da Memória Vetorial**: Mecanismo de busca semântica em banco vetorial embarcado no container da IA, permitindo separar o aprendizado da IA por contextos específicos (escolas, projetos, clínicas).
- **Leitor Automático de DSM-5-TR**: Módulo em **PyMuPDF** que lê o arquivo original `DSM-5-TR 2023 AHA portugues.pdf` (localizado em `static/library/`) e indexa de forma inteligente os parágrafos de interesse clínico, fornecendo fundamentações automáticas e insights no prontuário.
- **Radar de Renzulli**: Gráfico de radar interativo (`Chart.js`) renderizado na tela de prontuários administrativamente.

---

## 📁 Estrutura Atualizada do Projeto

```
c:/Users/Boanerges/Desktop/Projetos/SaS_NeuroPsicopedagogia/
├── backup_flask/               # Backup de segurança do Flask antigo
├── Dockerfile                  # Builds do container Django
├── docker-compose.yml          # Orquestração Django + FastAPI IA + MySQL
├── requirements.txt            # Dependências atualizadas do Python
├── migrate_sqlite_to_mysql.py  # Script de importação dos dados legados SQLite -> MySQL
├── create_admin.py             # Script para inicialização do administrador principal
├── run_prod.py                 # Runner de produção local Windows (Waitress)
│
├── sas_project/                # Pasta de configurações do Django
│   ├── settings.py             # Parâmetros de segurança, cookies e MySQL
│   └── urls.py                 # Roteamento global de telas
│
├── avaliacao/                  # Aplicativo principal do sistema
│   ├── models.py               # Modelos ORM (User, Resposta de 105 campos, LogAuditoria)
│   ├── security_utils.py       # Algoritmo Fernet de criptografia
│   ├── views.py                # Controladores do Dashboard, login e integração de IA
│   └── urls.py                 # Rotas do app
│
└── ai_service/                 # Microsserviço independente de IA de Borda (FastAPI)
    ├── main.py                 # API REST e inicializador automático do DSM-5
    ├── edge_ai.py              # Motor heurístico e insights diagnósticos
    ├── memory_palace.py        # Índice vetorial (ChromaDB/FAISS) local em SQLite
    ├── parser_dsm.py           # Parser PDF usando PyMuPDF
    └── Dockerfile              # Build do container de IA
```

---

## 🚦 Executando Localmente (Desenvolvimento Rápido)

Graças ao fallback automático para SQLite, você pode rodar a aplicação localmente no Windows sem precisar configurar um servidor MySQL:

### 1. Ativar o Ambiente Virtual e Instalar dependências
```powershell
& ".venv\Scripts\Activate.ps1"
pip install -r requirements.txt
```

### 2. Rodar Migrações Iniciais
```powershell
python manage.py migrate
```

### 3. Criar Administrador Padrão
```powershell
python create_admin.py
```
*Credenciais Iniciais:*
- **E-mail**: `admin@admin.com`
- **Senha**: `admin123` *(Altere no arquivo `.env` após rodar)*

### 4. Rodar o Servidor
```powershell
python manage.py runserver
```
Acesse no seu navegador: `http://127.0.0.1:8000/`

---

## 🐳 Implantando na VPS Hostinger (Docker Containers)

Em seu servidor VPS Hostinger (8GB RAM, 100GB SSD), a implantação é feita de forma profissional utilizando o Docker:

### 1. Configurar o `.env` de Produção
Crie um arquivo `.env` na VPS definindo o banco MySQL e a URL interna do serviço de IA:
```env
DEBUG_MODE=False
USE_SQLITE=False   # <--- ATIVA O MYSQL EM PRODUÇÃO
DB_NAME=sas_neuropsicopedagogia_db
DB_USER=sas_user
DB_PASSWORD=sua_senha_segura_aqui
DB_HOST=db
DB_PORT=3306
AI_SERVICE_URL=http://ai:5001
SECRET_KEY=sua_chave_secreta_vps
```

### 2. Rodar a Construção e Inicialização
```bash
docker-compose up --build -d
```
Este único comando compila a aplicação Django (servida via Gunicorn WSGI na porta `8000`), inicializa o microsserviço de IA FastAPI (porta `5001`), inicia a base do MySQL 8.0 persistida fisicamente e inicia a indexação automática em segundo plano do PDF do DSM-5-TR!

### 3. Aplicar Migrações e Criar Admin na VPS
```bash
docker-compose exec app python manage.py migrate
docker-compose exec app python create_admin.py
```

### 4. Migrar Prontuários do SQLite Antigo
Se possuir registros no banco legado, copie seu arquivo `app_database.db` para a pasta do projeto na VPS e rode:
```bash
docker-compose exec app python migrate_sqlite_to_mysql.py
```
*Os prontuários serão importados para o MySQL, sendo criptografados automaticamente em conformidade com a LGPD.*

---

## 🛡️ Segurança Adicional da VPS
A Hostinger isolará os containers em uma rede virtual fechada (`sas_network`). O banco de dados MySQL (`sas_db`) estará trancado e inacessível pela internet externa, expondo apenas a porta `8000` (Django/Web) para o público, garantindo máxima segurança para os dados médicos dos menores avaliados.
