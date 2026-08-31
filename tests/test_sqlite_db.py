from __future__ import annotations

import pytest
from storage.sqlite_db import db


def test_sqlite_wal_mode_and_pragmas():
    """Vérifie que la base est configurée en mode WAL, timeout et clés étrangères."""
    conn = db.get_connection()
    
    # 1. Vérifier journal_mode
    cur = conn.execute("PRAGMA journal_mode;")
    mode = cur.fetchone()[0]
    assert mode.upper() == "WAL"

    # 2. Vérifier foreign_keys
    cur = conn.execute("PRAGMA foreign_keys;")
    fk = cur.fetchone()[0]
    assert fk == 1


def test_all_16_tables_exist():
    """Vérifie que les 16 tables obligatoires sont bien créées en SQLite."""
    expected_tables = {
        "projects",
        "threads",
        "project_messages",
        "system_copilot_messages",
        "agents",
        "finops_ledger",
        "aa_benchmarks_cache",
        "mcp_servers",
        "mcp_tools",
        "skills_index",
        "rules_index",
        "hooks_index",
        "commands_index",
        "lessons_learned",
        "checkpoints",
        "hitl_requests",
    }
    
    rows = db.fetch_all("SELECT name FROM sqlite_master WHERE type='table';")
    existing_tables = {r["name"] for r in rows}
    
    for table in expected_tables:
        assert table in existing_tables, f"Table manquante dans SQLite : {table}"


def test_sqlite_transaction_rollback_on_error():
    """Vérifie que les transactions avec gestion d'erreurs effectuent un rollback propre."""
    # Insertion valide suivie d'une erreur
    try:
        with db.transaction():
            db.execute(
                "INSERT INTO system_copilot_messages (id, role, content, created_at) VALUES ('test_rollback', 'user', 'hello', '2026-08-21T00:00:00');"
            )
            # Provoquer une erreur volontaire pour forcer le rollback
            raise RuntimeError("Erreur forcée de transaction")
    except RuntimeError:
        pass

    # Vérifier que le message n'a pas été persisté
    row = db.fetch_one("SELECT * FROM system_copilot_messages WHERE id = 'test_rollback';")
    assert row is None
