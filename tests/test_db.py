"""
tests/test_db.py — Tests for core/db.py (SQLite mode only)

Run with: python -m pytest tests/test_db.py -v
"""
from __future__ import annotations

import os
import tempfile
import pytest

# Force SQLite mode for tests — never hit real Supabase
os.environ["DATABASE_MODE"] = "sqlite"


@pytest.fixture
def conn():
    """Create an in-memory SQLite DB for each test."""
    import importlib
    import core.db as db_module
    importlib.reload(db_module)  # reload so DATABASE_MODE env var is picked up
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    connection = db_module.init_db(db_path)
    yield connection
    connection.close()
    os.unlink(db_path)


# ── Account CRUD ──────────────────────────────────────────────────────────────

def test_upsert_and_get_account(conn):
    from core.db import upsert_account, get_account

    upsert_account(conn, {
        "id": "acc_test",
        "nickname": "Test Account",
        "kite_api_key": "enc_key_123",
        "kite_api_secret": "enc_secret_456",
        "kite_user_id": None,
        "access_token": None,
        "token_generated_at": None,
        "is_active": 1,
        "created_at": "2024-01-01T00:00:00",
    })

    account = get_account(conn, "acc_test")
    assert account is not None
    assert account["nickname"] == "Test Account"
    assert account["kite_api_key"] == "enc_key_123"


def test_get_account_returns_none_for_missing(conn):
    from core.db import get_account
    assert get_account(conn, "nonexistent") is None


def test_get_all_accounts_returns_active_only(conn):
    from core.db import upsert_account, get_all_accounts, delete_account

    upsert_account(conn, {
        "id": "acc_active", "nickname": "Active", "kite_api_key": "k",
        "kite_api_secret": "s", "kite_user_id": None, "access_token": None,
        "token_generated_at": None, "is_active": 1, "created_at": "2024-01-01T00:00:00",
    })
    upsert_account(conn, {
        "id": "acc_deleted", "nickname": "Deleted", "kite_api_key": "k",
        "kite_api_secret": "s", "kite_user_id": None, "access_token": None,
        "token_generated_at": None, "is_active": 1, "created_at": "2024-01-01T00:00:00",
    })

    delete_account(conn, "acc_deleted")

    accounts = get_all_accounts(conn)
    ids = [a["id"] for a in accounts]
    assert "acc_active" in ids
    assert "acc_deleted" not in ids


def test_update_account_token(conn):
    from core.db import upsert_account, update_account_token, get_account

    upsert_account(conn, {
        "id": "acc_token", "nickname": "Token Test", "kite_api_key": "k",
        "kite_api_secret": "s", "kite_user_id": None, "access_token": None,
        "token_generated_at": None, "is_active": 1, "created_at": "2024-01-01T00:00:00",
    })

    update_account_token(conn, "acc_token", "new_access_token_xyz", "KE1234")

    account = get_account(conn, "acc_token")
    assert account["access_token"] == "new_access_token_xyz"
    assert account["kite_user_id"] == "KE1234"


# ── Signal CRUD ───────────────────────────────────────────────────────────────

def test_insert_and_get_pending_signals(conn):
    from core.db import insert_signal, get_pending_signals
    import uuid

    signal = {
        "id": str(uuid.uuid4()),
        "strategy_id": "AI_AGENT",
        "account_id": "acc_test",
        "symbol": "TESTCO",
        "company": "Test Company",
        "signal_type": "BUY",
        "entry_price": 100.0,
        "sl_price": 90.0,
        "t1": 110.0,
        "t2": 120.0,
        "t3": 130.0,
        "quantity": 100,
        "generated_at": "2024-01-01T10:00:00",
        "status": "PENDING",
        "order_id": None,
        "notes": "Test signal",
    }

    insert_signal(conn, signal)
    pending = get_pending_signals(conn)
    symbols = [s["symbol"] for s in pending]
    assert "TESTCO" in symbols


def test_update_signal_status(conn):
    from core.db import insert_signal, update_signal_status, get_pending_signals
    import uuid

    sig_id = str(uuid.uuid4())
    signal = {
        "id": sig_id, "strategy_id": "AI_AGENT", "account_id": "acc_test",
        "symbol": "STATUSTEST", "company": "Status Test Co",
        "signal_type": "BUY", "entry_price": 50.0, "sl_price": 45.0,
        "t1": 55.0, "t2": 60.0, "t3": 65.0, "quantity": 50,
        "generated_at": "2024-01-01T10:00:00", "status": "PENDING",
        "order_id": None, "notes": "",
    }
    insert_signal(conn, signal)
    update_signal_status(conn, sig_id, "EXECUTED", "ORD999")

    # Should not appear in pending anymore
    pending = get_pending_signals(conn)
    pending_ids = [s["id"] for s in pending]
    assert sig_id not in pending_ids
