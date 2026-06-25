"""Migrações leves para colunas adicionadas depois da primeira versão do schema.

O projeto não usa Alembic/Flask-Migrate; `db.create_all()` cria tabelas que
ainda não existem, mas não altera tabelas já existentes num banco que já tem
dados (ex: a instância em produção). Este módulo cobre esse caso específico
para colunas novas em tabelas antigas - tabelas novas não precisam disso,
`create_all()` já cuida delas.
"""

from datetime import datetime

from sqlalchemy import inspect, text


def _parse_db_datetime(value):
    """Valores lidos via SQL textual (`text(...)`) não passam pelo
    result-processor do tipo `DateTime` do SQLAlchemy - vêm como a string
    crua salva no SQLite, não como `datetime`. Sem isso, atribuir esse valor
    direto numa coluna `db.DateTime` no INSERT seguinte (via ORM) quebra com
    `TypeError: SQLite DateTime type only accepts Python datetime and date
    objects as input.`
    """
    if value is None or isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value)

# (tabela, coluna, definição de tipo/default usada no ADD COLUMN)
_NEW_COLUMNS = [
    ("room", "min_attendees", "INTEGER"),
    ("room", "business_hours_start", "TIME"),
    ("room", "business_hours_end", "TIME"),
    ("room", "floor_id", "INTEGER"),
    ("booking", "attendees_count", "INTEGER DEFAULT 1"),
    ("booking", "virtual_room_url", "VARCHAR(500)"),
    ("user", "avatar_filename", "VARCHAR(255)"),
    ("user", "pin_encrypted", "VARCHAR(255)"),
    ("site_branding_settings", "icon_filename", "VARCHAR(255)"),
    ("display_layout_settings", "agenda_position", "VARCHAR(20) DEFAULT 'below_status'"),
    ("display_layout_settings", "button_position", "VARCHAR(20) DEFAULT 'status_banner'"),
    ("display_layout_settings", "logo_filename", "VARCHAR(255)"),
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


def ensure_default_floor(db):
    """Backfill do conceito de Andares/Unidade (ver BACKLOG.md item 5).

    Antes só existia uma planta global (`FloorMap`, tabela `floor_map`,
    removida do model). Na primeira vez que o app sobe com este código, cria
    uma `Unit`/`Floor` padrão, migra a imagem da antiga planta global (se
    existir) pra esse andar, e aponta toda sala sem `floor_id` pra ele - sem
    isso, salas antigas ficariam sem andar e não apareceriam em nenhum mapa.
    Roda em todo startup, mas só age de verdade na primeira vez (idempotente:
    sai cedo se já existir alguma `Unit`).
    """
    from app.models import Floor, Room, Unit

    if Unit.query.count() > 0:
        return

    inspector = inspect(db.engine)
    old_map_row = None
    if "floor_map" in inspector.get_table_names():
        with db.engine.begin() as conn:
            old_map_row = conn.execute(
                text(
                    "SELECT filename, original_filename, uploaded_by, uploaded_at "
                    "FROM floor_map LIMIT 1"
                )
            ).first()

    unit = Unit(name="Unidade Principal")
    db.session.add(unit)
    db.session.flush()

    floor = Floor(
        unit_id=unit.id,
        name="Andar 1",
        filename=old_map_row.filename if old_map_row else None,
        original_filename=old_map_row.original_filename if old_map_row else None,
        uploaded_by=old_map_row.uploaded_by if old_map_row else None,
        uploaded_at=_parse_db_datetime(old_map_row.uploaded_at) if old_map_row else None,
    )
    db.session.add(floor)
    db.session.flush()

    Room.query.filter(Room.floor_id.is_(None)).update({Room.floor_id: floor.id})
    db.session.commit()
