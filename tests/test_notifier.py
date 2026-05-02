"""
tests/test_notifier.py — Tests for core/notifier.py

Run with: python -m pytest tests/test_notifier.py -v
"""
from __future__ import annotations

import os
from unittest.mock import MagicMock, patch


# ── Helpers ───────────────────────────────────────────────────────────────────

def _set_telegram_env(token="test_token_123", chat_id="12345678"):
    """Set fake Telegram env vars for testing."""
    os.environ["TELEGRAM_BOT_TOKEN"] = token
    os.environ["TELEGRAM_CHAT_ID"] = chat_id


def _clear_telegram_env():
    os.environ.pop("TELEGRAM_BOT_TOKEN", None)
    os.environ.pop("TELEGRAM_CHAT_ID", None)


# ── is_configured ─────────────────────────────────────────────────────────────

def test_is_configured_returns_false_when_no_env():
    _clear_telegram_env()
    # Patch st.secrets to raise (no Streamlit context)
    with patch("streamlit.secrets", side_effect=Exception("no streamlit")):
        from core import notifier
        # Force reload of config
        with patch.object(notifier, "_get_config", return_value=("", "")):
            assert notifier.is_configured() is False


def test_is_configured_returns_true_when_env_set():
    _set_telegram_env()
    from core import notifier
    with patch.object(notifier, "_get_config", return_value=("test_token_123", "12345678")):
        assert notifier.is_configured() is True
    _clear_telegram_env()


# ── send_message ──────────────────────────────────────────────────────────────

def test_send_message_returns_false_when_not_configured():
    from core import notifier
    with patch.object(notifier, "_get_config", return_value=("", "")):
        result = notifier.send_message("hello")
    assert result is False


def test_send_message_calls_telegram_api():
    from core import notifier
    mock_response = MagicMock()
    mock_response.ok = True

    with patch.object(notifier, "_get_config", return_value=("fake_token", "12345")):
        with patch("requests.post", return_value=mock_response) as mock_post:
            result = notifier.send_message("Test message")

    assert result is True
    mock_post.assert_called_once()
    call_url = mock_post.call_args[0][0]
    assert "fake_token" in call_url
    assert "sendMessage" in call_url


def test_send_message_returns_false_on_request_failure():
    from core import notifier
    with patch.object(notifier, "_get_config", return_value=("fake_token", "12345")):
        with patch("requests.post", side_effect=Exception("connection error")):
            result = notifier.send_message("Test")
    assert result is False


# ── send_signal_alert ─────────────────────────────────────────────────────────

def test_send_signal_alert_formats_message():
    from core import notifier

    signal = {
        "symbol": "TESTCO",
        "company": "Test Company Ltd",
        "signal_type": "BUY",
        "entry_price": 100.0,
        "sl_price": 90.0,
        "t1": 110.0,
        "t2": 120.0,
        "t3": 130.0,
        "quantity": 100,
        "account_id": "acc_test",
        "notes": "Fresh breakout above 2-week high",
    }

    with patch.object(notifier, "_get_config", return_value=("fake_token", "12345")):
        with patch.object(notifier, "send_message", return_value=True) as mock_send:
            result = notifier.send_signal_alert(signal, source="Test")

    assert result is True
    mock_send.assert_called_once()
    message_text = mock_send.call_args[0][0]
    assert "TESTCO" in message_text
    assert "BUY" in message_text
    assert "100" in message_text  # entry price


# ── send_order_placed_alert ───────────────────────────────────────────────────

def test_send_order_placed_alert():
    from core import notifier

    with patch.object(notifier, "_get_config", return_value=("fake_token", "12345")):
        with patch.object(notifier, "send_message", return_value=True) as mock_send:
            result = notifier.send_order_placed_alert(
                symbol="TESTCO",
                order_id="ORD123",
                order_type="LIMIT",
                quantity=100,
                price=100.0,
                gtt_id=456,
            )

    assert result is True
    message_text = mock_send.call_args[0][0]
    assert "TESTCO" in message_text
    assert "ORD123" in message_text
