"""Explicit SQLite schema versions.

create_all builds a new database. This module adds columns that create_all
does not add to a database created by an older process. It does not delete
tables or rows.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import text

SCHEMA_VERSION = 2

# table -> (column, SQL type clause)
PHASE2_COLUMNS = {
    "simulation_runs": (
        ("mode", "VARCHAR(32) DEFAULT 'synthetic'"),
        ("mobility_source", "VARCHAR(80) DEFAULT 'synthetic'"),
        ("noise_source", "VARCHAR(80) DEFAULT 'synthetic'"),
        ("user_count", "INTEGER DEFAULT 0"),
    ),
    "mobility_datasets": (("storage_uri", "VARCHAR(255) DEFAULT ''"),),
    "noise_datasets": (("storage_uri", "VARCHAR(255) DEFAULT ''"),),
}


def _existing_columns(connection, table: str) -> set[str]:
    rows = connection.execute(text(f"PRAGMA table_info({table})")).fetchall()
    return {row[1] for row in rows}


def migrate(engine) -> int:
    if not str(engine.url).startswith("sqlite"):
        return SCHEMA_VERSION
    with engine.begin() as connection:
        connection.execute(
            text("CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)")
        )
        present = {int(row[0]) for row in connection.execute(text("SELECT version FROM schema_migrations")).fetchall()}
        if SCHEMA_VERSION in present:
            return SCHEMA_VERSION
        for table, columns in PHASE2_COLUMNS.items():
            have = _existing_columns(connection, table)
            if not have:
                continue
            for name, ddl in columns:
                if name not in have:
                    connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))
        connection.execute(
            text("INSERT INTO schema_migrations(version, applied_at) VALUES (:version, :applied)"),
            {"version": SCHEMA_VERSION, "applied": datetime.now(timezone.utc).isoformat()},
        )
    return SCHEMA_VERSION
