# Design System — IPO Trading Portal

Adapted from **Google Material Design 3** (M3) for Streamlit.
All UI decisions in `pages/` should reference this document.

---

## 1. Design Principles

### 1.1 Core Values (from M3)
| Principle | What it means for this app |
|-----------|---------------------------|
| **Personal** | Show account-specific data first, always. Default to the user's primary account. |
| **Adaptive** | Tables on wide screens, stacked cards on narrow. Use `layout="wide"`. |
| **Expressive** | Use colour to communicate state (green = profit/valid, red = loss/error, amber = warning). Never use colour alone — pair with an icon or label. |

### 1.2 Three-Layer Mental Model
Every page has three zones — do not mix them:
1. **Navigation** — Streamlit sidebar (account selector, global settings)
2. **Content** — Main area (`col_chat`, `col_main`) — data, charts, tables
3. **Actions** — Right column or bottom panel — buttons, forms, confirmations

---

## 2. Colour System

### 2.1 Semantic Colours (use these, not raw hex)
| Token | Streamlit element | Usage |
|-------|------------------|-------|
| `success` | `st.success()` | Trade executed, account saved, token valid |
| `error` | `st.error()` | Trade failed, token expired, required field missing |
| `warning` | `st.warning()` | Risk threshold approaching, GTT warning, unconfirmed action |
| `info` | `st.info()` | Live price, neutral status, hints |

### 2.2 Status Badge Colours (in markdown)
```python
# Token valid
st.markdown(":green[✅ Token valid]")

# Token expired  
st.markdown(":red[❌ Token expired]")

# Pending signal
st.markdown(":orange[⏳ Pending]")

# Executed
st.markdown(":green[✅ Executed]")

# Dismissed
st.markdown(":gray[✖ Dismissed]")
```

### 2.3 P&L Colouring
```python
# Always colour P&L values
color = "green" if pnl >= 0 else "red"
sign = "+" if pnl >= 0 else ""
st.markdown(f":{color}[{sign}₹{pnl:,.0f}]")
```

---

## 3. Typography

### 3.1 Hierarchy
| Level | Element | Used for |
|-------|---------|---------|
| H1 | `st.title()` | Page title — one per page only |
| H2 | `st.header()` | Major sections (e.g. "Connected Accounts") |
| H3 | `st.subheader()` | Sub-sections, card titles (e.g. account nickname) |
| Caption | `st.caption()` | Metadata, timestamps, helper text |
| Code | `` `backtick` `` in markdown | Account IDs, order IDs, symbols |

### 3.2 Number Formatting
```python
# Prices — always 2 decimal places with ₹ symbol
f"₹{price:,.2f}"        # ₹1,245.60

# Quantities — whole numbers with comma
f"{qty:,}"              # 1,500

# P&L — signed, coloured (see 2.3)
f"+₹{pnl:,.0f}"        # +₹12,450

# Percentages
f"{pct:.2f}%"           # 3.45%

# Large capital amounts
f"₹{capital/100000:.1f}L"   # ₹10.5L
```

---

## 4. Layout

### 4.1 Standard Page Template
```python
st.set_page_config(page_title="Page Name — IPO Portal", page_icon="🔥", layout="wide")
st.title("🔥 Page Title")
st.caption("One-sentence description of what this page does.")

# Sidebar: account selector + page-specific controls
with st.sidebar:
    st.header("⚙️ Settings")
    # ... controls

# Main content
col_main, col_actions = st.columns([3, 1])

with col_main:
    # Primary content: tables, charts, cards

with col_actions:
    st.subheader("⚡ Quick Actions")
    # Action buttons
```

### 4.2 Column Ratios
| Use case | Ratio |
|---------|-------|
| Content + actions panel | `[3, 1]` |
| Two equal data panels | `[1, 1]` |
| Form fields (label + input) | `[1, 2]` |
| Metric row (4 values) | `[1, 1, 1, 1]` |
| Account card header | `[3, 2, 1]` (name, status, action) |

### 4.3 Card Pattern
Use `st.container(border=True)` for any card-like section:
```python
with st.container(border=True):
    col1, col2, col3 = st.columns([3, 2, 1])
    col1.markdown("### Card Title")
    col1.caption("Subtitle or metadata")
    col2.markdown(":green[✅ Status]")
    if col3.button("Action", key="unique_key"):
        # handle action
```

---

## 5. Component Patterns

### 5.1 Metric Row (KPI Bar)
Use `st.metric()` for 4 key numbers at the top of a page:
```python
c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Capital", "₹10.5L", delta="+₹12,450")
c2.metric("Day P&L", "+₹3,200", delta="0.3%")
c3.metric("Pending Signals", "3")
c4.metric("Accounts Online", "2/3")
```
Rule: Metrics go at the top of the page, before any tables or content.

### 5.2 Data Tables
```python
st.dataframe(
    df,
    use_container_width=True,
    hide_index=True,
    column_config={
        "pnl": st.column_config.NumberColumn("P&L", format="₹%.0f"),
        "pnl_pct": st.column_config.NumberColumn("P&L %", format="%.2f%%"),
        "status": st.column_config.TextColumn("Status"),
    }
)
```
Rule: Always `use_container_width=True`. Never show the dataframe index.

### 5.3 Status Expander (for tool calls, logs)
```python
with st.status("Claude is thinking...", expanded=True) as status:
    # streaming updates
    status.update(label="Done ✓", state="complete", expanded=False)
```

### 5.4 Confirmation Pattern (before destructive actions)
```python
st.warning("⚠️ Clicking **Confirm** will place a live order. This cannot be undone.")
if st.button("✅ Confirm & Place Trade", type="primary", use_container_width=True):
    # place order
```
Rule: Always show a `st.warning()` before any irreversible action. Use `type="primary"` only on the final confirm button.

### 5.5 Form Pattern
```python
with st.form("form_id"):
    col1, col2 = st.columns(2)
    field1 = col1.text_input("Label", placeholder="hint")
    field2 = col2.text_input("Label 2")
    submitted = st.form_submit_button("💾 Save", type="primary")
    if submitted:
        if not all([field1, field2]):
            st.error("All fields are required.")
        else:
            try:
                # save logic
                st.success("✅ Saved.")
            except Exception as e:
                st.error(f"❌ Failed: {e}")
```
Rules:
- Always validate inside the form block
- Always wrap DB/API calls in try/except with `st.error()` on failure
- Use `type="primary"` on the submit button only

### 5.6 Trade Panel (inline after signal)
```python
with st.container(border=True):
    st.subheader(f"🛡️ Place Trade — {symbol}")
    
    # Order type selector
    order_type = st.radio("Order type", ["LIMIT", "MARKET"], horizontal=True)
    
    # Metrics row: SL + 3 targets
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("SL", f"₹{sl:,.2f}")
    c2.metric("T1", f"₹{t1:,.2f}")
    c3.metric("T2", f"₹{t2:,.2f}")
    c4.metric("T3", f"₹{t3:,.2f}")
    
    # Risk summary
    st.info(f"Risk: ₹{risk:,}  |  Max profit: ₹{reward:,}  |  R:R 1:{rr}")
    
    # Confirmation warning + button
    st.warning("⚠️ Clicking **Confirm** will place a live order via Kite.")
    if st.button("✅ Confirm & Place Trade", type="primary", use_container_width=True):
        # place order
```

---

## 6. Icons & Emoji System

Consistent icon use across all pages:

| Icon | Meaning |
|------|---------|
| 🏠 | Home / Dashboard |
| 👤 | Account / User |
| 💼 | Portfolio / Holdings |
| 📊 | Signals / Charts |
| 📋 | Orders / Lists |
| ⚙️ | Settings / Strategies |
| 📈 | Backtest / Performance |
| 🤖 | AI Agent |
| ✅ | Success / Confirmed / Valid |
| ❌ | Error / Failed / Expired |
| ⚠️ | Warning / Caution |
| 🔧 | Tool call / Technical |
| 🛡️ | Protected / Safe action |
| 🔄 | Refresh / Reload |
| 💾 | Save |
| 🗑️ | Delete / Remove |
| 🔐 | Login / Auth |
| 📡 | Live data / Real-time |
| ⚡ | Quick action |
| 💡 | Tip / Hint |
| ₹ | Indian Rupee (always use ₹, never Rs or INR in UI) |

---

## 7. Error Handling UX

### 7.1 Error Message Hierarchy
```
st.error()    → User action failed (form save, API call, order placement)
st.warning()  → User should be aware but can continue (token expires soon, GTT warning)
st.info()     → Neutral information (live price, empty state)
st.success()  → Positive outcome (saved, logged in, order placed)
```

### 7.2 Empty State Pattern
When a list/table has no data:
```python
if not items:
    st.info("No [items] yet. [Action to create first one].")
    st.stop()
```

### 7.3 API Error Pattern
```python
try:
    result = api_call()
    st.success("✅ Done.")
except SomeAPIError as e:
    st.error(f"❌ [Human-readable description]. Details: {e}")
except Exception as e:
    st.error(f"❌ Unexpected error: {e}")
```
Rule: Never let an unhandled exception crash a page. Every external call must have a try/except.

---

## 8. Responsiveness

Streamlit is always `layout="wide"`. Handle narrow screens:
```python
# For critical info on narrow screens, collapse to single column
if st.checkbox("Compact view"):
    cols = st.columns(1)
else:
    cols = st.columns([3, 1])
```
Rule: Don't rely on responsive CSS. Test at 1200px wide minimum.

---

## 9. Accessibility

- Every icon must be paired with text (never icon-only buttons)
- Colour is never the sole indicator of state (always add icon + label)
- `st.caption()` for all helper text — never rely on placeholder text alone
- Form labels must always be visible (use `label_visibility="visible"`)

---

## 10. Page Checklist

Before shipping any new page, verify:
- [ ] `st.set_page_config()` has page_title + page_icon
- [ ] Page starts with `st.title()` + `st.caption()`
- [ ] Sidebar has account selector (if account-specific data shown)
- [ ] All DB/API calls wrapped in try/except with user-visible error
- [ ] All destructive actions have a `st.warning()` confirmation
- [ ] Numbers formatted using the rules in Section 3.2
- [ ] Status badges use the colour tokens in Section 2.2
- [ ] Empty states handled with `st.info()` + `st.stop()`
