# 🎯 Início Rápido - Questionário Altas Habilidades

## ▶️ Como Executar

1. **Abra o PowerShell** na pasta do projeto
2. **Ative o ambiente virtual:**
   ```powershell
   & ".venv\Scripts\Activate.ps1"
   ```
3. **Inicie o servidor:**
   ```powershell
   python app.py
   ```
4. **Abra o navegador** em: `http://127.0.0.1:5000/`

## 📋 O que foi criado

✅ **Formulário web completo** com design moderno e profissional
✅ **105 campos** - todas as perguntas do PDF original
✅ **7 seções organizadas** conforme o documento original
✅ **Validação automática** de campos obrigatórios
✅ **Salvamento em Excel** - arquivo `responses.xlsx` criado automaticamente
✅ **Interface responsiva** - funciona em desktop e mobile

## 🎨 Melhorias Visuais

- ✨ Design moderno com gradiente roxo
- 📱 Layout responsivo para mobile
- 🎯 Campos organizados por seção com cores
- ✅ Botões e checkboxes estilizados
- 📝 Textareas redimensionáveis
- 🌈 Efeitos de hover e foco

## 📊 Estrutura do Formulário

### I - Identificação do Estudante
- Dados pessoais completos
- Informações escolares
- Dados dos pais e responsáveis

### II - Dados da Família
- Genograma
- Composição familiar

### III - Dados do Desenvolvimento
- Gestação e parto
- Marcos do desenvolvimento
- Saúde nos primeiros anos

### IV - Vida Escolar
- Alfabetização e aprendizagem
- Desempenho acadêmico
- Relacionamento escolar
- Histórico de aceleração/reprovação

### V - Vida Social
- Amizades e relacionamentos
- Atividades esportivas e culturais
- Religião e lazer
- Dinâmica familiar

### VI - Descrição Biopsicossocial
- Características da personalidade
- 24 indicadores de altas habilidades

### VII - Informações Adicionais
- Medicações e acompanhamentos
- Observações gerais
- Assinatura do psicólogo

## 💾 Arquivo Excel

O arquivo `responses.xlsx` é criado automaticamente na primeira submissão e contém:
- **Cabeçalho** com todas as 105 perguntas em português
- **Uma linha por submissão** com todas as respostas
- **Formato editável** - pode ser aberto no Excel ou Google Sheets

## 🛠️ Arquivos do Projeto

```
├── app.py                     # Backend Flask
├── templates/
│   ├── form.html             # Formulário principal (design moderno)
│   └── thankyou.html         # Página de confirmação
├── static/
│   └── style.css             # Estilos CSS personalizados
├── responses.xlsx            # Respostas (gerado automaticamente)
├── requirements.txt          # Dependências Python
└── README.md                 # Documentação completa
```

## 🚀 Próximos Passos

Para usar em produção:
1. Configure um servidor WSGI (Waitress, Gunicorn)
2. Adicione HTTPS se for expor na internet
3. Implemente autenticação se necessário
4. Configure backup automático do Excel

## 📞 Suporte

Consulte o `README.md` para documentação completa e solução de problemas.
