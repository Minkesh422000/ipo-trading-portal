---
name: fix-issue
argument-hint: [issue-number or bug description]
---

Fix GitHub issue #$ARGUMENTS or the described bug:

1. If a number: `gh issue view $ARGUMENTS` — read the full issue
2. Search relevant files using graphify-out/GRAPH_REPORT.md as the map
3. Identify root cause — no guessing, trace the actual code path
4. Implement the minimal fix — touch only what's necessary
5. Verify fix: run `python ipo_alert.py` with sample data or write a targeted test
6. Commit: `git commit -m "fix: <description> (closes #$ARGUMENTS)"`
