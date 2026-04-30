from __future__ import annotations

import sqlite3
from datetime import date, datetime
from typing import Optional

import requests

try:
    from core.db import get_scrape_cache, upsert_scrape_cache
except ImportError:
    from db import get_scrape_cache, upsert_scrape_cache


_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Referer": "https://www.chittorgarh.com/",
    "Origin": "https://www.chittorgarh.com",
    "Accept": "application/json, text/plain, */*",
}


class ScraperError(Exception):
    pass


def _fy_string(year: int) -> str:
    # Chittorgarh uses the FY that starts in the previous calendar year
    # e.g. year=2026 → "2025-26", year=2025 → "2024-25"
    return f"{year - 1}-{year % 100:02d}"


def _build_api_url(year: int) -> str:
    fy = _fy_string(year)
    return (
        f"https://webnodejs.chittorgarh.com/cloud/report/data-read"
        f"/25/1/4/{year}/{fy}/0/mainboard/0?search=&v=08-01"
    )


def _parse_listing_date(raw: str) -> Optional[date]:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
    except (ValueError, AttributeError):
        try:
            return datetime.strptime(raw[:10], "%Y-%m-%d").date()
        except (ValueError, AttributeError):
            return None


def _parse_row(row: dict) -> dict | None:
    name = (row.get("Company") or "").strip()
    nse_symbol = (row.get("~nse_symbol") or row.get("NSE Symbol") or "").strip()
    bse_code = str(row.get("~bse_script_code") or row.get("BSE Scrip Code") or "").strip()
    isin = (row.get("~isin") or row.get("ISIN") or "").strip()
    listing_at = (row.get("Listing At") or "").strip()
    listing_date = _parse_listing_date(
        row.get("~IL_IPO_Listing_date") or row.get("Listing Date") or ""
    )

    if not name or not listing_date:
        return None

    return {
        "name": name,
        "nse_symbol": nse_symbol,
        "bse_code": bse_code,
        "listing_date": listing_date,
        "isin": isin,
        "listing_at": listing_at,
    }


def fetch_ipo_listings_for_year(year: int, session: Optional[requests.Session] = None) -> list[dict]:
    url = _build_api_url(year)
    sess = session or requests.Session()
    try:
        resp = sess.get(url, headers=_HEADERS, timeout=20)
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise ScraperError(f"Failed to fetch IPO data for {year}: {exc}") from exc

    try:
        data = resp.json()
    except ValueError as exc:
        raise ScraperError(f"Non-JSON response for year {year}") from exc

    # API returns either a list directly or {"data": [...]} or {"report": [...]}
    if isinstance(data, list):
        rows = data
    elif isinstance(data, dict):
        rows = (
            data.get("reportTableData")
            or data.get("data")
            or data.get("report")
            or data.get("records")
            or []
        )
    else:
        rows = []

    result = []
    for row in rows:
        parsed = _parse_row(row)
        if parsed:
            result.append(parsed)
    return result


def fetch_ipo_listings(
    from_date: date,
    to_date: date,
    conn: sqlite3.Connection,
    force_refresh: bool = False,
) -> list[dict]:
    years = list(range(from_date.year, to_date.year + 1))
    session = requests.Session()
    all_ipos: list[dict] = []

    for year in years:
        cached = None if force_refresh else get_scrape_cache(conn, year)
        if cached is not None:
            ipos = []
            for entry in cached:
                entry = dict(entry)
                if isinstance(entry.get("listing_date"), str):
                    entry["listing_date"] = _parse_listing_date(entry["listing_date"])
                ipos.append(entry)
        else:
            ipos = fetch_ipo_listings_for_year(year, session)
            upsert_scrape_cache(conn, year, ipos)

        all_ipos.extend(ipos)

    filtered = [
        ipo for ipo in all_ipos
        if ipo.get("listing_date") and from_date <= ipo["listing_date"] <= to_date
    ]
    filtered.sort(key=lambda x: x["listing_date"])
    return filtered
