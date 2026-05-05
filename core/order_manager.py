"""
core/order_manager.py — Order and GTT placement via Zerodha Kite API.

All order placements go through explicit confirmation in the UI.
This module handles the actual API calls and persists results to the DB.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from core.kite_manager import KiteManager


class OrderError(Exception):
    pass


def place_order(
    account_id: str,
    symbol: str,
    transaction_type: str,  # "BUY" or "SELL"
    quantity: int,
    order_type: str,         # "MARKET", "LIMIT", "SL", "SL-M"
    price: float = 0.0,
    trigger_price: float = 0.0,
    product: str = "CNC",    # "CNC" (delivery) or "MIS" (intraday)
    conn=None,
    strategy_id: str = None,
    signal_id: str = None,
) -> str:
    """
    Place an order on Kite and record it in the DB.
    Returns the Kite order_id string.
    Raises OrderError on failure.
    """
    kite = KiteManager.get_kite(account_id, conn)
    if kite is None:
        raise OrderError(f"No active Kite session for account {account_id}. Please log in.")

    try:
        from kiteconnect import KiteConnect
        kite_params = {
            "tradingsymbol": symbol,
            "exchange": "NSE",
            "transaction_type": transaction_type,
            "quantity": quantity,
            "order_type": order_type,
            "product": product,
            "validity": "DAY",
        }
        if order_type == "LIMIT":
            kite_params["price"] = price
        elif order_type in ("SL", "SL-M"):
            kite_params["trigger_price"] = trigger_price
            if order_type == "SL":
                kite_params["price"] = price

        kite_order_id = kite.place_order(variety="regular", **kite_params)

    except Exception as exc:
        raise OrderError(f"Kite order placement failed: {exc}") from exc

    # Persist to DB
    if conn is not None:
        from core.db import insert_order
        order_record = {
            "id": str(uuid.uuid4()),
            "account_id": account_id,
            "kite_order_id": str(kite_order_id),
            "symbol": symbol,
            "transaction_type": transaction_type,
            "quantity": quantity,
            "order_type": order_type,
            "price": price,
            "trigger_price": trigger_price,
            "product": product,
            "status": "OPEN",
            "placed_at": datetime.utcnow().isoformat(),
            "strategy_id": strategy_id or "",
            "signal_id": signal_id or "",
        }
        insert_order(conn, order_record)

    return str(kite_order_id)


def place_gtt(
    account_id: str,
    symbol: str,
    quantity: int,
    entry_price: float,
    sl_price: float,
    target_price: float,   # T3 or whichever target the user picks
    conn=None,
    signal_id: str = None,
) -> int:
    """
    Create a two-leg GTT (Good Till Triggered) order:
    - Lower trigger = stop-loss → SELL at sl_price
    - Upper trigger = target → SELL at target_price

    GTTs persist even after session expiry — ideal for IPO breakout exits.
    Returns the Kite GTT ID.
    Raises OrderError on failure.
    """
    kite = KiteManager.get_kite(account_id, conn)
    if kite is None:
        raise OrderError(f"No active Kite session for account {account_id}. Please log in.")

    try:
        gtt_id = kite.place_gtt(
            trigger_type=kite.GTT_TYPE_OCO,  # OCO = One Cancels Other
            tradingsymbol=symbol,
            exchange="NSE",
            trigger_values=[sl_price, target_price],
            last_price=entry_price,
            orders=[
                {
                    "transaction_type": kite.TRANSACTION_TYPE_SELL,
                    "quantity": quantity,
                    "order_type": kite.ORDER_TYPE_LIMIT,
                    "product": kite.PRODUCT_CNC,
                    "price": round(sl_price * 0.995, 2),  # slight buffer below SL trigger
                },
                {
                    "transaction_type": kite.TRANSACTION_TYPE_SELL,
                    "quantity": quantity,
                    "order_type": kite.ORDER_TYPE_LIMIT,
                    "product": kite.PRODUCT_CNC,
                    "price": round(target_price * 0.995, 2),  # slight buffer below target trigger
                },
            ],
        )
    except Exception as exc:
        raise OrderError(f"Kite GTT placement failed: {exc}") from exc

    # Persist to DB
    if conn is not None:
        from core.db import insert_gtt
        import uuid
        gtt_record = {
            "id": str(uuid.uuid4()),
            "account_id": account_id,
            "kite_gtt_id": gtt_id,
            "symbol": symbol,
            "upper_trigger": target_price,
            "lower_trigger": sl_price,
            "quantity": quantity,
            "status": "active",
            "created_at": datetime.utcnow().isoformat(),
            "signal_id": signal_id or "",
        }
        insert_gtt(conn, gtt_record)

    return gtt_id


def place_protected_order(
    account_id: str,
    symbol: str,
    quantity: int,
    entry_price: float,
    sl_price: float,
    t1_price: float,
    t2_price: float,
    t3_price: float,
    order_type: str = "LIMIT",   # "LIMIT" or "MARKET"
    conn=None,
    strategy_id: str = None,
    signal_id: str = None,
) -> dict:
    """
    Place a risk-managed trade in two steps:

    Step 1 — BUY order (LIMIT or MARKET)
    Step 2 — OCO GTT immediately after:
              Lower leg: SL trigger → SELL full qty (caps loss at 1R)
              Upper leg: T3 trigger → SELL full qty (takes 3R profit)

    T1 / T2 partial exits are handled manually from the Orders page.
    After T1 is hit, user should "Move SL to Breakeven" to protect profits.

    Returns:
        {
            "order_id": str,          # Kite order ID (None if failed)
            "gtt_id": int,            # Kite GTT ID (None if failed)
            "gtt_error": str | None,  # GTT failure message (BUY may still have succeeded)
            "risk_amount": float,     # ₹ at risk = (entry - sl) × qty
            "max_profit": float,      # ₹ max profit = (t3 - entry) × qty
        }
    """
    R = entry_price - sl_price
    result = {
        "order_id": None,
        "gtt_id": None,
        "gtt_error": None,
        "risk_amount": round(R * quantity, 2),
        "max_profit": round((t3_price - entry_price) * quantity, 2),
    }

    # ── Step 1: BUY order ──────────────────────────────────────────────────────
    result["order_id"] = place_order(
        account_id=account_id,
        symbol=symbol,
        transaction_type="BUY",
        quantity=quantity,
        order_type=order_type,
        price=round(entry_price, 2) if order_type == "LIMIT" else 0.0,
        product="CNC",
        conn=conn,
        strategy_id=strategy_id,
        signal_id=signal_id,
    )

    # ── Step 2: OCO GTT (SL + T3) ─────────────────────────────────────────────
    # Even if GTT fails the BUY is live — we surface the error so user can
    # manually set GTT from the Orders page.
    try:
        result["gtt_id"] = place_gtt(
            account_id=account_id,
            symbol=symbol,
            quantity=quantity,
            entry_price=entry_price,
            sl_price=sl_price,
            target_price=t3_price,
            conn=conn,
            signal_id=signal_id,
        )
    except OrderError as exc:
        result["gtt_error"] = str(exc)

    return result


def modify_gtt_sl_to_breakeven(
    account_id: str,
    kite_gtt_id: int,
    symbol: str,
    quantity: int,
    entry_price: float,   # new SL = entry price (breakeven)
    t3_price: float,
    conn=None,
) -> bool:
    """
    After T1 is hit, move the GTT stop-loss to breakeven (entry price).
    Deletes the old GTT and creates a new OCO GTT with updated SL.
    Returns True on success.
    """
    kite = KiteManager.get_kite(account_id, conn)
    if kite is None:
        raise OrderError(f"No active Kite session for account {account_id}.")

    # Cancel old GTT
    try:
        kite.delete_gtt(trigger_id=kite_gtt_id)
    except Exception as exc:
        raise OrderError(f"Failed to cancel old GTT {kite_gtt_id}: {exc}") from exc

    # Place new GTT with SL at entry (breakeven)
    new_sl = round(entry_price * 0.999, 2)   # tiny buffer below entry
    try:
        new_gtt_id = kite.place_gtt(
            trigger_type=kite.GTT_TYPE_OCO,
            tradingsymbol=symbol,
            exchange="NSE",
            trigger_values=[new_sl, t3_price],
            last_price=entry_price,
            orders=[
                {
                    "transaction_type": kite.TRANSACTION_TYPE_SELL,
                    "quantity": quantity,
                    "order_type": kite.ORDER_TYPE_LIMIT,
                    "product": kite.PRODUCT_CNC,
                    "price": round(new_sl * 0.995, 2),
                },
                {
                    "transaction_type": kite.TRANSACTION_TYPE_SELL,
                    "quantity": quantity,
                    "order_type": kite.ORDER_TYPE_LIMIT,
                    "product": kite.PRODUCT_CNC,
                    "price": round(t3_price * 0.995, 2),
                },
            ],
        )
    except Exception as exc:
        raise OrderError(f"Failed to create breakeven GTT: {exc}") from exc

    # Update DB record
    if conn is not None:
        from core.db import insert_gtt
        import uuid
        insert_gtt(conn, {
            "id": str(uuid.uuid4()),
            "account_id": account_id,
            "kite_gtt_id": new_gtt_id,
            "symbol": symbol,
            "upper_trigger": t3_price,
            "lower_trigger": new_sl,
            "quantity": quantity,
            "status": "active",
            "created_at": datetime.utcnow().isoformat(),
            "signal_id": "",
        })

    return True


def get_live_orders(account_id: str, conn) -> list[dict]:
    """Fetch current day's orders directly from Kite (live status)."""
    kite = KiteManager.get_kite(account_id, conn)
    if kite is None:
        return []
    try:
        return kite.orders() or []
    except Exception:
        return []


def get_live_gtts(account_id: str, conn) -> list[dict]:
    """Fetch active GTTs directly from Kite."""
    kite = KiteManager.get_kite(account_id, conn)
    if kite is None:
        return []
    try:
        return kite.get_gtts() or []
    except Exception:
        return []


def cancel_order(account_id: str, kite_order_id: str, conn) -> bool:
    """Cancel an open order. Returns True on success."""
    kite = KiteManager.get_kite(account_id, conn)
    if kite is None:
        return False
    try:
        kite.cancel_order(variety="regular", order_id=kite_order_id)
        return True
    except Exception:
        return False


def cancel_gtt(account_id: str, kite_gtt_id: int, conn) -> bool:
    """Cancel a GTT order. Returns True on success."""
    kite = KiteManager.get_kite(account_id, conn)
    if kite is None:
        return False
    try:
        kite.delete_gtt(trigger_id=kite_gtt_id)
        return True
    except Exception:
        return False


# ── Bot automation functions ───────────────────────────────────────────────────

def _place_gtt_single(
    kite,
    account_id: str,
    symbol: str,
    trigger_price: float,
    sell_price: float,
    quantity: int,
    last_price: float,
    conn,
    signal_id: str,
    label: str,          # "SL", "T1", or "T2" — for DB record
) -> int:
    """
    Place a single-leg GTT SELL order. Returns Kite GTT ID.
    Raises OrderError on failure.
    """
    try:
        gtt_id = kite.place_gtt(
            trigger_type=kite.GTT_TYPE_SINGLE,
            tradingsymbol=symbol,
            exchange="NSE",
            trigger_values=[trigger_price],
            last_price=last_price,
            orders=[{
                "transaction_type": kite.TRANSACTION_TYPE_SELL,
                "quantity": quantity,
                "order_type": kite.ORDER_TYPE_LIMIT,
                "product": kite.PRODUCT_CNC,
                "price": round(sell_price, 2),
            }],
        )
    except Exception as exc:
        raise OrderError(f"GTT {label} placement failed for {symbol}: {exc}") from exc

    if conn is not None:
        from core.db import insert_gtt
        insert_gtt(conn, {
            "id": str(uuid.uuid4()),
            "account_id": account_id,
            "kite_gtt_id": gtt_id,
            "symbol": symbol,
            "upper_trigger": trigger_price if label in ("T1", "T2") else None,
            "lower_trigger": trigger_price if label == "SL" else None,
            "quantity": quantity,
            "status": "active",
            "created_at": datetime.utcnow().isoformat(),
            "signal_id": signal_id or "",
        })

    return gtt_id


def auto_place_ipo_order(
    account_id: str,
    symbol: str,
    qty: int,
    entry: float,
    sl: float,
    t1: float,
    t2: float,
    t3: float,           # informational — T3 monitored by position_tracker
    conn=None,
    strategy_id: str = None,
    signal_id: str = None,
) -> dict:
    """
    Full auto-order for IPO breakout strategy:

    1. LIMIT BUY at entry (2-week high)
    2. GTT-SL: single trigger SELL full qty at sl_price (2-week low)
    3. GTT-T1: single trigger SELL 1/3 qty at t1
    4. GTT-T2: single trigger SELL 1/3 qty at t2
       (T3 and trailing SL managed by position_tracker after T2 fires)

    Returns dict with order_id and gtt IDs. Raises OrderError on critical failure.
    """
    kite = KiteManager.get_kite(account_id, conn)
    if kite is None:
        raise OrderError(f"No active Kite session for account {account_id}.")

    t1_qty = qty // 3
    t2_qty = qty // 3
    sl_qty = qty  # full qty protected initially

    result: dict = {
        "order_id": None,
        "gtt_sl_id": None,
        "gtt_t1_id": None,
        "gtt_t2_id": None,
        "errors": [],
    }

    # Step 1: LIMIT BUY entry order
    result["order_id"] = place_order(
        account_id=account_id,
        symbol=symbol,
        transaction_type="BUY",
        quantity=qty,
        order_type="LIMIT",
        price=round(entry, 2),
        product="CNC",
        conn=conn,
        strategy_id=strategy_id,
        signal_id=signal_id,
    )

    # Step 2: GTT-SL (full qty at 2-week low)
    sl_sell_price = round(sl * 0.995, 2)  # slight buffer below trigger
    try:
        result["gtt_sl_id"] = _place_gtt_single(
            kite, account_id, symbol,
            trigger_price=sl, sell_price=sl_sell_price,
            quantity=sl_qty, last_price=entry,
            conn=conn, signal_id=signal_id, label="SL",
        )
    except OrderError as exc:
        result["errors"].append(str(exc))

    # Step 3: GTT-T1 (1/3 qty at T1)
    if t1_qty > 0:
        try:
            result["gtt_t1_id"] = _place_gtt_single(
                kite, account_id, symbol,
                trigger_price=t1, sell_price=round(t1 * 0.995, 2),
                quantity=t1_qty, last_price=entry,
                conn=conn, signal_id=signal_id, label="T1",
            )
        except OrderError as exc:
            result["errors"].append(str(exc))

    # Step 4: GTT-T2 (1/3 qty at T2)
    if t2_qty > 0:
        try:
            result["gtt_t2_id"] = _place_gtt_single(
                kite, account_id, symbol,
                trigger_price=t2, sell_price=round(t2 * 0.995, 2),
                quantity=t2_qty, last_price=entry,
                conn=conn, signal_id=signal_id, label="T2",
            )
        except OrderError as exc:
            result["errors"].append(str(exc))

    # Persist GTT IDs on signal
    if conn is not None and signal_id:
        from core.db import update_signal_gtt_ids, update_signal_status
        update_signal_gtt_ids(
            conn, signal_id,
            gtt_sl_id=result["gtt_sl_id"],
            gtt_t1_id=result["gtt_t1_id"],
            gtt_t2_id=result["gtt_t2_id"],
            kite_order_id=result["order_id"],
        )
        update_signal_status(conn, signal_id, "PENDING_FILL", order_id=result["order_id"])

    return result


def update_sl_gtt(
    account_id: str,
    old_gtt_id: int,
    symbol: str,
    new_qty: int,
    new_sl: float,
    last_price: float,
    conn=None,
    signal_id: str = None,
) -> int:
    """
    Replace the SL GTT with an updated quantity and price.
    Called by position_tracker after T1 or T2 is hit.
    Returns new GTT ID.
    """
    kite = KiteManager.get_kite(account_id, conn)
    if kite is None:
        raise OrderError(f"No active Kite session for account {account_id}.")

    # Cancel old SL GTT (ignore if already triggered/gone)
    try:
        kite.delete_gtt(trigger_id=old_gtt_id)
    except Exception:
        pass

    # Place new SL GTT
    new_gtt_id = _place_gtt_single(
        kite, account_id, symbol,
        trigger_price=new_sl,
        sell_price=round(new_sl * 0.995, 2),
        quantity=new_qty,
        last_price=last_price,
        conn=conn,
        signal_id=signal_id or "",
        label="SL",
    )
    return new_gtt_id
