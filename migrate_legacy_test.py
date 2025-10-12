import sqlite3
from datetime import datetime

DB_PATH = 'app_database.db'

# Campos do teste legado (do FIELDS em app.py)
LEGACY_FIELDS = [
    ('nome_completo', 'Nome Completo'),
    ('data_nascimento', 'Data de Nascimento'),
    ('idade', 'Idade'),
    ('escolaridade', 'Escolaridade'),
    ('nome_escola', 'Nome da Escola'),
    ('turma', 'Turma'),
    ('turno', 'Turno'),
    ('nome_responsavel', 'Nome do Responsável'),
    ('parentesco', 'Parentesco'),
    ('telefone', 'Telefone'),
    ('email', 'E-mail'),
    ('motivo_avaliacao', 'Motivo da Avaliação'),
]

# Perguntas específicas do teste
LEGACY_QUESTIONS = [
    ('text', 'A criança possui facilidade para aprender novos conteúdos?', '', 1),
    ('text', 'Demonstra curiosidade intensa e faz perguntas elaboradas?', '', 1),
    ('text', 'Apresenta vocabulário avançado para a idade?', '', 1),
    ('text', 'Tem facilidade em áreas específicas (matemática, leitura, artes)?', '', 1),
    ('text', 'Demonstra criatividade e originalidade em suas produções?', '', 1),
    ('text', 'Possui boa memória e capacidade de concentração?', '', 1),
    ('text', 'Apresenta sensibilidade emocional aguçada?', '', 1),
    ('text', 'Tem interesse por temas complexos ou incomuns para a idade?', '', 1),
    ('text', 'Demonstra liderança natural entre os colegas?', '', 1),
    ('text', 'Prefere companhia de crianças mais velhas ou adultos?', '', 1),
    ('textarea', 'Descreva comportamentos ou situações que indicam possíveis altas habilidades:', '', 2),
    ('textarea', 'A criança apresenta alguma dificuldade de aprendizagem ou comportamental?', '', 2),
    ('textarea', 'Observações adicionais (histórico escolar, hobbies, interesses especiais):', '', 2),
]

def migrate_legacy_test():
    """Migra o teste legado de Altas Habilidades para o novo sistema"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        print("\n" + "="*60)
        print("MIGRANDO TESTE LEGADO DE ALTAS HABILIDADES")
        print("="*60)
        
        # Verificar se já existe
        cursor.execute("SELECT id FROM tests WHERE titulo = 'Avaliação de Altas Habilidades (Legado)'")
        if cursor.fetchone():
            print("\n⚠️  Teste legado já migrado anteriormente!")
            
            # Perguntar se quer recriar
            resp = input("\nDeseja recriar o teste? (s/n): ").lower()
            if resp != 's':
                print("\n✓ Migração cancelada.")
                return
            
            # Deletar teste existente
            cursor.execute("DELETE FROM questions WHERE test_id IN (SELECT id FROM tests WHERE titulo = 'Avaliação de Altas Habilidades (Legado)')")
            cursor.execute("DELETE FROM tests WHERE titulo = 'Avaliação de Altas Habilidades (Legado)'")
            print("\n✓ Teste antigo removido.")
        
        # Buscar categoria de Altas Habilidades
        cursor.execute("SELECT id FROM test_categories WHERE nome LIKE '%Altas Habilidades%'")
        category = cursor.fetchone()
        
        if not category:
            print("\n❌ Categoria 'Altas Habilidades' não encontrada!")
            return
        
        category_id = category[0]
        
        # Criar teste
        cursor.execute('''
            INSERT INTO tests (
                category_id, titulo, descricao, instrucoes, 
                tempo_estimado, pontuacao_maxima, ativo, criado_por, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            category_id,
            'Avaliação de Altas Habilidades/Superdotação',
            'Avaliação inicial para identificação de indicadores de altas habilidades e superdotação em crianças e adolescentes.',
            '''Este formulário deve ser preenchido por pais, responsáveis ou professores que conhecem bem a criança/adolescente.

INSTRUÇÕES IMPORTANTES:
- Responda com honestidade e baseado em observações concretas
- Não há respostas certas ou erradas
- Considere o comportamento habitual, não situações isoladas
- Seja o mais específico possível nas respostas descritivas
- O tempo estimado é de 15-20 minutos''',
            20,
            15,  # Total de questões
            1,   # Ativo
            1,   # Criado pelo admin (assumindo ID 1)
            datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        ))
        
        test_id = cursor.lastrowid
        print(f"\n✓ Teste criado com ID: {test_id}")
        
        # Adicionar questões
        ordem = 1
        
        # Questões sim/não (10 primeiras)
        for i, (tipo, enunciado, opcoes, pontos) in enumerate(LEGACY_QUESTIONS[:10], 1):
            cursor.execute('''
                INSERT INTO questions (
                    test_id, ordem, tipo, enunciado, opcoes, 
                    resposta_esperada, pontos, obrigatoria, ativa
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                test_id, ordem, 'yes_no', enunciado, 'Sim,Não',
                '', pontos, 1, 1
            ))
            ordem += 1
        
        # Questões descritivas (3 últimas)
        for tipo, enunciado, opcoes, pontos in LEGACY_QUESTIONS[10:]:
            cursor.execute('''
                INSERT INTO questions (
                    test_id, ordem, tipo, enunciado, opcoes, 
                    resposta_esperada, pontos, obrigatoria, ativa
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                test_id, ordem, tipo, enunciado, '',
                '', pontos, 1, 1
            ))
            ordem += 1
        
        conn.commit()
        
        print(f"✓ {ordem - 1} questões adicionadas")
        print("\n" + "="*60)
        print("✅ MIGRAÇÃO CONCLUÍDA COM SUCESSO!")
        print("="*60)
        print(f"\nO teste '{cursor.execute('SELECT titulo FROM tests WHERE id = ?', (test_id,)).fetchone()[0]}'")
        print(f"está disponível em: /teste/{test_id}")
        print(f"\nAgora você pode:")
        print(f"  1. Ver o teste no Dashboard")
        print(f"  2. Editar questões em: Gerenciar Testes")
        print(f"  3. Responder o teste na página inicial pública")
        
    except Exception as e:
        conn.rollback()
        print(f"\n❌ ERRO na migração: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()

if __name__ == '__main__':
    migrate_legacy_test()
