# 🎯 Sistema de Avaliação - Altas Habilidades/Superdotação

Sistema web completo para aplicação e gestão de questionários de diagnóstico inicial, com autenticação, níveis de usuário e dashboard administrativo.

## ✨ Novidades da Versão 2.0

### 🔐 Sistema de Autenticação Completo
- Login seguro com bcrypt
- Registro de novos usuários
- Sessões persistentes
- Recuperação de senha

### 👥 Níveis de Usuário
- **Administrador**: Acesso completo ao dashboard, visualização de respostas, gestão de usuários
- **Usuário Comum**: Acesso ao formulário e área pessoal

### 📊 Dashboard Administrativo
- Estatísticas em tempo real
- Gráficos interativos (Chart.js)
- Análise de respostas por tipo de teste
- Últimas submissões
- Métricas de desempenho

### 🎨 Design Moderno
- Interface adaptada às cores da logo institucional
- Layout responsivo e mobile-first
- Menu superior com dropdown
- Cards e seções bem organizadas
- Animações suaves

### 💾 Banco de Dados SQLite
- Armazenamento estruturado
- Relacionamentos entre tabelas
- Consultas otimizadas
- Backup automático

## 🚀 Instalação Rápida

### 1. Ativar ambiente virtual

```powershell
& ".\.venv\Scripts\Activate.ps1"
```

### 2. Instalar dependências

```powershell
pip install -r requirements.txt
```

### 3. Iniciar servidor

```powershell
python app.py
```

### 4. Acessar sistema

```
http://127.0.0.1:5000/
```

## 🔑 Acesso Padrão

### Administrador
- **Email**: admin@admin.com
- **Senha**: admin123

⚠️ **IMPORTANTE**: Altere a senha do administrador após o primeiro login!

## 📁 Estrutura do Projeto

```
Testes - Altas Habilidades/
├── app.py                          # Backend Flask com autenticação
├── app_database.db                 # Banco de dados SQLite
├── migrate.py                      # Script de migração
├── requirements.txt                # Dependências Python
├── README.md                       # Este arquivo
│
├── static/
│   ├── logo.jpg                    # Logo institucional
│   └── style.css                   # CSS moderno e responsivo
│
└── templates/
    ├── login.html                  # Tela de login
    ├── register.html               # Cadastro de usuários
    ├── dashboard.html              # Dashboard administrativo
    ├── admin_responses.html        # Lista de respostas
    ├── admin_users.html            # Gestão de usuários
    ├── view_response.html          # Detalhes de uma resposta
    ├── user_area.html              # Área do usuário
    ├── form.html                   # Formulário público
    └── thankyou.html               # Confirmação de envio
```

## 🎯 Funcionalidades

### Para Pacientes/Famílias (Sem Login Necessário)
- ✅ Preenchimento do questionário completo
- ✅ 105 campos organizados em 7 seções
- ✅ Validação automática
- ✅ Interface intuitiva e responsiva

### Para Usuários Cadastrados
- ✅ Área pessoal com dados do perfil
- ✅ Histórico de preenchimentos (futuro)
- ✅ Edição de dados pessoais (futuro)

### Para Administradores (Neuropsicopedagoga)
- ✅ Dashboard com estatísticas completas
- ✅ Visualização de todas as respostas
- ✅ Detalhes de cada questionário
- ✅ Gráficos e análises
- ✅ Exportação para Excel
- ✅ Gestão de usuários
- ✅ Controle de acesso

## 🎨 Paleta de Cores

Baseada na logo institucional:

- **Primary**: #8B5A3C (Marrom) 
- **Secondary**: #D4A574 (Dourado)
- **Accent**: #E8B892 (Bege)
- **Success**: #52A675 (Verde)
- **Background**: #F6F5F0 (Off-white)

## 📊 Banco de Dados

### Tabelas

#### `users`
- id, nome, email, senha_hash
- role (admin/user)
- data_nascimento, escolaridade, telefone
- created_at

#### `test_types`
- id, nome, descricao

#### `responses`
- id, test_type_id
- timestamp
- 105 campos do questionário

## 🔐 Segurança

- ✅ Senhas criptografadas com bcrypt
- ✅ Proteção CSRF automática do Flask
- ✅ Sessões seguras
- ✅ Decoradores de proteção de rotas
- ✅ Validação de permissões

## 🌐 Rotas da Aplicação

### Públicas
- `/` - Formulário público
- `/submit` - Submissão do formulário
- `/login` - Tela de login
- `/register` - Cadastro de usuários

### Protegidas (Login necessário)
- `/area-do-usuario` - Área do usuário
- `/logout` - Sair da conta

### Administrativas (Apenas admin)
- `/dashboard` - Dashboard principal
- `/admin/respostas` - Lista de respostas
- `/admin/resposta/<id>` - Detalhes de uma resposta
- `/admin/usuarios` - Gestão de usuários
- `/exportar` - Exportar para Excel

## 📱 Responsividade

O sistema é totalmente responsivo e funciona perfeitamente em:

- 💻 Desktop (1920px+)
- 💻 Laptop (1366px - 1920px)
- 📱 Tablet (768px - 1366px)
- 📱 Mobile (< 768px)

## 🛠️ Tecnologias Utilizadas

- **Backend**: Flask 2.0+
- **Autenticação**: Flask-Login + Flask-Bcrypt
- **Banco de Dados**: SQLite3
- **Frontend**: HTML5, CSS3, JavaScript
- **Gráficos**: Chart.js 4.4
- **Ícones**: Emojis Unicode

## 🚦 Próximos Passos

### Melhorias Futuras
- [ ] Histórico de questionários por usuário
- [ ] Filtros avançados no dashboard
- [ ] Exportação em PDF
- [ ] Relatórios personalizados
- [ ] Notificações por email
- [ ] API REST para integração
- [ ] Testes automatizados
- [ ] Deploy em produção

## 📝 Notas Importantes

### Mudança do Excel para SQLite
A aplicação agora usa SQLite em vez de Excel. Benefícios:
- ✅ Melhor performance
- ✅ Consultas mais rápidas
- ✅ Relacionamentos entre dados
- ✅ Backup mais fácil
- ✅ Concurrent access seguro

### Migração de Dados
Se você tinha dados no `responses.xlsx` anterior, eles foram preservados no backup.

## 🐛 Solução de Problemas

### Erro: "Flask-Login not found"
```powershell
pip install Flask-Login Flask-Bcrypt
```

### Erro: "Database is locked"
- Feche todas as conexões ao banco
- Reinicie o servidor

### Esqueci a senha do admin
Execute no Python:
```python
from flask_bcrypt import Bcrypt
bcrypt = Bcrypt()
print(bcrypt.generate_password_hash('nova_senha').decode('utf-8'))
```
Atualize manualmente no banco.

## 📞 Suporte

Para questões sobre o sistema ou o processo de identificação de Altas Habilidades/Superdotação, entre em contato com a Diretoria de Educação Inclusiva e Atendimentos Educacionais Especializados da SEEDF.

## 📄 Licença

Este projeto foi desenvolvido para uso educacional e assistencial no contexto do Atendimento Educacional Especializado da Secretaria de Estado de Educação do Distrito Federal.

---

**Desenvolvido com ❤️ para a SEEDF**
