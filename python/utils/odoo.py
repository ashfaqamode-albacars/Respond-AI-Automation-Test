import requests
import time
from typing import Optional, List
from .config import load_config

_uid = None


def _call(endpoint: str, payload: dict) -> dict:
    cfg = load_config()
    url = f"{cfg['odoo']['url']}{endpoint}"
    resp = requests.post(url, json=payload, timeout=15)
    resp.raise_for_status()
    result = resp.json()
    if "error" in result:
        raise RuntimeError(f"Odoo JSON-RPC error: {result['error']}")
    return result.get("result")


def authenticate() -> int:
    global _uid
    if _uid:
        return _uid
    cfg = load_config()
    result = _call("/jsonrpc", {
        "jsonrpc": "2.0",
        "method": "call",
        "id": 1,
        "params": {
            "service": "common",
            "method": "authenticate",
            "args": [
                cfg["odoo"]["db"],
                cfg["odoo"]["username"],
                cfg["odoo"]["api_key"],
                {}
            ] 
            # "kwargs": { # "fields": fields, # "limit": limit, # "context": {"uid": uid}, # },
        }
    })
    if not result:
        raise RuntimeError("Odoo authentication failed. Check credentials in config.yaml.")
    _uid = result
    return _uid


def search_read(model: str, domain: list, fields: list, limit: int = 10) -> List[dict]:
    cfg = load_config()
    uid = authenticate()
    return _call("/jsonrpc", {
        "jsonrpc": "2.0",
        "method": "call",
        "params": {
            "service": "object",
            "method": "execute_kw",
            "args": [
                cfg["odoo"]["db"],
                uid,
                cfg["odoo"]["api_key"],
                model,
                "search_read",
                [domain],
                {
                    "fields": fields,
                    "limit": limit,
                }
            ],
        },
    })

def get_lead_by_phone(phone: str) -> Optional[dict]:
    phone_clean = phone.lstrip("+")
    for field in ["x_studio_partner_phone"]:
        leads = search_read(
            model="x_sales_crm",
            domain=[(field, "ilike", phone_clean)],
            fields=["id", "x_name", "x_studio_stage_id", "x_studio_department",
                    "x_studio_stock_car", "x_studio_partner_phone", "create_date"],
            limit=1,
        )
        if leads:
            return leads[0]
    return None


def get_activities_for_lead(lead_id: int) -> List[dict]:
    """Get all mail.activity records linked to a CRM lead."""
    return search_read(
        model="mail.activity",
        domain=[("res_id", "=", lead_id), ("res_model", "=", "x_sales_crm")],
        fields=["id", "activity_type_id", "summary", "x_studio_due_date_time", "note", "state"],
    )


def wait_and_get_lead(phone: str, wait_seconds: int = None, retries: int = 2, retry_gap: float = 2.0) -> Optional[dict]:
    """
    Wait for Odoo sync then return the lead for this phone number.

    Args:
        phone: Customer phone number.
        wait_seconds: How long to wait before querying (defaults to config value).
    """
    cfg = load_config()
    wait = wait_seconds or cfg["timing"]["odoo_wait_seconds"]
    time.sleep(wait)
    for attempt in range(retries):
        lead = get_lead_by_phone(phone)
        if lead:
            return lead
        if attempt < retries - 1:
            time.sleep(retry_gap)
    return None

def assert_lead_field(lead: dict, field: str, expected_value, label: str = None) -> tuple[bool, str]:
    """
    Assert a field on a lead dict matches expected value.

    Returns:
        (passed: bool, detail: str)
    """
    actual = lead.get(field)
    # Handle Odoo many2one fields returned as [id, name]
    if isinstance(actual, list) and len(actual) == 2:
        actual = actual[1]
    passed = str(actual).lower() == str(expected_value).lower()
    field_label = label or field
    detail = f"{field_label}: expected '{expected_value}', got '{actual}'"
    return passed, detail


def has_activity_of_type(activities: List[dict], activity_type_name: str) -> bool:
    """Check if any activity matches the given type name (case-insensitive)."""
    for act in activities:
        type_name = act.get("activity_type_id", [None, ""])
        if isinstance(type_name, list):
            type_name = type_name[1] or ""
        if activity_type_name.lower() in type_name.lower():
            return True
    return False
