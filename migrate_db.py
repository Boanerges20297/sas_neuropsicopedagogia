# Script de Migração - Adicionar campos de pontuação
import sqlite3
import os

DB_PATH = 'app_database.db'

def migrate_database():
    """Adiciona campos de pontuação à tabela responses"""
    if not os.path.exists(DB_PATH):
        print("❌ Banco de dados não encontrado!")
        return
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Verificar se as colunas já existem
        cursor.execute("PRAGMA table_info(responses)")
        columns = [column[1] for column in cursor.fetchall()]
        
        migrations = []
        
        if 'score' not in columns:
            migrations.append("ALTER TABLE responses ADD COLUMN score INTEGER DEFAULT 0")
        
        if 'scored_by' not in columns:
            migrations.append("ALTER TABLE responses ADD COLUMN scored_by INTEGER")
        
        if 'scored_at' not in columns:
            migrations.append("ALTER TABLE responses ADD COLUMN scored_at DATETIME")
        
        if 'notes' not in columns:
            migrations.append("ALTER TABLE responses ADD COLUMN notes TEXT")
        
        if migrations:
            print(f"🔄 Aplicando {len(migrations)} migração(ões)...")
            for migration in migrations:
                cursor.execute(migration)
                print(f"✅ {migration}")
            
            conn.commit()
            print("\n✅ Migração concluída com sucesso!")
        else:
            print("✅ Banco de dados já está atualizado!")
        
    except Exception as e:
        print(f"❌ Erro na migração: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == '__main__':
    migrate_database()
