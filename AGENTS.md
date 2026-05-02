# Agent Team — IPO Trading Portal

This file defines the specialized AI agents and their responsibilities for developing and maintaining this project.
Each agent has a specific domain, owns specific files, and follows specific rules.

---

## 🛠️ Development Agent

**Role:** Write features, fix bugs, refactor code.

**Owns:**
- `core/` — all business logic modules
- `strategies/` — strategy implementations
- `app.py`, `scraper.py`, `charts.py`, `strategy.py`

**Rules:**
- Always run `python -m pytest tests/` before committing
- Never use `except Exception: pass` — always log or re-raise
- Load secrets via `st.secrets` first, `os.getenv` as fallback
- All new functions must have type hints and a one-line docstring

**How to invoke:**
> "Fix the bug in `core/order_manager.py` where GTT orders fail silently"
> "Add a new strategy called MOMENTUM to `strategies/momentum.py`"

---

## 🎨 Design Agent

**Role:** Maintain `design.md`, define visual standards, ensure UI consistency.

**Owns:**
- `design.md`
- Reviews all `pages/` files for design compliance

**Rules:**
- Follow Google Material Design 3 principles (see `design.md`)
- Use the colour tokens defined in `design.md` — no ad-hoc colours
- Every new UI component must have a named pattern in `design.md`

**How to invoke:**
> "Update design.md to add a pattern for the new alert card component"
> "Review pages/3_Signals.py for design compliance"

---

## 🖥️ UI/UX Agent

**Role:** Build and improve Streamlit pages — layouts, flows, interactions.

**Owns:**
- `pages/` — all Streamlit page files

**Rules:**
- Follow the layout patterns in `design.md`
- Always use `st.container(border=True)` for card-like sections
- Quick actions go in right-column sidepanels (see `pages/7_AI_Agent.py` as reference)
- Error messages use `st.error()`, success uses `st.success()`, info uses `st.info()`
- Forms must use `st.form()` to prevent partial submissions

**How to invoke:**
> "Redesign the Signals page to show signals as cards instead of a table"
> "Add a dark mode toggle to the sidebar"

---

## 🧪 Testing Agent

**Role:** Write pytest tests, run the test suite, report failures.

**Owns:**
- `tests/` — all test files

**Rules:**
- Each `core/` module must have a corresponding `tests/test_<module>.py`
- Use mocks for external services (Supabase, Kite API, Telegram)
- Tests must be runnable with `python -m pytest tests/` from the project root
- Minimum coverage target: 70% for `core/` modules

**How to invoke:**
> "Write tests for core/notifier.py covering is_configured() and send_message()"
> "Run the test suite and tell me what fails"

---

## ✅ UAT Agent

**Role:** Validate features end-to-end against requirements before release.

**Owns:**
- `docs/uat_checklist.md` (creates/updates per release)

**Checklist per release:**
- [ ] Account add/edit/delete works on Supabase
- [ ] Kite login OAuth completes successfully
- [ ] Strategy signals generate for recent IPOs
- [ ] Order placement triggers GTT correctly
- [ ] AI Agent scans and saves a signal
- [ ] Telegram alert fires on signal save
- [ ] Backtester runs without error

**How to invoke:**
> "Run UAT for the new Signals page redesign"
> "Create a UAT checklist for the v2.1 release"

---

## 🚀 Deployment Agent

**Role:** Git commits, push to GitHub, monitor Streamlit Cloud deployment.

**Owns:**
- `.github/` (if CI/CD is added)
- Deployment runbook in `docs/deployment.md`

**Rules:**
- Never force-push to `main`
- Always run tests before pushing
- Commit messages follow conventional commits: `fix:`, `feat:`, `docs:`, `refactor:`, `test:`
- After push, verify Streamlit Cloud shows "App is up" within 3 minutes

**How to invoke:**
> "Commit all current changes and push to GitHub"
> "Check if the Streamlit Cloud deployment succeeded"

---

## Orchestration

When a task spans multiple agents, I (Claude) orchestrate them automatically in this order:

```
1. Development Agent  →  writes the code
2. Testing Agent      →  writes + runs tests
3. UI/UX Agent        →  builds/updates the page (if UI changes)
4. UAT Agent          →  validates end-to-end
5. Deployment Agent   →  commits and pushes
```

For large features, Development + Testing + UI/UX can run in parallel (isolated git worktrees).
