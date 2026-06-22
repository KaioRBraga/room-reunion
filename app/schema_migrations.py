"""Migrações leves para colunas adicionadas depois da primeira versão do schema.

O projeto não usa Alembic/Flask-Migrate; `db.create_all()` cria tabelas que
ainda não existem, mas não altera tabelas já existentes num banco que já tem
dados (ex: a instância em produção). Este módulo cobre esse caso específico
para colunas novas em tabelas antigas - tabelas novas não precisam disso,
`create_all()` já cuida delas.
"""

from sqlalchemy import inspect, text

# (tabela, coluna, definição de tipo/default usada no ADD COLUMN)
_NEW_COLUMNS = [
    ("room", "min_attendees", "INTEGER"),
    ("room", "business_hours_start", "TIME"),
    ("room", "business_hours_end", "TIME"),
    ("booking", "attendees_count", "INTEGER DEFAULT 1"),
    ("booking", "virtual_room_url", "VARCHAR(500)"),
    ("user", "avatar_filename", "VARCHAR(255)"),
    ("user", "pin_encrypted", "VARCHAR(255)"),
]


def ensure_columns(db):
    inspector = inspect(db.engine)
    existing_tables = set(inspector.get_table_names())

    with db.engine.begin() as conn:
        for table, column, ddl_type in _NEW_COLUMNS:
            if table not in existing_tables:
                continue
            columns = {c["name"] for c in inspector.get_columns(table)}
            if column in columns:
                continue
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl_type}"))
