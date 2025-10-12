# Questionário Altas Habilidades - Formulário Interativo

Este projeto transforma o questionário em PDF do AEE-AH/SD (Atendimento Educacional Especializado ao Estudante com Altas Habilidades/Superdotação) em um formulário web interativo.

## 📋 Características

- **Formulário web completo** com todos os campos do PDF original
- **Validação automática** de campos obrigatórios
- **Armazenamento em Excel** - cria `responses.xlsx` automaticamente na primeira submissão
- **Interface intuitiva** - campos adaptados para melhor experiência (números, texto, seleção, checkboxes)
- **105 campos mapeados** - nenhuma pergunta foi omitida do formulário original

## 🚀 Instalação e Execução

### Pré-requisitos

- Python 3.7 ou superior
- Windows PowerShell

### Passo 1: Ativar o ambiente virtual

Abra o PowerShell na pasta do projeto e execute:

```powershell
& ".venv\Scripts\Activate.ps1"
```

Se você encontrar erro de política de execução, execute antes:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Passo 2: Instalar dependências (se necessário)

Se as dependências não estiverem instaladas:

```powershell
pip install -r requirements.txt
```

### Passo 3: Iniciar o servidor Flask

```powershell
python app.py
```

O servidor será iniciado em `http://127.0.0.1:5000/`

### Passo 4: Acessar o formulário

Abra seu navegador e acesse:

```
http://127.0.0.1:5000/
```

## 📝 Uso

1. **Preencha o formulário** com os dados do estudante
2. **Clique em "Enviar"** ao finalizar
3. **Verifique as respostas** no arquivo `responses.xlsx` criado na pasta do projeto

### Arquivo Excel

- **Criação automática**: O arquivo `responses.xlsx` é criado na primeira submissão
- **Adição de linhas**: Cada nova submissão adiciona uma linha ao arquivo
- **Cabeçalhos em português**: Todas as colunas têm rótulos descritivos
- **105 colunas**: Uma para cada campo do formulário

## 🗂️ Estrutura do Projeto

```
Testes - Altas Habilidades/
├── app.py                      # Aplicação Flask principal
├── templates/
│   ├── form.html              # Template do formulário
│   └── thankyou.html          # Página de agradecimento
├── requirements.txt           # Dependências Python
├── responses.xlsx             # Excel com respostas (criado automaticamente)
├── extract_pdf.py             # Script de extração do PDF
├── extracted_text.txt         # Texto extraído do PDF
└── README.md                  # Este arquivo
```

## 📊 Campos do Formulário

O formulário inclui todas as seções do PDF original:

### I - Identificação do Estudante
- Nome, idade, data de nascimento, sexo, naturalidade
- Endereço, telefones, CEP
- Unidade escolar, série, turma, turno
- Dados dos pais/responsáveis

### I - Dados da Família
- Genograma
- Composição familiar

### II - Dados do Desenvolvimento
- Gestação e parto
- Marcos do desenvolvimento (andar, falar)
- Sono e saúde

### III - Vida Escolar
- Ingresso na escola
- Alfabetização (leitura, escrita, cálculos)
- Desempenho acadêmico
- Relação com escola, professores e colegas
- Participação em concursos
- Histórico de aceleração/reprovação

### IV - Vida Social
- Amizades e relacionamentos
- Atividades esportivas e culturais
- Religião
- Atividades extraescolares
- Lazer e hobbies

### V - Descrição Biopsicossocial
- Características da personalidade
- **24 características de superdotação** (checkboxes)
  - Facilidades cognitivas
  - Criatividade
  - Comprometimento com tarefas

### VI - Informações Adicionais
- Medicações
- Acompanhamentos médicos/psicológicos
- Observações gerais

## 🔧 Personalização

### Modificar campos

Edite o arquivo `app.py` e atualize a lista `FIELDS` com os campos desejados.

### Alterar estilo

Edite o CSS inline em `templates/form.html` ou crie um arquivo CSS em `static/style.css`.

### Alterar porta

Modifique a última linha de `app.py`:

```python
app.run(debug=True, port=8080)  # Altere 8080 para a porta desejada
```

## ⚠️ Observações Importantes

- **Desenvolvimento**: O servidor Flask está configurado em modo de desenvolvimento (`debug=True`)
- **Produção**: Para uso em produção, considere usar um servidor WSGI como Gunicorn ou Waitress
- **Backup**: Faça backup regular do arquivo `responses.xlsx`
- **LGPD**: O questionário coleta dados sensíveis - garanta conformidade com a LGPD

## 🐛 Solução de Problemas

### Erro: "flask: comando não encontrado"

Execute com o Python do ambiente virtual:

```powershell
python app.py
```

### Erro: "Não é possível carregar o arquivo Activate.ps1"

Execute no PowerShell como administrador:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Porta já em uso

Altere a porta em `app.py` ou finalize o processo que está usando a porta 5000:

```powershell
Get-Process -Id (Get-NetTCPConnection -LocalPort 5000).OwningProcess | Stop-Process
```

## 📄 Licença

Este projeto foi desenvolvido para uso educacional e assistencial no contexto do Atendimento Educacional Especializado da Secretaria de Estado de Educação do Distrito Federal.

## 📞 Suporte

Para questões sobre o formulário original ou o processo de identificação de Altas Habilidades/Superdotação, entre em contato com a Diretoria de Educação Inclusiva e Atendimentos Educacionais Especializados da SEEDF.
