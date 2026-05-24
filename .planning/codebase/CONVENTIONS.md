# Convenções de Código e Padrões

Este documento resume as práticas recomendadas de estilo, segurança e estruturação observadas na base de código.

## 🐍 Padrões Python e Django

* **Style Guide**: Segue o PEP 8 (snake_case para variáveis e funções, PascalCase para classes).
* **Idioma**: Nomenclatura em português para classes de domínio clínico (`Paciente`, `Resposta`, `LogAuditoria`, `AnotacaoAtendimento`) e inglês para configurações estruturais do framework (`settings.py`, `middleware`).

## 🔐 Padrões de Segurança e LGPD

### 1. Criptografia de Campos (Criptografia Transparente)
* **Princípio**: Qualquer dado que identifique diretamente um menor (nome, telefone, responsável, observações clínicas) deve ser criptografado no banco de dados.
* **Implementação**: Método `save()` dos modelos intercepta os campos definidos em `SENSITIVE_FIELDS` e os criptografa usando Fernet (`cryptography` library) se ainda não estiverem criptografados.
* **Leitura**: Deve-se chamar explicitamente `decrypt_sensitive()` na instância carregada do banco antes de repassar para renderização no template.

### 2. Logs de Auditoria
* **Implementação**: Ações administrativas relevantes (como visualização de prontuários) geram um registro em `LogAuditoria` anotando o usuário executor, a ação realizada e o IP do solicitante.

## 📁 Convenções de Templates HTML

* **Herança**: A maioria dos templates herda de um layout comum ou inclui componentes globais (como `templates/includes/admin_navbar.html`).
* **Design**: Mistura de HSL CSS tailored layouts. Estilização é feita via CSS Vanilla localizado no diretório `/static/`.
