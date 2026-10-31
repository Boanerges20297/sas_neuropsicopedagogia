"""Additive, repeatable SQLite schema setup for dynamic assessments."""

SCHEMA_STATEMENTS = (
    """CREATE TABLE IF NOT EXISTS test_categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        descricao TEXT DEFAULT '',
        cor TEXT DEFAULT '#315b61',
        icone TEXT DEFAULT '',
        ativo INTEGER NOT NULL DEFAULT 1,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )""",
    """CREATE TABLE IF NOT EXISTS tests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category_id INTEGER NOT NULL,
        titulo TEXT NOT NULL,
        descricao TEXT DEFAULT '',
        instrucoes TEXT DEFAULT '',
        tempo_estimado INTEGER DEFAULT 30,
        pontuacao_maxima INTEGER NOT NULL DEFAULT 0,
        criado_por INTEGER,
        ativo INTEGER NOT NULL DEFAULT 1,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (category_id) REFERENCES test_categories(id),
        FOREIGN KEY (criado_por) REFERENCES users(id)
    )""",
    """CREATE TABLE IF NOT EXISTS questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        test_id INTEGER NOT NULL,
        ordem INTEGER NOT NULL,
        tipo TEXT NOT NULL DEFAULT 'text',
        enunciado TEXT NOT NULL,
        opcoes TEXT DEFAULT '',
        ativa INTEGER NOT NULL DEFAULT 1,
        pontos INTEGER NOT NULL DEFAULT 1,
        obrigatoria INTEGER NOT NULL DEFAULT 0,
        FOREIGN KEY (test_id) REFERENCES tests(id)
    )""",
    """CREATE TABLE IF NOT EXISTS question_responses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        response_id INTEGER NOT NULL,
        question_id INTEGER NOT NULL,
        resposta TEXT NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (response_id) REFERENCES responses(id),
        FOREIGN KEY (question_id) REFERENCES questions(id)
    )""",
)

# The dynamic test endpoint uses additional fields on the legacy response table.
RESPONSE_COLUMNS = {
    "test_id": "INTEGER",
    "nome_pessoa": "TEXT",
    "idade": "TEXT",
    "email_pessoa": "TEXT",
    "telefone_pessoa": "TEXT",
    "submission_date": "DATETIME",
    "campo_1": "TEXT",
}


def ensure_dynamic_test_schema(connection):
    """Add missing structures without rewriting or dropping existing data.

    The caller owns the transaction, including commit and rollback.
    """
    cursor = connection.cursor()
    for statement in SCHEMA_STATEMENTS:
        cursor.execute(statement)

    existing = {
        row[1].lower()
        for row in cursor.execute("PRAGMA table_info(responses)").fetchall()
    }
    user_columns = {row[1].lower() for row in cursor.execute("PRAGMA table_info(users)")}
    if "must_change_password" not in user_columns:
        cursor.execute("ALTER TABLE users ADD COLUMN must_change_password INTEGER NOT NULL DEFAULT 0")

    for name, sql_type in RESPONSE_COLUMNS.items():
        if name.lower() not in existing:
            cursor.execute(f"ALTER TABLE responses ADD COLUMN {name} {sql_type}")
