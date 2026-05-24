# Preocupações, Riscos e Pontos Críticos

Este documento lista os principais débitos técnicos, riscos e pontos de atenção arquiteturais identificados.

## ⚠️ Débitos Técnicos Críticos

### 1. Duplicidade de Frameworks (Django & Flask)
* **Problema**: O projeto tem arquivos do Flask (`app.py`) e do Django (`sas_project`, `avaliacao`). Embora apenas o Django esteja ativo no contêiner de produção da VPS, a coexistência no mesmo repositório causa confusão para desenvolvimento e manutenção.
* **Ação**: Remover `app.py` e limpar qualquer arquivo de configuração exclusivo do Flask.

### 2. Presença de Nomes Legados ("SaS" e "Teste")
* **Problema**: O usuário solicitou explicitamente a remoção de qualquer menção a "SaS" ou "Teste". Atualmente, existem variáveis, caminhos de diretório, banco de dados (ex: `sas_neuropsicopedagogia_db`) e títulos de páginas que utilizam estes termos.
* **Ação**: Renomear projeto de `sas_project` para `neuro_diagnosis` (ou similar), e atualizar todas as referências no front e back.

### 3. Falta de Testes Automatizados
* **Problema**: Não há suíte de testes automatizados rodando no CI/CD. Bugs em lógicas sensíveis como criptografia Fernet de dados LGPD podem passar despercebidos.

### 4. Gestão de Segredos no Repositório
* **Problema**: Chaves como `SECRET_KEY` ou `FIELD_ENCRYPTION_KEY` e a senha da VPS (`PASSWORD_VPS`) estão no arquivo `.env` local. É necessário garantir que estes segredos não sejam expostos e que na VPS sejam gerenciados de forma robusta.
