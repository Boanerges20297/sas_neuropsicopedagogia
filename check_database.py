import sqlite3

DB_PATH = 'app_database.db'

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

print("=" * 60)
print("VERIFICANDO DADOS NO BANCO")
print("=" * 60)

# Verificar categorias
cursor.execute('SELECT COUNT(*) FROM test_categories')
cat_count = cursor.fetchone()[0]
print(f"\n✓ Categorias: {cat_count}")

if cat_count > 0:
    cursor.execute('SELECT id, nome, cor FROM test_categories LIMIT 5')
    for row in cursor.fetchall():
        print(f"  - ID {row[0]}: {row[1]} ({row[2]})")

# Verificar testes
cursor.execute('SELECT COUNT(*) FROM tests')
test_count = cursor.fetchone()[0]
print(f"\n✓ Testes: {test_count}")

if test_count > 0:
    cursor.execute('''
        SELECT t.id, t.titulo, t.ativo, tc.nome as categoria
        FROM tests t
        LEFT JOIN test_categories tc ON t.category_id = tc.id
    ''')
    for row in cursor.fetchall():
        status = "ATIVO" if row[2] else "INATIVO"
        print(f"  - ID {row[0]}: {row[1]} ({row[3]}) - {status}")
        
        # Contar questões deste teste
        cursor.execute('SELECT COUNT(*) FROM questions WHERE test_id = ?', (row[0],))
        q_count = cursor.fetchone()[0]
        print(f"    └─ {q_count} questões")

# Verificar questões
cursor.execute('SELECT COUNT(*) FROM questions')
q_count = cursor.fetchone()[0]
print(f"\n✓ Questões: {q_count}")

# Verificar respostas
cursor.execute('SELECT COUNT(*) FROM responses')
r_count = cursor.fetchone()[0]
print(f"\n✓ Respostas: {r_count}")

conn.close()

print("\n" + "=" * 60)
print("VERIFICAÇÃO CONCLUÍDA")
print("=" * 60)
