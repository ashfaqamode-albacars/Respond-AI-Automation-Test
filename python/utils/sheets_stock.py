import os
from typing import Optional
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from .config import load_config

_service = None
_cached_rows = None

SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
SA_PATH = os.path.join(os.path.dirname(__file__), "../config/sheets_stock_sa.json")


def _get_service():
    global _service
    if _service:
        return _service
    creds = Credentials.from_service_account_file(SA_PATH, scopes=SCOPES)
    _service = build("sheets", "v4", credentials=creds)
    return _service


def _get_all_rows() -> list[dict]:
    """Fetch all rows from the stock sheet and return as list of dicts."""
    global _cached_rows
    if _cached_rows is not None:
        return _cached_rows

    cfg = load_config()
    sheet_id = cfg["sheets"]["stock_sheet_id"]
    sheet_name = cfg["sheets"]["stock_sheet_name"]

    result = (
        _get_service()
        .spreadsheets()
        .values()
        .get(spreadsheetId=sheet_id, range=sheet_name)
        .execute()
    )

    values = result.get("values", [])
    if not values:
        return []

    headers = values[0]
    rows = []
    for row in values[1:]:
        padded = row + [""] * (len(headers) - len(row))
        rows.append(dict(zip(headers, padded)))

    _cached_rows = rows
    return rows


def _parse_price(price_str: str) -> Optional[float]:
    """Parse price strings like '132999 AED' or '49999 AED' into float."""
    if not price_str:
        return None
    cleaned = price_str.replace("AED", "").replace(",", "").strip()
    try:
        return float(cleaned)
    except ValueError:
        return None


def _parse_monthly(monthly_str: str) -> Optional[float]:
    """Parse monthly price strings like '2605.0AED' into float."""
    if not monthly_str:
        return None
    cleaned = monthly_str.replace("AED", "").replace(",", "").strip()
    try:
        return float(cleaned)
    except ValueError:
        return None


def _parse_year(year_str: str) -> Optional[int]:
    try:
        return int(str(year_str).strip())
    except (ValueError, TypeError):
        return None


def _parse_mileage(mileage_str: str) -> Optional[int]:
    """Parse mileage strings like '36156 Km' into int."""
    if not mileage_str:
        return None
    cleaned = mileage_str.replace("Km", "").replace(",", "").strip()
    try:
        return int(float(cleaned))
    except ValueError:
        return None


def get_coming_soon_car() -> Optional[dict]:
    """Return the first car with Current Status = CS."""
    for row in _get_all_rows():
        if row.get("Current Status", "").strip().upper() == "CS":
            return row
    return None


def get_car_in_price_range(min_price: float, max_price: float) -> Optional[dict]:
    """Return the first available car whose price falls within the given range."""
    for row in _get_all_rows():
        if row.get("Current Status", "").strip().upper() != "AV":
            continue
        price = _parse_price(row.get("Price", ""))
        if price and min_price <= price <= max_price:
            return row
    return None


def get_car_by_monthly_budget(max_monthly: float) -> Optional[dict]:
    """Return the first available car whose monthly price is within budget."""
    for row in _get_all_rows():
        if row.get("Current Status", "").strip().upper() != "AV":
            continue
        monthly = _parse_monthly(row.get("Monthly Price", ""))
        if monthly and monthly <= max_monthly:
            return row
    return None


def get_available_car() -> Optional[dict]:
    """Return any available car (first AV car in sheet)."""
    for row in _get_all_rows():
        if row.get("Current Status", "").strip().upper() == "AV":
            return row
    return None


def get_eligible_purchase_car() -> dict:
    """
    Return a hardcoded eligible car for the purchase test.
    Rules: mainstream German brand, 2022 or newer, under 40000km, GCC spec.
    We use fixed values so the test message is predictable.
    """
    return {
        "Brand": "BMW",
        "Model": "530i",
        "Year": "2022",
        "Mileage": "32000 Km",
        "SPEC": "GCC",
    }


def get_disqualified_purchase_car() -> dict:
    """
    Return a hardcoded disqualified car (pre-2015) for the purchase disqualified test.
    """
    return {
        "Brand": "Toyota",
        "Model": "Corolla",
        "Year": "2014",
        "Mileage": "95000 Km",
        "SPEC": "GCC",
    }


def invalidate_cache():
    """Force a fresh fetch on the next call. Useful if stock changes mid-run."""
    global _cached_rows
    _cached_rows = None
