"""
tests/conftest.py — Shared pytest fixtures and configuration.
"""
import os

# Force SQLite mode for all tests — never hit real Supabase or Kite
os.environ["DATABASE_MODE"] = "sqlite"
os.environ["DATA_SOURCE"] = "yfinance"
