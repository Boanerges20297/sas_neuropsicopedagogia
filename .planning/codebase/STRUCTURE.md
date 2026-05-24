# Estrutura do Diretório

Este documento descreve a organização física dos arquivos no repositório.

## 📂 Árvore de Diretórios Principal

```text
SaS_NeuroPsicopedagogia/
├── .planning/                # Arquivos do GSD (Roadmap, Planos, Estado)
├── ai_service/               # Microsserviço de IA de Borda (FastAPI)
│   ├── memory_db/            # Banco SQLite local da IA (Memory Palace)
│   ├── edge_ai.py            # Regras heurísticas e inteligência
│   ├── main.py               # Servidor FastAPI
│   └── parser_dsm.py         # Extrator de conteúdo do DSM-5-TR
├── avaliacao/                # App Principal Django
│   ├── migrations/           # Migrações do Banco de Dados
│   ├── models.py             # Modelos (Paciente, Resposta, Usuario, Audit)
│   ├── views.py              # Controladores e lógica de rotas
│   └── security_utils.py     # Criptografia LGPD (Fernet)
├── sas_project/              # Configurações do Projeto Django
│   ├── settings.py           # Configurações do Django
│   └── urls.py               # Rotas principais
├── scripts/                  # Scripts de automação SSH para VPS
├── static/                   # Arquivos estáticos (CSS, JS, Gráficos)
│   ├── library/              # PDFs de suporte científico (DSM-5)
│   └── scoring.js            # Lógica de score no front
├── templates/                # Templates HTML (compartilhados Django/Flask)
│   ├── includes/             # Partials (navbar, etc.)
│   └── *.html                # Telas de login, paciente, prontuário
├── Dockerfile                # Build da imagem da aplicação web
├── docker-compose.yml        # Orquestração local/VPS dos 3 contêineres
├── entrypoint.sh             # Inicialização do contêiner Django
├── requirements.txt          # Dependências Python globais
└── app.py                    # Legacy Flask App (não utilizado em produção)
```

## 🔍 Descrição dos Componentes Principais

* **`avaliacao/models.py`**: Contém o esquema relacional dos Pacientes, Anotações, Respostas (105 campos do questionário legado) e logs de auditoria.
* **`templates/`**: Mistura telas específicas de questionários legados (ex: `form.html`) com o sistema moderno de pacientes (ex: `pacientes_list.html`).
* **`app.py`**: Legado Flask que repete algumas lógicas de banco, mas não é usado na VPS. Deve ser limpo para simplificar a arquitetura.
