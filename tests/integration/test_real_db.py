"""
Migration smoke test — runs against a real PostgreSQL instance.

Verifies that Alembic migrations work correctly end-to-end:
  upgrade head  → expected tables exist
  downgrade base → all tables removed
  upgrade head  → idempotent, tables back

Requires DATABASE_URL env var pointing to PostgreSQL.
Skipped automatically in any other context.
"""

import os
import subprocess

import pytest
from sqlalchemy import create_engine, inspect

DATABASE_URL = os.environ.get("DATABASE_URL", "")

pytestmark = pytest.mark.skipif(
    "postgresql" not in DATABASE_URL,
    reason="Requires DATABASE_URL pointing to PostgreSQL",
)

EXPECTED_TABLES = {"trips", "users", "expenses", "memberships", "expense_splits"}


def _run_alembic(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["python", "-m", "alembic", *args],
        capture_output=True,
        text=True,
        env={**os.environ, "DATABASE_URL": DATABASE_URL},
    )


def _get_tables() -> set[str]:
    engine = create_engine(DATABASE_URL, future=True)
    try:
        with engine.connect():
            return set(inspect(engine).get_table_names())
    finally:
        engine.dispose()


def test_upgrade_creates_all_tables():
    result = _run_alembic("upgrade", "head")
    assert result.returncode == 0, f"alembic upgrade head failed:\n{result.stderr}"
    missing = EXPECTED_TABLES - _get_tables()
    assert not missing, f"Missing tables after upgrade: {missing}"


def test_downgrade_removes_all_tables():
    result = _run_alembic("downgrade", "base")
    assert result.returncode == 0, f"alembic downgrade base failed:\n{result.stderr}"
    remaining = EXPECTED_TABLES & _get_tables()
    assert not remaining, f"Tables still present after downgrade: {remaining}"


def test_upgrade_is_idempotent():
    """Running upgrade head twice must not raise."""
    for i in range(2):
        result = _run_alembic("upgrade", "head")
        assert (
            result.returncode == 0
        ), f"alembic upgrade head (run {i + 1}) failed:\n{result.stderr}"
    assert EXPECTED_TABLES.issubset(_get_tables())
