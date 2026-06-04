#!/bin/bash
# Post-edit hook: auto-formats Python files after Claude writes/edits them.
# Runs silently — does not block on failure.

FILE=$(python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('tool_input',{}).get('file_path',''))" 2>/dev/null || true)

if [[ "$FILE" == *.py ]]; then
  # Auto-format with autopep8 if available
  if command -v autopep8 &>/dev/null; then
    autopep8 --in-place --max-line-length 100 "$FILE" 2>/dev/null
  fi
fi

exit 0
