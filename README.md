# Neuro-Diagnosis

Aplicacao web para atendimento clinico neuropsicopedagogico com:

- cadastro e prontuario de pacientes
- anamnese estruturada
- anotacoes por atendimento
- consulta IA local com memoria supervisionada
- exportacao operacional
- trilha de auditoria e criptografia de dados sensiveis

O sistema foi reorganizado para funcionar como produto clinico, e nao como um formulario isolado. A navegacao principal hoje gira em torno de `Pacientes -> Prontuario -> Anamnese -> Consulta IA -> Avaliacoes`.

## Visao geral

O projeto usa duas camadas principais:

1. `Django`
   Responsavel por autenticacao, interface, prontuario, anamnese, dashboard, auditoria, persistencia e exportacao.

2. `FastAPI`
   Responsavel pelo motor de IA local, analise heuristica, memoria semantica e aprendizado incremental.

O banco pode rodar em:

- `SQLite` para desenvolvimento local
- `MySQL 8` para producao

## Fluxo clinico atual

### 1. Login

- A tela de login foi preservada.
- O sistema diferencia perfil `admin` e `user`.
- A neuropsicopedagoga administradora entra no dashboard clinico.

### 2. Dashboard clinico

Tela de operacao com:

- total de avaliacoes
- total de pacientes
- total de usuarios
- ultimo registro
- distribuicao recente de atendimentos

### 3. Area de pacientes

Fluxo principal da aplicacao:

1. cadastrar paciente
2. abrir prontuario
3. registrar anotacoes de atendimento
4. abrir nova anamnese vinculada ao paciente
5. consultar a IA com contexto clinico
6. registrar feedback sobre a utilidade da resposta da IA

### 4. Prontuario do paciente

Cada paciente concentra:

- dados cadastrais
- informacoes escolares
- queixa principal
- observacoes
- historico de anotacoes
- vinculo com anamneses
- vinculo com consultas IA

### 5. Anotacoes de atendimento

As anotacoes podem ser registradas por tipo:

- `sessao`
- `observacao`
- `orientacao`
- `encaminhamento`
- `ia`

Campos relevantes:

- `data_consulta`
- `titulo`
- `conteudo`

As anotacoes sao usadas em dois niveis:

1. historico do prontuario
2. base de contexto para aprendizado da IA

### 6. Anamnese estruturada

A anamnese foi reorganizada em blocos menores para uso clinico:

- identificacao do caso
- escola e aprendizagem
- perfil observado
- fechamento do registro

O modelo `AvaliacaoClinica` ainda concentra o formulario clinico mais extenso do sistema, com foco em:

- desenvolvimento
- vida escolar
- vida social
- perfil biopsicossocial
- caracteristicas observadas
- observacoes adicionais

### 7. Avaliacao clinica

As anamneses salvas alimentam:

- lista administrativa de avaliacoes
- leitura do prontuario
- consulta IA
- exportacao em Excel

### 8. Consulta IA clinica

A tela `Consulta IA` funciona como console clinico do sistema.

Fluxo:

1. a profissional seleciona o paciente ou usa consulta geral
2. informa a pergunta clinica
3. descreve o contexto da sessao
4. o Django envia a requisicao ao microsservico local
5. a resposta e salva no banco
6. a profissional marca se a resposta foi acerto, parcial ou erro
7. o feedback retorna para o fluxo de aprendizado

## Qual IA esta rodando hoje

Hoje o sistema **nao usa uma LLM remota** como padrao.

O que roda e:

- um microsservico local `FastAPI`
- um motor heuristico proprio chamado `EdgeAIDiagnosticEngine`
- uma memoria semantica local chamada `MemoryPalace`
- indexacao local do `DSM-5-TR` quando o PDF esta disponivel

Arquivos principais:

- [ai_service/main.py](C:\Users\Boanerges\Desktop\Projetos\SaS_NeuroPsicopedagogia\ai_service\main.py)
- [ai_service/edge_ai.py](C:\Users\Boanerges\Desktop\Projetos\SaS_NeuroPsicopedagogia\ai_service\edge_ai.py)
- [ai_service/memory_palace.py](C:\Users\Boanerges\Desktop\Projetos\SaS_NeuroPsicopedagogia\ai_service\memory_palace.py)
- [ai_service/parser_dsm.py](C:\Users\Boanerges\Desktop\Projetos\SaS_NeuroPsicopedagogia\ai_service\parser_dsm.py)

## Fluxo detalhado da IA

### Analise

1. Django envia um caso para `POST /api/v1/analyze`
2. o motor heuristico processa:
   - caracteristicas observadas
   - marcos de desenvolvimento
   - leitura precoce
   - escrita precoce
   - fala e marcha
   - interesses e dificuldades
3. o motor calcula sinais e dimensoes heuristicas
4. a memoria semantica busca suporte textual relevante
5. o resultado volta para a interface clinica

### Aprendizado

O sistema manda conhecimento para `POST /api/v1/learn` em varios momentos:

- nova anamnese salva
- anotacao clinica registrada
- consulta IA realizada
- feedback humano da consulta

### Feedback supervisionado

O aprendizado supervisionado usa pesos clinicos:

- `acerto = +2`
- `parcial = +1`
- `erro = -2`

Isso permite que a memoria receba sinal positivo ou negativo sobre a utilidade real das respostas.

### Contexto por dominio

O sistema tenta segmentar aprendizado por contexto usando dominios como:

- `geral`
- `paciente_<id>`

Isso ajuda a separar memoria global de memoria ligada a um caso.

## Modelos principais

Arquivos:

- [avaliacao/models.py](C:\Users\Boanerges\Desktop\Projetos\SaS_NeuroPsicopedagogia\avaliacao\models.py)

### `PerfilUsuario`

- usuario customizado do Django
- perfis `admin` e `user`

### `Paciente`

- dados de cadastro
- escola
- serie
- queixa principal
- observacoes

### `AnotacaoAtendimento`

- historico clinico por paciente
- tipo da anotacao
- data da consulta
- titulo e conteudo

### `AvaliacaoClinica`

- anamnese estruturada e avaliacao extensa
- associacao opcional com paciente
- score e parecer administrativo

### `ConsultaIAClinica`

- pergunta
- contexto
- resultado da IA
- profissional
- paciente opcional

### `FeedbackConsultaIA`

- julgamento da resposta
- peso aplicado
- comentario

### `LogAuditoria`

- usuario
- acao
- IP
- data e hora

## Datas e formato Brasil

O sistema foi ajustado para trabalhar com datas no formato brasileiro:

- `dd/mm/yyyy`
- `dd/mm/yyyy HH:MM`

Campos importantes seguem esse padrao na interface:

- `data_nascimento`
- `data_consulta`
- `bairro_data`
- exibicoes de historico e dashboard

## Seguranca e LGPD

### Criptografia de campos

Campos sensiveis sao criptografados com `Fernet` antes de ir ao banco.

Exemplos de dados protegidos:

- nome
- telefone
- email
- endereco
- queixa principal
- observacoes
- conteudos clinicos de anotacoes
- conteudo de consulta IA

Arquivo:

- [avaliacao/security_utils.py](C:\Users\Boanerges\Desktop\Projetos\SaS_NeuroPsicopedagogia\avaliacao\security_utils.py)

### Auditoria

O sistema registra eventos como:

- login
- logout
- acesso ao dashboard
- visualizacao de prontuario
- anotacao adicionada
- exportacao
- consulta IA
- feedback sobre IA

### Hardening de sessao

Configuracoes presentes:

- `SESSION_COOKIE_HTTPONLY`
- `CSRF_COOKIE_HTTPONLY`
- `SameSite=Lax`
- suporte a `SESSION_COOKIE_SECURE` e `CSRF_COOKIE_SECURE`

## Estrutura do projeto

```text
SaS_NeuroPsicopedagogia/
|-- ai_service/
|   |-- main.py
|   |-- edge_ai.py
|   |-- memory_palace.py
|   |-- parser_dsm.py
|
|-- avaliacao/
|   |-- migrations/
|   |-- models.py
|   |-- views.py
|   |-- urls.py
|   |-- security_utils.py
|
|-- neuro_diagnosis/
|   |-- settings.py
|   |-- urls.py
|   |-- wsgi.py
|
|-- static/
|   |-- style.css
|   |-- dashboard.js
|   |-- library/
|
|-- templates/
|   |-- login.html
|   |-- dashboard.html
|   |-- pacientes_list.html
|   |-- paciente_form.html
|   |-- paciente_detail.html
|   |-- ia_consulta.html
|   |-- admin_avaliacoes.html
|   |-- view_response.html
|   `-- includes/
|
|-- manage.py
|-- create_admin.py
|-- run_prod.py
|-- Dockerfile
|-- docker-compose.yml
`-- requirements.txt
```

## Rotas principais

Arquivo:

- [avaliacao/urls.py](C:\Users\Boanerges\Desktop\Projetos\SaS_NeuroPsicopedagogia\avaliacao\urls.py)

### Publicas

- `/`
- `/login/`
- `/register/`
- `/logout/`
- `/area-do-usuario/`

### Fluxo de anamnese

- `/anamnese/nova/`
- `/anamnese/salvar/`

### Area clinica administrativa

- `/dashboard/`
- `/admin/pacientes/`
- `/admin/pacientes/novo/`
- `/admin/pacientes/<id>/`
- `/admin/pacientes/<id>/nova-anamnese/`
- `/admin/avaliacoes/`
- `/admin/avaliacao/<id>/`
- `/admin/avaliacao/<id>/pontuar/`
- `/admin/usuarios/`
- `/admin/ia/`
- `/admin/ia/<id>/feedback/`
- `/exportar/`

## Interface e UX

A interface foi reformulada para sair do visual de formulario cru e ir para um padrao mais proximo de produto clinico:

- hero forte no topo
- paines de trabalho
- trilho lateral de contexto
- tabelas com mais hierarquia visual
- prontuario e anamnese em blocos curtos
- mesma linguagem visual entre dashboard, pacientes, prontuario e IA

Observacao:

- a tela de login foi mantida fora dessa reformulacao por decisao de produto

## Requisitos

- Python `3.10`
- pip
- virtualenv opcional
- MySQL `8.0` para producao
- Docker e Docker Compose para stack completa

Dependencias Python:

- Django
- FastAPI
- requests
- openpyxl
- cryptography
- PyMuPDF
- gunicorn
- whitenoise
- mysqlclient

## Configuracao local

### 1. Clonar e entrar no projeto

```powershell
git clone <repo>
cd SaS_NeuroPsicopedagogia
```

### 2. Criar e ativar ambiente virtual

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3. Instalar dependencias

```powershell
pip install -r requirements.txt
```

### 4. Criar arquivo `.env`

Use `.env.example` como base.

Exemplo minimo para desenvolvimento local:

```env
DEBUG_MODE=True
SECRET_KEY=troque-esta-chave
ALLOWED_HOSTS=*
USE_SQLITE=True

AI_SERVICE_URL=http://localhost:5001

ADMIN_EMAIL=admin@admin.com
ADMIN_PASSWORD=admin123
ADMIN_NAME=Administradora
```

Observacao:

- se `FIELD_ENCRYPTION_KEY` nao existir, o sistema tenta gerar uma automaticamente

### 5. Rodar migracoes

```powershell
python manage.py migrate
```

### 6. Criar admin inicial

```powershell
python create_admin.py
```

### 7. Subir o Django

```powershell
python manage.py runserver
```

Aplicacao web:

- `http://127.0.0.1:8000`

### 8. Subir o microsservico de IA

Em outro terminal:

```powershell
cd ai_service
uvicorn main:app --host 0.0.0.0 --port 5001 --reload
```

Servico IA:

- `http://127.0.0.1:5001`

## Configuracao com Docker

O projeto possui stack pronta com:

- app Django
- microsservico IA
- MySQL

### Subir tudo

```bash
docker-compose up --build -d
```

### Aplicar migracoes no container

```bash
docker-compose exec app python manage.py migrate
```

### Criar admin

```bash
docker-compose exec app python create_admin.py
```

## Variaveis de ambiente importantes

### Aplicacao Django

- `DEBUG_MODE`
- `SECRET_KEY`
- `ALLOWED_HOSTS`
- `USE_SQLITE`
- `AI_SERVICE_URL`
- `SESSION_COOKIE_SECURE`
- `CSRF_COOKIE_SECURE`
- `CSRF_TRUSTED_ORIGINS`
- `CLINICA_NOME`
- `PROFISSIONAL_NOME`

### Banco

- `DB_NAME`
- `DB_USER`
- `DB_PASSWORD`
- `DB_HOST`
- `DB_PORT`
- `MYSQL_ROOT_PASSWORD`

### Criptografia

- `FIELD_ENCRYPTION_KEY`

### Admin inicial

- `ADMIN_EMAIL`
- `ADMIN_PASSWORD`
- `ADMIN_NAME`

## Exportacao

O sistema exporta a base clinica para planilha Excel.

Rota:

- `/exportar/`

O arquivo inclui:

- identificacao da avaliacao
- paciente vinculado
- data e hora
- pontuacao
- parecer
- campos clinicos exportaveis

## Operacao recomendada

Fluxo sugerido para uso diario da neuropsicopedagoga:

1. abrir `Pacientes`
2. cadastrar ou localizar o caso
3. revisar prontuario
4. registrar anotacao da sessao
5. abrir anamnese quando necessario
6. usar `Consulta IA` como apoio de hipotese
7. marcar feedback da IA
8. revisar `Avaliacoes`
9. exportar quando precisar de consolidado

## Estado atual do produto

O sistema ja tem:

- fluxo clinico central funcional
- visual unificado nas telas principais
- IA local integrada
- aprendizado supervisionado basico
- criptografia de campos
- auditoria

O sistema ainda pode evoluir em:

- explainability mais profunda da IA
- dashboards clinicos mais densos
- filtros avancados de prontuario
- modelos de acompanhamento evolutivo
- camada formal de validacao automatizada de UX

## Arquivos mais importantes para continuar o projeto

- [README.md](C:\Users\Boanerges\Desktop\Projetos\SaS_NeuroPsicopedagogia\README.md)
- [neuro_diagnosis/settings.py](C:\Users\Boanerges\Desktop\Projetos\SaS_NeuroPsicopedagogia\neuro_diagnosis\settings.py)
- [avaliacao/models.py](C:\Users\Boanerges\Desktop\Projetos\SaS_NeuroPsicopedagogia\avaliacao\models.py)
- [avaliacao/views.py](C:\Users\Boanerges\Desktop\Projetos\SaS_NeuroPsicopedagogia\avaliacao\views.py)
- [avaliacao/urls.py](C:\Users\Boanerges\Desktop\Projetos\SaS_NeuroPsicopedagogia\avaliacao\urls.py)
- [static/style.css](C:\Users\Boanerges\Desktop\Projetos\SaS_NeuroPsicopedagogia\static\style.css)
- [templates/ia_consulta.html](C:\Users\Boanerges\Desktop\Projetos\SaS_NeuroPsicopedagogia\templates\ia_consulta.html)
- [templates/pacientes_list.html](C:\Users\Boanerges\Desktop\Projetos\SaS_NeuroPsicopedagogia\templates\pacientes_list.html)

## Observacoes finais

- O README antigo ficou defasado em relacao ao novo fluxo clinico.
- Este documento passa a ser a referencia principal do produto atual.
- Se houver outros `.md` antigos no repositorio, trate-os como material historico ate serem consolidados.
