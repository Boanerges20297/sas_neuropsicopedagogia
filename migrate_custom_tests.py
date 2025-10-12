# Migração Completa - Sistema de Testes Cognitivos Personalizados
import sqlite3
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

DB_PATH = 'app_database.db'

def migrate_to_custom_tests():
    """
    Migra o sistema para suportar testes cognitivos personalizados
    """
    if not os.path.exists(DB_PATH):
        print("❌ Banco de dados não encontrado!")
        return
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        print("🔄 Iniciando migração para sistema de testes personalizados...\n")
        
        # 1. Tabela de Categorias de Testes
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS test_categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome VARCHAR(100) NOT NULL UNIQUE,
                descricao TEXT,
                cor VARCHAR(7) DEFAULT '#315b61',
                icone VARCHAR(10) DEFAULT '📋',
                ativo BOOLEAN DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        print("✅ Tabela test_categories criada")
        
        # 2. Tabela de Testes Personalizados
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category_id INTEGER NOT NULL,
                titulo VARCHAR(200) NOT NULL,
                descricao TEXT,
                instrucoes TEXT,
                tempo_estimado INTEGER,
                pontuacao_maxima INTEGER DEFAULT 0,
                ativo BOOLEAN DEFAULT 1,
                criado_por INTEGER,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (category_id) REFERENCES test_categories(id),
                FOREIGN KEY (criado_por) REFERENCES users(id)
            )
        ''')
        print("✅ Tabela tests criada")
        
        # 3. Tabela de Questões
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                test_id INTEGER NOT NULL,
                ordem INTEGER NOT NULL,
                tipo VARCHAR(50) DEFAULT 'text',
                enunciado TEXT NOT NULL,
                opcoes TEXT,
                resposta_esperada TEXT,
                pontos INTEGER DEFAULT 1,
                obrigatoria BOOLEAN DEFAULT 1,
                ativa BOOLEAN DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (test_id) REFERENCES tests(id) ON DELETE CASCADE
            )
        ''')
        print("✅ Tabela questions criada")
        
        # 4. Atualizar tabela responses para referenciar tests
        cursor.execute("PRAGMA table_info(responses)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'test_id' not in columns:
            cursor.execute('''
                ALTER TABLE responses ADD COLUMN test_id INTEGER REFERENCES tests(id)
            ''')
            print("✅ Coluna test_id adicionada à tabela responses")
        
        # 5. Tabela de Respostas por Questão
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS question_responses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                response_id INTEGER NOT NULL,
                question_id INTEGER NOT NULL,
                resposta TEXT,
                pontos_obtidos INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (response_id) REFERENCES responses(id) ON DELETE CASCADE,
                FOREIGN KEY (question_id) REFERENCES questions(id)
            )
        ''')
        print("✅ Tabela question_responses criada")
        
        # 6. Tabela de PDFs temporários
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS temp_pdf_uploads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename VARCHAR(255) NOT NULL,
                filepath VARCHAR(500) NOT NULL,
                texto_extraido TEXT,
                uploaded_by INTEGER NOT NULL,
                uploaded_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                expires_at DATETIME,
                FOREIGN KEY (uploaded_by) REFERENCES users(id)
            )
        ''')
        print("✅ Tabela temp_pdf_uploads criada")
        
        # 7. Inserir categorias padrão
        categorias_padrao = [
            ('Altas Habilidades/Superdotação', 'Avaliação de características de AH/SD', '#667eea', '🌟'),
            ('TDAH', 'Transtorno de Déficit de Atenção e Hiperatividade', '#f093fb', '🎯'),
            ('Dislexia', 'Avaliação de dificuldades de leitura e escrita', '#4facfe', '📖'),
            ('Memória', 'Testes de memória e retenção', '#43e97b', '🧠'),
            ('Atenção e Concentração', 'Avaliação de capacidade atentiva', '#fa709a', '👁️'),
            ('Funções Executivas', 'Planejamento, organização e flexibilidade cognitiva', '#fee140', '⚡'),
            ('Linguagem', 'Compreensão e expressão linguística', '#30cfd0', '💬'),
            ('Raciocínio Lógico', 'Pensamento analítico e resolução de problemas', '#a8edea', '🧩')
        ]
        
        for nome, desc, cor, icone in categorias_padrao:
            cursor.execute('''
                INSERT OR IGNORE INTO test_categories (nome, descricao, cor, icone)
                VALUES (?, ?, ?, ?)
            ''', (nome, desc, cor, icone))
        
        print("✅ Categorias padrão inseridas")
        
        conn.commit()
        print("\n✅ Migração concluída com sucesso!")
        print("\n📊 Estrutura criada:")
        print("   • test_categories - Categorias de testes cognitivos")
        print("   • tests - Testes personalizados")
        print("   • questions - Questões dos testes")
        print("   • question_responses - Respostas por questão")
        print("   • temp_pdf_uploads - Upload temporário de PDFs")
        
    except Exception as e:
        print(f"\n❌ Erro na migração: {e}")
        conn.rollback()
        import traceback
        traceback.print_exc()
    finally:
        conn.close()

if __name__ == '__main__':
    migrate_to_custom_tests()
