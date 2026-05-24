# Integrações do Sistema

Este documento descreve as integrações internas e externas do sistema.

## 🔄 Integrações Internas

### 1. Comunicação Django ↔️ Microsserviço de IA (FastAPI)
* **Protocolo**: HTTP (REST API)
* **Configuração**: URL definida via `AI_SERVICE_URL` no `.env` (ex: `http://ai:5001` no Docker Compose).
* **Fluxo**:
  1. A neuropsicopedagoga submete ou visualiza uma resposta de questionário.
  2. O Django faz uma requisição POST para o endpoint `/api/v1/analyze` do FastAPI passando os dados do paciente.
  3. O serviço de IA calcula as dimensões de Joseph Renzulli e faz a busca de suporte no DSM-5-TR, retornando JSON.
  4. O Django renderiza o gráfico de radar e os insights diagnósticos na página do paciente.

### 2. Django ↔️ Banco de Dados (MySQL / SQLite)
* **ORM**: Django ORM.
* **Segurança de Dados (LGPD)**: Integração com biblioteca `cryptography.fernet` para criptografia transparente no banco de dados. Os campos sensíveis são criptografados antes de salvar e descriptografados ao ler na memória.

## 📂 Integrações com Arquivos e Documentos

### 1. DSM-5-TR (PDF)
* **Localização**: `static/library/DSM-5-TR 2023 AHA portugues.pdf`.
* **Fluxo**: No startup do microsserviço de IA, o FastAPI lê e indexa semanticamente o PDF no banco de dados local `memory_db/memory_palace.db` para busca semântica em tempo real.

## 🚀 Integrações de Deployment e Gerenciamento

### 1. Scripts SSH Paramiko (Local ↔️ VPS)
* **Localização**: `scripts/`
* **Objetivo**: Permite empurrar alterações e executar comandos remotamente na VPS Hostinger através de SSH usando credenciais configuradas no `.env` (`HOST_VPS` e `PASSWORD_VPS`).
