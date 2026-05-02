"""
core/kite_manager.py — Multi-account Zerodha Kite connection pool.

Each Zerodha account has its own API key + secret (₹500/month each).
Access tokens expire daily at ~6:30 AM IST and must be renewed via OAuth.

This module manages:
- Storing multiple account credentials in the database
- Generating Kite OAuth login URLs per account
- Completing OAuth (request_token → access_token exchange)
- Checking token validity
- Returning live authenticated KiteConnect instances
- Fetching and caching portfolio data (holdings, positions, margins)
"""
from __future__ import annotations

import hashlib
import os
from datetime import date, datetime, timezone
from typing import Optional

# ── Encryption helpers (AES-256 via cryptography library) ─────────────────────
def _load_encryption_key() -> str:
    """Load ENCRYPTION_KEY from st.secrets first, then os.getenv fallback."""
    try:
        import streamlit as st
        return st.secrets.get("ENCRYPTION_KEY", "") or os.getenv("ENCRYPTION_KEY", "")
    except Exception:
        return os.getenv("ENCRYPTION_KEY", "")

_ENCRYPT_KEY = _load_encryption_key()


def _encrypt(plaintext: str) -> str:
    """Encrypt sensitive strings (API secrets). Falls back to plaintext if no key set."""
    if not _ENCRYPT_KEY or not plaintext:
        return plaintext
    try:
        from cryptography.fernet import Fernet
        import base64
        key = base64.urlsafe_b64encode(hashlib.sha256(_ENCRYPT_KEY.encode()).digest())
        return Fernet(key).encrypt(plaintext.encode()).decode()
    except Exception:
        return plaintext  # graceful fallback


def _decrypt(ciphertext: str) -> str:
    """Decrypt encrypted strings."""
    if not _ENCRYPT_KEY or not ciphertext:
        return ciphertext
    try:
        from cryptography.fernet import Fernet
        import base64
        key = base64.urlsafe_b64encode(hashlib.sha256(_ENCRYPT_KEY.encode()).digest())
        return Fernet(key).decrypt(ciphertext.encode()).decode()
    except Exception:
        return ciphertext  # return as-is if decryption fails


# ── Token validity ──────────────────────────────────────────────────────────────

def _token_expiry_today() -> datetime:
    """Kite tokens expire at 06:30 AM IST = 01:00 AM UTC of the same calendar date."""
    now_ist = datetime.now(timezone.utc).astimezone(
        __import__("zoneinfo", fromlist=["ZoneInfo"]).ZoneInfo("Asia/Kolkata")
        if hasattr(__import__("zoneinfo", fromlist=[""]), "ZoneInfo")
        else timezone.utc
    )
    # If current IST time < 06:30, expiry is 06:30 today; else it's 06:30 tomorrow
    cutoff = now_ist.replace(hour=6, minute=30, second=0, microsecond=0)
    return cutoff


class KiteManager:
    """Static helper methods — no instantiation needed."""

    @staticmethod
    def generate_login_url(api_key: str, redirect_url: str = "https://127.0.0.1") -> str:
        """Return the Kite OAuth URL the user must visit to log in."""
        try:
            from kiteconnect import KiteConnect
            kite = KiteConnect(api_key=api_key)
            return kite.login_url()
        except ImportError:
            # kiteconnect not installed — return manual URL
            return f"https://kite.trade/connect/login?api_key={api_key}&v=3"

    @staticmethod
    def complete_login(account_id: str, request_token: str, conn) -> tuple[bool, str]:
        """
        Exchange request_token for access_token and save to DB.
        Returns (success, error_message).
        """
        from core.db import get_account, update_account_token
        account = get_account(conn, account_id)
        if not account:
            return False, "Account not found"

        api_key = _decrypt(account["kite_api_key"])
        api_secret = _decrypt(account["kite_api_secret"])

        try:
            from kiteconnect import KiteConnect
            kite = KiteConnect(api_key=api_key)
            session = kite.generate_session(request_token, api_secret=api_secret)
            access_token = session["access_token"]
            user_id = session.get("user_id") or session.get("login_time", "")
            update_account_token(conn, account_id, access_token, user_id)
            return True, ""
        except ImportError:
            return False, "kiteconnect package not installed"
        except Exception as exc:
            return False, str(exc)

    @staticmethod
    def get_kite(account_id: str, conn) -> Optional["KiteConnect"]:
        """
        Return an authenticated KiteConnect instance, or None if token is invalid/expired.
        """
        from core.db import get_account
        account = get_account(conn, account_id)
        if not account or not account.get("access_token"):
            return None

        if not KiteManager.is_token_valid(account):
            return None

        try:
            from kiteconnect import KiteConnect
            api_key = _decrypt(account["kite_api_key"])
            kite = KiteConnect(api_key=api_key)
            kite.set_access_token(account["access_token"])
            return kite
        except ImportError:
            return None
        except Exception:
            return None

    @staticmethod
    def is_token_valid(account: dict) -> bool:
        """
        Kite access tokens expire daily.
        A token is valid if it was generated after today's 06:30 AM IST mark.
        """
        generated_at_str = account.get("token_generated_at")
        if not generated_at_str:
            return False
        try:
            generated_at = datetime.fromisoformat(generated_at_str.replace("Z", "+00:00"))
            # Make timezone-aware if naive (assume UTC)
            if generated_at.tzinfo is None:
                generated_at = generated_at.replace(tzinfo=timezone.utc)
            cutoff = _token_expiry_today()
            if cutoff.tzinfo is None:
                cutoff = cutoff.replace(tzinfo=timezone.utc)
            return generated_at > cutoff
        except (ValueError, AttributeError):
            return False

    @staticmethod
    def refresh_portfolio(account_id: str, conn) -> dict:
        """
        Fetch holdings, positions, and margins from Kite and save to DB.
        Returns {"holdings": [...], "positions": [...], "margins": {...}, "error": "..."}
        """
        from core.db import upsert_holdings, upsert_positions, upsert_margins

        kite = KiteManager.get_kite(account_id, conn)
        if kite is None:
            return {"holdings": [], "positions": [], "margins": {}, "error": "Token expired — please log in again"}

        result = {"holdings": [], "positions": [], "margins": {}, "error": None}

        try:
            raw_holdings = kite.holdings()
            holdings = [
                {
                    "symbol": h["tradingsymbol"],
                    "quantity": h["quantity"],
                    "average_price": h["average_price"],
                    "last_price": h["last_price"],
                    "pnl": h.get("pnl", 0.0),
                    "pnl_pct": (
                        ((h["last_price"] - h["average_price"]) / h["average_price"] * 100)
                        if h["average_price"] > 0 else 0.0
                    ),
                }
                for h in raw_holdings
                if h.get("quantity", 0) > 0
            ]
            upsert_holdings(conn, account_id, holdings)
            result["holdings"] = holdings
        except Exception as exc:
            result["error"] = f"Holdings fetch failed: {exc}"

        try:
            raw_positions = kite.positions()
            net = raw_positions.get("net", [])
            positions = [
                {
                    "symbol": p["tradingsymbol"],
                    "quantity": p["quantity"],
                    "average_price": p["average_price"],
                    "last_price": p["last_price"],
                    "pnl": p.get("pnl", 0.0),
                    "product": p.get("product", ""),
                }
                for p in net
                if p.get("quantity", 0) != 0
            ]
            upsert_positions(conn, account_id, positions)
            result["positions"] = positions
        except Exception as exc:
            result.setdefault("error", f"Positions fetch failed: {exc}")

        try:
            raw_margins = kite.margins()
            equity = raw_margins.get("equity", {})
            margins = {
                "available_cash": equity.get("available", {}).get("cash", 0.0),
                "used_margin": equity.get("utilised", {}).get("debits", 0.0),
                "total_balance": equity.get("net", 0.0),
            }
            upsert_margins(conn, account_id, margins)
            result["margins"] = margins
        except Exception as exc:
            result.setdefault("error", f"Margins fetch failed: {exc}")

        return result
