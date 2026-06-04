#!/bin/bash
# Pre-commit hook: runs before every git commit.
# Exit code 2 = BLOCK the commit. Exit code 0 = allow.

STAGED_PY=$(git diff --cached --name-only | grep "\.py$")

if [ -z "$STAGED_PY" ]; then
  exit 0  # No Python files staged — nothing to check
fi

echo "Running pre-commit checks on staged Python files..."

# 1. Syntax check
for f in $STAGED_PY; do
  python3 -m py_compile "$f" 2>&1
  if [ $? -ne 0 ]; then
    echo "BLOCKED: Syntax error in $f"
    exit 2
  fi
done

# 2. Check for hardcoded secrets (tokens, passwords, API keys)
if git diff --cached | grep -qE "(TOKEN|SECRET|PASSWORD|API_KEY)\s*=\s*['\"][a-zA-Z0-9_\-]{10,}['\"]"; then
  echo "BLOCKED: Possible hardcoded secret detected. Use environment variables instead."
  exit 2
fi

# 3. Check .streamlit/secrets.toml is not being committed
if git diff --cached --name-only | grep -q "secrets.toml"; then
  echo "BLOCKED: Never commit secrets.toml — contains credentials."
  exit 2
fi

echo "Pre-commit checks passed."
exit 0
