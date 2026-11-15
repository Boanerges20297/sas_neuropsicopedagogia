# 🔐 Guia de Segurança - Sistema de Avaliação

## 📋 Checklist de Segurança

### 1️⃣ Configuração Inicial (OBRIGATÓRIO)

#### Gerar SECRET_KEY segura
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```
- Copie o resultado e cole no arquivo `.env` na variável `SECRET_KEY`

#### Alterar senha do administrador
- Abra o arquivo `.env`
- Altere `ADMIN_PASSWORD` para uma senha forte
- Use no mínimo 12 caracteres com letras, números e símbolos

#### Alterar email do administrador
- No arquivo `.env`, altere `ADMIN_EMAIL` para um email real
- Use um email que você tenha acesso

### 2️⃣ Configurações por Ambiente

#### Desenvolvimento (seu computador)
```env
DEBUG_MODE=True
HOST=127.0.0.1
PORT=5000
```

#### Produção (servidor online)
```env
DEBUG_MODE=False
HOST=0.0.0.0
PORT=5000
SECRET_KEY=(chave-gerada-com-64-caracteres)
```

### 3️⃣ Proteção do Arquivo .env

⚠️ **NUNCA** compartilhe o arquivo `.env` em:
- Repositórios Git/GitHub
- E-mails
- Mensagens de WhatsApp/Telegram
- Qualquer lugar público

✅ O arquivo `.gitignore` já está configurado para proteger o `.env`

### 4️⃣ Backup do Banco de Dados

Faça backups regulares do arquivo `app_database.db`:
```bash
# Windows PowerShell
Copy-Item app_database.db -Destination "backup_$(Get-Date -Format 'yyyyMMdd_HHmmss').db"
```

### 5️⃣ Atualizações de Segurança

Mantenha as dependências atualizadas:
```bash
pip install --upgrade Flask Flask-Login Flask-Bcrypt python-dotenv
```

### 6️⃣ Monitoramento

- Revise periodicamente os usuários cadastrados
- Verifique tentativas de login suspeitas
- Mude a senha do admin a cada 3-6 meses

### 7️⃣ Primeira Execução

1. Copie `.env.example` para `.env`
2. Edite o `.env` com suas configurações
3. Gere uma SECRET_KEY segura
4. Defina uma senha forte para o admin
5. Execute `python app.py`

---

## 🆘 Em Caso de Problema

Se suspeitar de comprometimento de segurança:

1. **Pare o servidor imediatamente** (Ctrl+C no terminal)
2. **Mude a SECRET_KEY** no arquivo `.env`
3. **Troque a senha do admin**
4. **Delete o arquivo `app_database.db`** para resetar tudo
5. **Execute novamente** `python app.py`

---

## 📞 Contato

Para dúvidas sobre segurança, consulte a documentação oficial:
- Flask: https://flask.palletsprojects.com/en/latest/security/
- Flask-Login: https://flask-login.readthedocs.io/
