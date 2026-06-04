---
paths:
  - "**/*.py"
---

# Python Rules

- Python 3.11+, type hints on all function signatures
- No bare `except` — always catch specific exceptions
- No `print` for errors — use `print(f"[ERROR] ...")` format with module prefix
- Functions under 60 lines; split logic into well-named helpers
- Use `from __future__ import annotations` for forward references
- f-strings only — no `.format()` or `%` formatting
- Guard all env var reads with `_require_env()` or `os.getenv(name, default)`
- Never hardcode credentials, tokens, or API keys in source files
- Sort imports: stdlib → third-party → local (separated by blank lines)
