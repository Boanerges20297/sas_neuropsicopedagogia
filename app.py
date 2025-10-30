from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_bcrypt import Bcrypt
from functools import wraps
import sqlite3
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

# Carrega variáveis de ambiente do arquivo .env
load_dotenv()

APP_ROOT = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(APP_ROOT, os.getenv('DATABASE_NAME', 'app_database.db'))

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'chave-padrao-insegura-mude-isso')
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'  # type: ignore
login_manager.login_message = 'Por favor, faça login para acessar esta página.'
login_manager.login_message_category = 'info'

# ==================== DEFINIÇÃO DOS CAMPOS DO QUESTIONÁRIO ====================
FIELDS = [
    ("nome", "Nome"),
    ("idade_anos", "Idade (anos)"),
    ("idade_meses", "Idade (meses)"),
    ("data_nascimento", "Data de Nascimento"),
    ("sexo", "Sexo"),
    ("naturalidade", "Naturalidade"),
    ("endereco", "Endereço Residencial"),
    ("fones", "Fone(s)"),
    ("celular", "Celular"),
    ("cep", "CEP"),
    ("unidade_escolar", "Unidade Escolar de origem"),
    ("serie", "Série"),
    ("turma", "Turma"),
    ("turno", "Turno"),
    ("nome_pai", "Nome do Pai"),
    ("grau_instrucao_pai", "Grau de Instrução (Pai)"),
    ("profissao_pai", "Profissão (Pai)"),
    ("local_trabalho_pai", "Local de trabalho (Pai)"),
    ("fone_pai", "Fone (Pai)"),
    ("nome_mae", "Nome da Mãe"),
    ("grau_instrucao_mae", "Grau de Instrução (Mãe)"),
    ("profissao_mae", "Profissão (Mãe)"),
    ("local_trabalho_mae", "Local de trabalho (Mãe)"),
    ("fone_mae", "Fone (Mãe)"),
    ("outro_responsavel", "Outro responsável"),
    ("fone_outro_responsavel", "Fone(s) Outro responsável"),
    ("celular_outro_responsavel", "Celular Outro responsável"),
    ("email_outro_responsavel", "E-mail Outro responsável"),
    ("genograma", "Genograma"),
    ("quantas_pessoas", "Quantas pessoas moram em sua casa"),
    ("parentesco_idades", "Parentesco e idade das pessoas"),
    ("mae_problema_gestacao", "Mãe teve problema durante a gestação"),
    ("mae_problema_gestacao_desc", "Descreva problema na gestação"),
    ("parto_tipo", "Parto (normal/cesárea)"),
    ("parto_problema", "Houve algum problema durante ou após o parto"),
    ("parto_problema_desc", "Descreva problema no parto"),
    ("sono_bebe_bem", "Quando bebê, dormia bem"),
    ("sono_atual", "Atualmente, como é o sono"),
    ("andou_anos", "Começou a andar (anos)"),
    ("andou_meses", "Começou a andar (meses)"),
    ("falou_anos", "Começou a falar (anos)"),
    ("falou_meses", "Começou a falar (meses)"),
    ("frases_completas_idade_anos", "Frases completas com (anos)"),
    ("frases_completas_idade_meses", "Frases completas com (meses)"),
    ("problema_saude_primeiros_anos", "Teve problema de saúde nos primeiros anos"),
    ("problema_saude_qual", "Qual problema de saúde"),
    ("ingresso_escola_anos", "Ingresso na escola (anos)"),
    ("ingresso_escola_meses", "Ingresso na escola (meses)"),
    ("antes_saber_ler_escrever", "Antes de ingressar já sabia ler/escrever"),
    ("antes_saber_especifique", "Especifique se sabia ler/escrever"),
    ("leitura_comecou_anos", "Começou a ler (anos)"),
    ("leitura_comecou_meses", "Começou a ler (meses)"),
    ("escrita_comecou_anos", "Começou a escrever (anos)"),
    ("escrita_comecou_meses", "Começou a escrever (meses)"),
    ("calculo_comecou_anos", "Começou a fazer cálculos (anos)"),
    ("calculo_comecou_meses", "Começou a fazer cálculos (meses)"),
    ("comparacao_faixa_etaria", "Comparação com estudantes da mesma faixa etária"),
    ("faz_deveres", "Geralmente faz seus deveres"),
    ("quem_ajuda_tarefas", "Quem ajuda nas tarefas escolares"),
    ("disciplinas_facilidade", "Disciplinas com mais facilidade"),
    ("disciplinas_dificuldade", "Disciplinas com mais dificuldade"),
    ("demonstra_habilidade_em", "Demonstra habilidade em"),
    ("assunto_interesse", "Assunto que tem mais interesse"),
    ("gosta_de_ler", "Gosta de ler"),
    ("tipo_leitura", "Qual tipo de leitura"),
    ("opiniao_sobre_escola", "Opinião sobre a escola"),
    ("opiniao_por_que", "Por que"),
    ("o_que_acha_professores", "O que acha dos professores"),
    ("o_que_professores_falam", "O que os professores falam"),
    ("o_que_pensa_colegas", "O que pensa dos colegas"),
    ("participou_concursos", "Já participou de concursos na escola"),
    ("foi_premiado", "Foi premiado"),
    ("participou_concursos_especifique", "Especifique concurso/premiação"),
    ("foi_acelerado", "Já foi acelerado alguma vez"),
    ("para_qual_serie", "Para qual série foi acelerado"),
    ("ja_reprovou", "Já reprovou alguma vez"),
    ("em_quais_series_reprovou", "Em quais série(s) reprovou"),
    ("tem_muitos_amigos", "Tem muitos amigos"),
    ("gosta_de_ficar", "Gosta de ficar (sozinho/em grupo/sempre companhia)"),
    ("relacionamento_familia", "Como é o relacionamento com os familiares"),
    ("pratica_esporte", "Pratica algum esporte"),
    ("qual_esporte", "Qual esporte"),
    ("frequencia_esporte", "Frequência do esporte"),
    ("vai_a_cultura", "Vai a teatros/cinemas/museus"),
    ("frequencia_cultura", "Frequência de atividades culturais"),
    ("tem_religiao", "Tem alguma religião"),
    ("qual_religiao", "Qual religião"),
    ("vai_igreja", "Vai à Igreja"),
    ("frequencia_igreja", "Frequência de ida à Igreja"),
    ("participa_extraescolar", "Participa de atividade extraescolar"),
    ("extraescolar_especifique", "Especifique atividade extraescolar"),
    ("horas_lazer_gosta", "Nas horas de lazer, o que mais gosta de fazer"),
    ("houve_mudanca_significativa", "Houve mudança significativa no desenvolvimento"),
    ("mudanca_especifique", "Especifique mudança significativa"),
    ("familia_atividade_comum", "Família realiza atividade em comum"),
    ("familia_atividade_especifique", "Especifique atividade em comum"),
    ("familia_atividade_frequencia", "Frequência da atividade em comum"),
    ("descricao_biopsicossocial", "Descrição biopsicossocial"),
    ("caracteristicas_marcantes", "Características marcantes na personalidade"),
    ("observed_characteristics", "Características observadas (checkboxes)"),
    ("medicacao_controlada", "Toma medicação controlada"),
    ("acompanhamento", "Faz acompanhamento médico/psicológico/psicopedagógico"),
    ("observacoes", "Observações"),
    ("bairro_data", "Data (Brasília)"),
    ("assinatura_psicologo", "Carimbo/Assinatura do Psicólogo")
]

CHECKBOX_OPTIONS = [
    "Facilidade em processar informações, integrar experiências e emitir respostas apropriadas",
    "Aprendizagem rápida/fácil e com pouca repetição",
    "Pensador crítico; lida com problemas abstratos/complexos",
    "Boa memória e facilidade para acumular conhecimento",
    "Habilidade de raciocínio lógico-matemático",
    "Vocabulário avançado para a idade; verbalmente fluente",
    "Capacidade de generalizar e transferir aprendizagem",
    "Percepções incomuns na resolução de problemas",
    "Facilidade e agilidade para produzir ideias",
    "Flexibilidade ou facilidade para pensar fora dos padrões",
    "Originalidade de pensamento",
    "Capacidade de resolver problemas de forma criativa e efetiva",
    "Abertura a novas experiências e disposição para correr riscos",
    "Vê relações entre ideias diversas",
    "Independência e autonomia de pensamento",
    "Apurado senso de humor",
    "Interesse constante por certos tópicos",
    "Tendência a iniciar suas próprias atividades",
    "Persistência na realização de tarefas de interesse",
    "Auto-imposição para atingir a perfeição",
    "Ocupa seu tempo de forma produtiva",
    "Concentra-se por período prolongado sem aborrecer-se",
    "Preferência por responsabilidade pessoal sobre sua produção",
    "Obstinação em procurar informações sobre tópicos de interesse"
]

# ==================== MODELO DE USUÁRIO ====================
class User(UserMixin):
    def __init__(self, id, email, nome, role, data_nascimento=None, escolaridade=None, telefone=None):
        self.id = id
        self.email = email
        self.nome = nome
        self.role = role  # 'admin' ou 'user'
        self.data_nascimento = data_nascimento
        self.escolaridade = escolaridade
        self.telefone = telefone
    
    def is_admin(self):
        return self.role == 'admin'

@login_manager.user_loader
def load_user(user_id):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
    user_data = cursor.fetchone()
    conn.close()
    
    if user_data:
        return User(
            id=user_data['id'],
            email=user_data['email'],
            nome=user_data['nome'],
            role=user_data['role'],
            data_nascimento=user_data['data_nascimento'],
            escolaridade=user_data['escolaridade'],
            telefone=user_data['telefone']
        )
    return None

# ==================== DECORADOR ADMIN ====================
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin():
            flash('Você precisa ser administrador para acessar esta página.', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

# ==================== INICIALIZAÇÃO DO BANCO DE DADOS ====================
def init_db():
    """Inicializa o banco de dados com todas as tabelas necessárias"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Tabela de usuários
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            senha_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            data_nascimento TEXT,
            escolaridade TEXT,
            telefone TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Tabela de tipos de teste
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS test_types (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            descricao TEXT
        )
    ''')
    
    # Insere tipo de teste padrão se não existir
    cursor.execute('SELECT COUNT(*) FROM test_types')
    if cursor.fetchone()[0] == 0:
        cursor.execute('''
            INSERT INTO test_types (nome, descricao)
            VALUES ('Altas Habilidades/Superdotação', 'Questionário para diagnóstico inicial de AH/SD')
        ''')
    
    # Tabela de respostas
    columns = ', '.join([f'{key} TEXT' for key, _ in FIELDS])
    cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS responses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            test_type_id INTEGER DEFAULT 1,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            score INTEGER DEFAULT 0,
            scored_by INTEGER,
            scored_at DATETIME,
            notes TEXT,
            {columns},
            FOREIGN KEY (test_type_id) REFERENCES test_types(id),
            FOREIGN KEY (scored_by) REFERENCES users(id)
        )
    ''')
    
    # Cria usuário admin padrão se não existir (usando variáveis de ambiente)
    admin_email = os.getenv('ADMIN_EMAIL', 'admin@admin.com')
    admin_password_plain = os.getenv('ADMIN_PASSWORD', 'admin123')
    admin_name = os.getenv('ADMIN_NAME', 'Administrador')
    
    cursor.execute('SELECT COUNT(*) FROM users WHERE email = ?', (admin_email,))
    if cursor.fetchone()[0] == 0:
        admin_password = bcrypt.generate_password_hash(admin_password_plain).decode('utf-8')
        cursor.execute('''
            INSERT INTO users (nome, email, senha_hash, role)
            VALUES (?, ?, ?, ?)
        ''', (admin_name, admin_email, admin_password, 'admin'))
        print(f"✓ Usuário admin criado: {admin_email} / {admin_password_plain}")
        print("⚠ IMPORTANTE: Altere a senha padrão no arquivo .env!")
    
    conn.commit()
    conn.close()

# ==================== FUNÇÕES DE BANCO DE DADOS ====================
def save_response(data, test_type_id=1):
    """Salva uma resposta no banco de dados"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    columns = ', '.join(['test_type_id'] + [key for key, _ in FIELDS])
    placeholders = ', '.join(['?' for _ in range(len(FIELDS) + 1)])
    values = [test_type_id] + [data.get(key, '') for key, _ in FIELDS]
    
    cursor.execute(f'''
        INSERT INTO responses ({columns})
        VALUES ({placeholders})
    ''', values)
    
    conn.commit()
    conn.close()

def get_dashboard_stats():
    """Retorna estatísticas para o dashboard admin"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Total de respostas
    cursor.execute('SELECT COUNT(*) as count FROM responses')
    total_responses = cursor.fetchone()['count']
    
    # Respostas de hoje
    cursor.execute('''
        SELECT COUNT(*) as count FROM responses
        WHERE DATE(timestamp) = DATE('now')
    ''')
    new_today = cursor.fetchone()['count']
    
    # Total de usuários
    cursor.execute('SELECT COUNT(*) as count FROM users')
    total_users = cursor.fetchone()['count']
    
    # Contagem de admins
    cursor.execute("SELECT COUNT(*) as count FROM users WHERE role = 'admin'")
    admin_count = cursor.fetchone()['count']
    
    # Tipos de teste
    cursor.execute('SELECT id, nome, descricao FROM test_types')
    test_types = [dict(row) for row in cursor.fetchall()]
    
    # Respostas por tipo de teste
    cursor.execute('''
        SELECT tt.nome, COUNT(r.id) as count
        FROM test_types tt
        LEFT JOIN responses r ON tt.id = r.test_type_id
        GROUP BY tt.id, tt.nome
        ORDER BY count DESC
    ''')
    responses_by_type = cursor.fetchall()
    
    # Respostas dos últimos 7 dias (por dia)
    cursor.execute('''
        SELECT 
            DATE(timestamp) as date,
            COUNT(*) as count
        FROM responses
        WHERE DATE(timestamp) >= DATE('now', '-7 days')
        GROUP BY DATE(timestamp)
        ORDER BY date ASC
    ''')
    daily_data = cursor.fetchall()
    
    # Preencher dias faltantes com 0
    from datetime import datetime, timedelta
    daily_responses = []
    for i in range(7):
        date = (datetime.now() - timedelta(days=6-i)).strftime('%Y-%m-%d')
        count = 0
        for row in daily_data:
            if row['date'] == date:
                count = row['count']
                break
        day_label = (datetime.now() - timedelta(days=6-i)).strftime('%d/%m')
        daily_responses.append((day_label, count))
    
    # Última resposta
    cursor.execute('''
        SELECT timestamp FROM responses
        ORDER BY timestamp DESC
        LIMIT 1
    ''')
    last_row = cursor.fetchone()
    if last_row and last_row['timestamp']:
        try:
            last_dt = datetime.fromisoformat(last_row['timestamp'])
            last_response_date = last_dt.strftime('%d/%m/%Y')
            last_response_time = last_dt.strftime('%H:%M')
        except:
            last_response_date = 'N/A'
            last_response_time = ''
    else:
        last_response_date = 'Nenhuma'
        last_response_time = ''
    
    # Últimas 5 respostas para tabela
    cursor.execute('''
        SELECT 
            r.id,
            r.timestamp,
            tt.nome as test_type
        FROM responses r
        LEFT JOIN test_types tt ON r.test_type_id = tt.id
        ORDER BY r.timestamp DESC
        LIMIT 5
    ''')
    recent_responses_raw = cursor.fetchall()
    recent_responses = []
    for row in recent_responses_raw:
        try:
            timestamp = datetime.fromisoformat(row['timestamp']) if row['timestamp'] else None
        except:
            timestamp = None
        recent_responses.append({
            'id': row['id'],
            'timestamp': timestamp,
            'test_type': row['test_type'] or 'Desconhecido'
        })
    
    conn.close()
    
    return {
        'total_responses': total_responses,
        'new_today': new_today,
        'total_users': total_users,
        'admin_count': admin_count,
        'test_types': test_types,
        'responses_by_type': responses_by_type,
        'daily_responses': daily_responses,
        'last_response_date': last_response_date,
        'last_response_time': last_response_time,
        'recent_responses': recent_responses
    }

# ==================== ROTAS PÚBLICAS ====================
@app.route('/')
def index():
    """Página inicial - Login para não autenticados, Dashboard para autenticados"""
    # Se estiver autenticado, redireciona para dashboard
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    # Se não estiver autenticado, redireciona para login
    return redirect(url_for('login'))

@app.route('/select-test')
def select_test():
    """Página de seleção de testes disponíveis"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Buscar testes ativos com suas categorias
    cursor.execute('''
        SELECT t.*, tc.nome as categoria_nome, tc.cor as categoria_cor, tc.icone as categoria_icone,
               (SELECT COUNT(*) FROM questions WHERE test_id = t.id AND ativa = 1) as num_questoes
        FROM tests t
        LEFT JOIN test_categories tc ON t.category_id = tc.id
        WHERE t.ativo = 1
        ORDER BY tc.nome, t.titulo
    ''')
    tests = cursor.fetchall()
    
    conn.close()
    
    return render_template('select_test.html', tests=tests)

@app.route('/teste/<int:test_id>')
def take_test(test_id):
    """Responder teste específico"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Buscar teste
    cursor.execute('''
        SELECT t.*, tc.nome as categoria_nome, tc.icone as categoria_icone, tc.cor as categoria_cor
        FROM tests t
        LEFT JOIN test_categories tc ON t.category_id = tc.id
        WHERE t.id = ? AND t.ativo = 1
    ''', (test_id,))
    test = cursor.fetchone()
    
    if not test:
        flash('Teste não encontrado!', 'danger')
        return redirect(url_for('index'))
    
    # Buscar questões
    cursor.execute('''
        SELECT * FROM questions 
        WHERE test_id = ? AND ativa = 1 
        ORDER BY ordem
    ''', (test_id,))
    questions = cursor.fetchall()
    
    conn.close()
    
    if not questions:
        flash('Este teste ainda não possui questões!', 'warning')
        return redirect(url_for('index'))
    
    return render_template('take_test.html', test=test, questions=questions)

@app.route('/teste/legado')
def legacy_test():
    """Teste legado de Altas Habilidades (form.html antigo)"""
    return render_template('form.html', fields=FIELDS, checkbox_options=CHECKBOX_OPTIONS)

@app.route('/submit', methods=['POST'])
def submit():
    """Submissão do formulário público"""
    data = {}
    for key, _ in FIELDS:
        if key == 'observed_characteristics':
            vals = request.form.getlist('observed_characteristics')
            data[key] = ", ".join(vals)
        else:
            data[key] = request.form.get(key, '').strip()
    
    save_response(data)
    return render_template('thankyou.html')

@app.route('/teste/<int:test_id>/enviar', methods=['POST'])
def submit_test_response(test_id):
    """Submissão de respostas de teste dinâmico"""
    try:
        # Dados pessoais
        nome = request.form.get('nome', '').strip()
        idade = request.form.get('idade', '').strip()
        email = request.form.get('email', '').strip()
        telefone = request.form.get('telefone', '').strip()
        
        if not nome or not idade:
            flash('Nome e idade são obrigatórios!', 'danger')
            return redirect(url_for('take_test', test_id=test_id))
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Buscar nome do teste
        cursor.execute('SELECT titulo FROM tests WHERE id = ?', (test_id,))
        test = cursor.fetchone()
        
        if not test:
            flash('Teste não encontrado!', 'danger')
            return redirect(url_for('index'))
        
        # Criar entrada na tabela responses
        cursor.execute('''
            INSERT INTO responses (
                test_type_id, test_id, nome_pessoa, idade, email_pessoa, telefone_pessoa, 
                submission_date, campo_1
            ) VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
        ''', (1, test_id, nome, idade, email, telefone, f'Teste: {test[0]}'))
        
        response_id = cursor.lastrowid
        
        # Salvar respostas individuais
        cursor.execute('SELECT id, tipo FROM questions WHERE test_id = ? ORDER BY ordem', (test_id,))
        questions = cursor.fetchall()
        
        for question_id, question_type in questions:
            answer_value = request.form.get(f'question_{question_id}', '').strip()
            
            if answer_value:
                cursor.execute('''
                    INSERT INTO question_responses (response_id, question_id, resposta)
                    VALUES (?, ?, ?)
                ''', (response_id, question_id, answer_value))
        
        conn.commit()
        conn.close()
        
        return render_template('thankyou.html')
        
    except Exception as e:
        print(f"Erro ao salvar resposta: {e}")
        flash('Erro ao salvar suas respostas. Tente novamente.', 'danger')
        return redirect(url_for('take_test', test_id=test_id))

# ==================== ROTAS DE AUTENTICAÇÃO ====================
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard' if current_user.is_admin() else 'user_area'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        senha = request.form.get('senha')
        
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE email = ?', (email,))
        user_data = cursor.fetchone()
        conn.close()
        
        if user_data and bcrypt.check_password_hash(user_data['senha_hash'], senha):
            user = User(
                id=user_data['id'],
                email=user_data['email'],
                nome=user_data['nome'],
                role=user_data['role'],
                data_nascimento=user_data['data_nascimento'],
                escolaridade=user_data['escolaridade'],
                telefone=user_data['telefone']
            )
            # Converte o valor do checkbox para booleano
            remember_me = request.form.get('remember') == 'on'
            login_user(user, remember=remember_me)
            flash(f'Bem-vindo, {user.nome}!', 'success')
            
            next_page = request.args.get('next')
            if user.is_admin():
                return redirect(next_page or url_for('dashboard'))
            return redirect(next_page or url_for('user_area'))
        else:
            flash('Email ou senha incorretos.', 'danger')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard' if current_user.is_admin() else 'user_area'))
    
    if request.method == 'POST':
        nome = request.form.get('nome')
        email = request.form.get('email')
        senha = request.form.get('senha')
        data_nascimento = request.form.get('data_nascimento')
        escolaridade = request.form.get('escolaridade')
        telefone = request.form.get('telefone')
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Verifica se email já existe
        cursor.execute('SELECT id FROM users WHERE email = ?', (email,))
        if cursor.fetchone():
            flash('Este email já está cadastrado.', 'danger')
            conn.close()
            return redirect(url_for('register'))
        
        # Cria novo usuário
        senha_hash = bcrypt.generate_password_hash(senha).decode('utf-8')
        cursor.execute('''
            INSERT INTO users (nome, email, senha_hash, role, data_nascimento, escolaridade, telefone)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (nome, email, senha_hash, 'user', data_nascimento, escolaridade, telefone))
        
        conn.commit()
        conn.close()
        
        flash('Cadastro realizado com sucesso! Faça login para continuar.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Você saiu da sua conta.', 'info')
    return redirect(url_for('index'))

# ==================== ROTAS ADMINISTRATIVAS ====================
@app.route('/dashboard')
@login_required
@admin_required
def dashboard():
    """Dashboard administrativo com estatísticas"""
    stats = get_dashboard_stats()
    return render_template('dashboard.html', stats=stats)

@app.route('/admin/respostas')
@login_required
@admin_required
def admin_responses():
    """Lista todas as respostas"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT r.*, tt.nome as test_type
        FROM responses r
        LEFT JOIN test_types tt ON r.test_type_id = tt.id
        ORDER BY r.timestamp DESC
    ''')
    responses = cursor.fetchall()
    
    conn.close()
    
    return render_template('admin_responses.html', responses=responses, fields=FIELDS)

@app.route('/admin/resposta/<int:response_id>')
@login_required
@admin_required
def view_response(response_id):
    """Visualiza uma resposta específica"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT r.*, tt.nome as test_type
        FROM responses r
        LEFT JOIN test_types tt ON r.test_type_id = tt.id
        WHERE r.id = ?
    ''', (response_id,))
    response = cursor.fetchone()
    
    conn.close()
    
    if not response:
        flash('Resposta não encontrada.', 'danger')
        return redirect(url_for('admin_responses'))
    
    return render_template('view_response.html', response=response, fields=FIELDS)

@app.route('/admin/resposta/<int:response_id>/pontuar', methods=['POST'])
@login_required
@admin_required
def score_response(response_id):
    """Salva a pontuação de uma resposta"""
    try:
        data = request.get_json()
        score = data.get('score', 0)
        notes = data.get('notes', '')
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE responses 
            SET score = ?, notes = ?, scored_by = ?, scored_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (score, notes, current_user.id, response_id))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Pontuação salva com sucesso!'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/admin/usuarios')
@login_required
@admin_required
def admin_users():
    """Lista todos os usuários"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM users ORDER BY created_at DESC')
    users = cursor.fetchall()
    
    conn.close()
    
    return render_template('admin_users.html', users=users)

# ============================================
# GESTÃO DE TESTES COGNITIVOS PERSONALIZADOS
# ============================================

@app.route('/admin/categorias')
@login_required
@admin_required
def admin_categories():
    """Lista todas as categorias de testes"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM test_categories ORDER BY nome')
    categories = cursor.fetchall()
    
    conn.close()
    
    return render_template('admin_categories.html', categories=categories)

@app.route('/admin/categorias/adicionar', methods=['POST'])
@login_required
@admin_required
def add_category():
    """Adiciona nova categoria"""
    try:
        nome = request.form.get('nome')
        descricao = request.form.get('descricao', '')
        cor = request.form.get('cor', '#315b61')
        icone = request.form.get('icone', '📋')
        
        if not nome:
            return jsonify({'success': False, 'message': 'Nome é obrigatório'}), 400
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO test_categories (nome, descricao, cor, icone)
            VALUES (?, ?, ?, ?)
        ''', (nome, descricao, cor, icone))
        
        conn.commit()
        category_id = cursor.lastrowid
        conn.close()
        
        return jsonify({'success': True, 'message': 'Categoria adicionada!', 'id': category_id})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/admin/categorias/<int:category_id>')
@login_required
@admin_required
def get_category(category_id):
    """Busca dados de uma categoria"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM test_categories WHERE id = ?', (category_id,))
        category = cursor.fetchone()
        conn.close()
        
        if not category:
            return jsonify({'success': False, 'message': 'Categoria não encontrada'}), 404
        
        return jsonify({
            'success': True,
            'category': {
                'id': category['id'],
                'nome': category['nome'],
                'descricao': category['descricao'],
                'cor': category['cor'],
                'icone': category['icone'],
                'ativo': category['ativo']
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/admin/categorias/<int:category_id>/editar', methods=['POST'])
@login_required
@admin_required
def edit_category(category_id):
    """Edita uma categoria"""
    try:
        nome = request.form.get('nome')
        descricao = request.form.get('descricao', '')
        cor = request.form.get('cor', '#315b61')
        icone = request.form.get('icone', '📋')
        
        if not nome:
            return jsonify({'success': False, 'message': 'Nome é obrigatório'}), 400
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE test_categories 
            SET nome = ?, descricao = ?, cor = ?, icone = ?
            WHERE id = ?
        ''', (nome, descricao, cor, icone, category_id))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Categoria atualizada!'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/admin/categorias/<int:category_id>/excluir', methods=['POST'])
@login_required
@admin_required
def delete_category(category_id):
    """Exclui uma categoria"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Verificar se há testes usando esta categoria
        cursor.execute('SELECT COUNT(*) FROM tests WHERE category_id = ?', (category_id,))
        count = cursor.fetchone()[0]
        
        if count > 0:
            conn.close()
            return jsonify({
                'success': False, 
                'message': f'Não é possível excluir. Existem {count} teste(s) usando esta categoria.'
            }), 400
        
        cursor.execute('DELETE FROM test_categories WHERE id = ?', (category_id,))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Categoria excluída!'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/admin/categorias/<int:category_id>/status', methods=['POST'])
@login_required
@admin_required
def toggle_category_status(category_id):
    """Ativa/desativa uma categoria"""
    try:
        data = request.get_json()
        ativo = data.get('ativo', 1)
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('UPDATE test_categories SET ativo = ? WHERE id = ?', (ativo, category_id))
        conn.commit()
        conn.close()
        
        status_text = 'ativada' if ativo else 'desativada'
        return jsonify({'success': True, 'message': f'Categoria {status_text}!'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/admin/testes')
@login_required
@admin_required
def admin_tests():
    """Lista todos os testes personalizados"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT t.*, tc.nome as categoria_nome, tc.cor as categoria_cor,
               (SELECT COUNT(*) FROM questions WHERE test_id = t.id) as num_questoes
        FROM tests t
        LEFT JOIN test_categories tc ON t.category_id = tc.id
        ORDER BY t.created_at DESC
    ''')
    tests = cursor.fetchall()
    
    conn.close()
    
    return render_template('admin_tests.html', tests=tests)

@app.route('/admin/testes/novo')
@login_required
@admin_required
def new_test():
    """Formulário para criar novo teste"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM test_categories WHERE ativo = 1 ORDER BY nome')
    categories = cursor.fetchall()
    
    conn.close()
    
    return render_template('new_test.html', categories=categories)

@app.route('/admin/testes/criar', methods=['POST'])
@login_required
@admin_required
def create_test():
    """Cria novo teste"""
    try:
        category_id = request.form.get('category_id')
        titulo = request.form.get('titulo')
        descricao = request.form.get('descricao', '')
        instrucoes = request.form.get('instrucoes', '')
        tempo_estimado = request.form.get('tempo_estimado', 30)
        
        if not category_id or not titulo:
            flash('Categoria e título são obrigatórios!', 'danger')
            return redirect(url_for('new_test'))
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO tests (category_id, titulo, descricao, instrucoes, tempo_estimado, criado_por)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (category_id, titulo, descricao, instrucoes, tempo_estimado, current_user.id))
        
        test_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        flash('Teste criado com sucesso!', 'success')
        return redirect(url_for('edit_test_questions', test_id=test_id))
        
    except Exception as e:
        flash(f'Erro ao criar teste: {str(e)}', 'danger')
        return redirect(url_for('new_test'))

@app.route('/admin/testes/<int:test_id>/questoes')
@login_required
@admin_required
def edit_test_questions(test_id):
    """Editar questões do teste"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Buscar teste
    cursor.execute('''
        SELECT t.*, tc.nome as categoria_nome
        FROM tests t
        LEFT JOIN test_categories tc ON t.category_id = tc.id
        WHERE t.id = ?
    ''', (test_id,))
    test = cursor.fetchone()
    
    if not test:
        flash('Teste não encontrado!', 'danger')
        return redirect(url_for('admin_tests'))
    
    # Buscar questões
    cursor.execute('''
        SELECT * FROM questions 
        WHERE test_id = ? 
        ORDER BY ordem
    ''', (test_id,))
    questions = cursor.fetchall()
    
    conn.close()
    
    return render_template('edit_test_questions.html', test=test, questions=questions)

@app.route('/admin/testes/<int:test_id>/questoes/adicionar', methods=['POST'])
@login_required
@admin_required
def add_question():
    """Adiciona questão ao teste"""
    try:
        test_id = request.form.get('test_id')
        enunciado = request.form.get('enunciado')
        tipo = request.form.get('tipo', 'text')
        opcoes = request.form.get('opcoes', '')
        pontos = request.form.get('pontos', 1)
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Obter próxima ordem
        cursor.execute('SELECT MAX(ordem) FROM questions WHERE test_id = ?', (test_id,))
        max_ordem = cursor.fetchone()[0] or 0
        
        cursor.execute('''
            INSERT INTO questions (test_id, ordem, tipo, enunciado, opcoes, pontos)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (test_id, max_ordem + 1, tipo, enunciado, opcoes, pontos))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Questão adicionada!'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/admin/testes/<int:test_id>/questoes/<int:question_id>/editar', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_question(test_id, question_id):
    """Edita questão do teste"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    if request.method == 'GET':
        # Buscar dados da questão
        cursor.execute('SELECT * FROM questions WHERE id = ? AND test_id = ?', (question_id, test_id))
        question = cursor.fetchone()
        conn.close()
        
        if not question:
            return jsonify({'success': False, 'message': 'Questão não encontrada'}), 404
        
        return jsonify({
            'success': True,
            'question': {
                'id': question[0],
                'tipo': question[3],
                'enunciado': question[4],
                'opcoes': question[5] or '',
                'pontos': question[7],
                'obrigatoria': bool(question[8])
            }
        })
    
    # POST - Atualizar questão
    try:
        enunciado = request.form.get('enunciado')
        tipo = request.form.get('tipo', 'text')
        opcoes = request.form.get('opcoes', '')
        pontos = request.form.get('pontos', 1)
        obrigatoria = request.form.get('obrigatoria') == 'on'
        
        cursor.execute('''
            UPDATE questions 
            SET tipo = ?, enunciado = ?, opcoes = ?, pontos = ?, obrigatoria = ?
            WHERE id = ? AND test_id = ?
        ''', (tipo, enunciado, opcoes, pontos, obrigatoria, question_id, test_id))
        
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'Questão atualizada!'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/admin/testes/<int:test_id>/questoes/<int:question_id>/excluir', methods=['POST'])
@login_required
@admin_required
def delete_question(test_id, question_id):
    """Exclui questão do teste"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM questions WHERE id = ? AND test_id = ?', (question_id, test_id))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Questão excluída!'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# ==================== ROTAS DE USUÁRIO ====================
@app.route('/area-do-usuario')
@login_required
def user_area():
    """Área do usuário comum"""
    return render_template('user_area.html')

# ==================== INICIALIZAÇÃO ====================
if __name__ == '__main__':
    init_db()
    
    # Configurações de ambiente
    debug_mode = os.getenv('DEBUG_MODE', 'True').lower() == 'true'
    host = os.getenv('HOST', '127.0.0.1')
    port = int(os.getenv('PORT', 5000))
    
    print("\n" + "="*60)
    print("🚀 Servidor Flask Iniciado!")
    print("="*60)
    print(f"📍 URL: http://{host}:{port}/")
    print(f"🔧 Debug Mode: {debug_mode}")
    print(f"🔐 SECRET_KEY: {'Configurada via .env' if os.getenv('SECRET_KEY') else '⚠ Usando padrão (inseguro!)'}")
    print("="*60 + "\n")
    
    app.run(debug=debug_mode, host=host, port=port)
