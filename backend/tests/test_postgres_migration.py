"""Compatibilité des migrations de démarrage avec PostgreSQL."""

from app.main import _portable_ddl


def test_portable_ddl_converts_boolean_defaults_for_postgresql():
    assert _portable_ddl("BOOLEAN DEFAULT 0", "postgresql") == "BOOLEAN DEFAULT FALSE"
    assert _portable_ddl("BOOLEAN DEFAULT 1", "postgresql") == "BOOLEAN DEFAULT TRUE"


def test_portable_ddl_keeps_sqlite_syntax():
    assert _portable_ddl("BOOLEAN DEFAULT 0", "sqlite") == "BOOLEAN DEFAULT 0"
    assert _portable_ddl("TIMESTAMP", "sqlite") == "TIMESTAMP"
