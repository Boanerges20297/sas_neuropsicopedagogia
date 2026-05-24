# Plano de Implementação - Modernização e Limpeza do App Neuro-Diagnosis

Este plano descreve as etapas para remover os resquícios da arquitetura legado (Flask), renomear referências de "SaS" e "Teste" para termos mais adequados ("Avaliação", "Anamnese"), unificar o fluxo de atendimento em torno de **Pacientes** e aprimorar a interface e o assistente de IA local para a Neuropsicopedagoga.

## User Review Required

> [!IMPORTANT]
> **Mudanças Críticas de Banco de Dados:**
> 1. Removeremos tabelas legadas (`CategoriaTeste`, `Teste`, `Questao`, `RespostaQuestao`) que pertenciam ao sistema de testes dinâmicos antigo, focando na ficha clínica estruturada de 105 campos.
> 2. Associaremos a ficha clínica estruturada (atualmente no modelo `Resposta`) diretamente ao modelo `Paciente` via chave estrangeira.
> 3. Renomearemos o projeto Django de `sas_project` para `neuro_diagnosis` para alinhar com o domínio da VPS (`neuro-diagnosis.tech`).

> [!WARNING]
> **Exclusão de Arquivos:**
> Arquivos Flask antigos (`app.py`, `app_database.db`, `responses.db`, `migrate_sqlite_to_mysql.py`) e arquivos temporários serão completamente removidos do repositório para limpar o diretório.

## Open Questions

- **Nome da Clínica/Profissional:** Gostaria de personalizar a marca "M.I. Joca de Sousa Teixeira" para o nome específico da sua esposa ou da clínica dela? (Podemos parametrizar isso via `.env` como `CLINICA_NOME` e `PROFISSIONAL_NOME`).

---

## Proposed Changes

### 1. Limpeza de Código Legado (Flask e Scripts Órfãos)

#### [DELETE] [app.py](file:///c:/Users/Boanerges/Desktop/Projetos/SaS_NeuroPsicopedagogia/app.py)
#### [DELETE] [app_database.db](file:///c:/Users/Boanerges/Desktop/Projetos/SaS_NeuroPsicopedagogia/app_database.db)
#### [DELETE] [responses.db](file:///c:/Users/Boanerges/Desktop/Projetos/SaS_NeuroPsicopedagogia/responses.db)
#### [DELETE] [responses.xlsx](file:///c:/Users/Boanerges/Desktop/Projetos/SaS_NeuroPsicopedagogia/responses.xlsx)
#### [DELETE] [migrate_sqlite_to_mysql.py](file:///c:/Users/Boanerges/Desktop/Projetos/SaS_NeuroPsicopedagogia/migrate_sqlite_to_mysql.py)

---

### 2. Renomeação do Projeto e Atualização de Infraestrutura

#### [MODIFY] [manage.py](file:///c:/Users/Boanerges/Desktop/Projetos/SaS_NeuroPsicopedagogia/manage.py)
* Atualizar `DJANGO_SETTINGS_MODULE` de `sas_project.settings` para `neuro_diagnosis.settings`.

#### [MODIFY] [Dockerfile](file:///c:/Users/Boanerges/Desktop/Projetos/SaS_NeuroPsicopedagogia/Dockerfile)
#### [MODIFY] [docker-compose.yml](file:///c:/Users/Boanerges/Desktop/Projetos/SaS_NeuroPsicopedagogia/docker-compose.yml)
#### [MODIFY] [entrypoint.sh](file:///c:/Users/Boanerges/Desktop/Projetos/SaS_NeuroPsicopedagogia/entrypoint.sh)
* Renomear caminhos e referências de `sas_project` para `neuro_diagnosis`.

#### [NEW] [neuro_diagnosis/](file:///c:/Users/Boanerges/Desktop/Projetos/SaS_NeuroPsicopedagogia/neuro_diagnosis)
* Renomear pasta `sas_project` para `neuro_diagnosis`.
* Atualizar `wsgi.py`, `asgi.py` e `settings.py` com o novo nome do projeto.

---

### 3. Ajuste de Modelos e Banco de Dados (Django ORM)

#### [MODIFY] [avaliacao/models.py](file:///c:/Users/Boanerges/Desktop/Projetos/SaS_NeuroPsicopedagogia/avaliacao/models.py)
* Remover modelos órfãos: `CategoriaTeste`, `Teste`, `Questao`, `RespostaQuestao`.
* Renomear modelo `Resposta` para `AvaliacaoClinica`.
* Adicionar chave estrangeira em `AvaliacaoClinica` para `Paciente`:
  ```python
  paciente = models.ForeignKey(Paciente, on_delete=models.CASCADE, related_name='avaliacoes', null=True, blank=True)
  ```
* Criar migrações do Django (`python manage.py makemigrations` e `python manage.py migrate`).

---

### 4. Limpeza de Visualizações e Fluxo de Pacientes

#### [MODIFY] [avaliacao/urls.py](file:///c:/Users/Boanerges/Desktop/Projetos/SaS_NeuroPsicopedagogia/avaliacao/urls.py)
#### [MODIFY] [avaliacao/views.py](file:///c:/Users/Boanerges/Desktop/Projetos/SaS_NeuroPsicopedagogia/avaliacao/views.py)
* Remover rotas e funções de controle ligadas a "Testes" (`legacy_test`, `submit_test`, `take_test`, etc.).
* Atualizar rota `/dashboard/` para focar em métricas de Pacientes e Atendimentos.
* Adaptar `/exportar/` para gerar a planilha com base no novo modelo `AvaliacaoClinica` associado aos Pacientes.

---

### 5. Modernização e Refinamento do Frontend

#### [MODIFY] [templates/includes/admin_navbar.html](file:///c:/Users/Boanerges/Desktop/Projetos/SaS_NeuroPsicopedagogia/templates/includes/admin_navbar.html)
* Ajustar links: remover "Respostas" e "Consulta IA" soltos; integrar "Avaliações" e centralizar o fluxo na listagem de "Pacientes".
* Tornar o título parametrizável para o nome da clínica/profissional.

#### [MODIFY] [templates/dashboard.html](file:///c:/Users/Boanerges/Desktop/Projetos/SaS_NeuroPsicopedagogia/templates/dashboard.html)
* Modernizar visual do dashboard para exibir total de pacientes ativos, número de atendimentos na semana, e atalhos rápidos para "Cadastrar Paciente" e "Ver Prontuários".

#### [MODIFY] [templates/paciente_detail.html](file:///c:/Users/Boanerges/Desktop/Projetos/SaS_NeuroPsicopedagogia/templates/paciente_detail.html)
* Adicionar seção estilizada para exibir as avaliações clínicas vinculadas àquele paciente.
* Adicionar card interativo da IA local de borda que permite consultar a anamnese do paciente instantaneamente contra as diretrizes do DSM-5-TR indexadas.

---

## Verification Plan

### Automated Tests
- Criar teste de sanidade em `avaliacao/tests.py` validando que as rotas básicas do painel do paciente respondem HTTP 200.
- Executar `python manage.py test` localmente.

### Manual Verification
- Rodar o app localmente com SQLite e certificar-se de que o fluxo de login, listagem de pacientes, criação de anotação de sessão, e consulta à IA funcionam perfeitamente.
- Subir alterações para a VPS de teste usando os scripts em `scripts/` e validar o container `neuro-diagnosis-app` em produção.
