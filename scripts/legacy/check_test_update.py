import sqlite3

conn = sqlite3.connect('app_database.db')
cursor = conn.cursor()

# Verificar o teste
cursor.execute('''
    SELECT tests.id, tests.titulo, COUNT(questions.id) as num_questoes,
           tests.tempo_estimado, tests.pontuacao_maxima
    FROM tests 
    LEFT JOIN questions ON tests.id = questions.test_id
    WHERE tests.id = 1
    GROUP BY tests.id
''')

result = cursor.fetchone()

print("\n" + "="*70)
print("VERIFICAÇÃO DO TESTE ATUALIZADO")
print("="*70)
print(f"\n✓ Teste ID: {result[0]}")
print(f"✓ Título: {result[1]}")
print(f"✓ Total de Questões: {result[2]}")
print(f"✓ Tempo Estimado: {result[3]} minutos")
print(f"✓ Pontuação Máxima: {result[4]} pontos")

# Ver algumas questões
cursor.execute('''
    SELECT ordem, tipo, enunciado
    FROM questions
    WHERE test_id = 1
    ORDER BY ordem
    LIMIT 10
''')

print("\n" + "="*70)
print("PRIMEIRAS 10 QUESTÕES:")
print("="*70)

for row in cursor.fetchall():
    print(f"\n{row[0]}. [{row[1]}] {row[2][:60]}...")

conn.close()

print("\n" + "="*70)
