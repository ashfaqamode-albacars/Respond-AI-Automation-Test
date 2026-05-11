import requests
import time
from typing import Optional
from .config import load_config

BASE_URL = "https://api.respond.io/v2"


def _headers():
    cfg = load_config()
    return {"Authorization": f"Bearer {cfg['respond']['api_key']}"}


def get_contact_by_phone(phone: str) -> Optional[dict]:
    resp = requests.get(
        f"{BASE_URL}/contact/phone:{phone}",
        headers=_headers(),
        timeout=10,
    )
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


def get_latest_message(contact_id: str) -> Optional[dict]:
    """Get the most recent AI agent message for this contact."""
    resp = requests.get(
        f"{BASE_URL}/contact/id:{contact_id}/message/list",
        headers=_headers(),
        params={"limit": 10},
        timeout=10,
    )
    resp.raise_for_status()
    items = resp.json().get("items", [])
    # Filter to AI agent outgoing messages only
    ai_messages = [
        m for m in items
        if m.get("traffic") == "outgoing"
        and m.get("sender", {}).get("source") == "ai_agent"
    ]
    return ai_messages[0] if ai_messages else None


def poll_for_reply(contact_id: str, sent_after_ts: float, max_wait: int = None, retries: int = 2, retry_gap: float = 2.0) -> Optional[dict]:
    """
    Poll until a new ai_agent message appears after sent_after_ts.
    sent_after_ts is a Python time.time() value (seconds).
    Respond.io timestamps are in milliseconds so we convert.
    """
    cfg = load_config()
    timeout = max_wait or cfg["timing"]["reply_poll_seconds"]
    interval = 2
    elapsed = 0
    sent_after_ms = sent_after_ts * 1000  # convert to ms for comparison
    for attempt in range(retries):
        elapsed = 0  # ← reset here
        while elapsed < timeout:
            msg = get_latest_message(contact_id)
            if msg:
                statuses = msg.get("status", [])
                msg_ts_ms = statuses[0].get("timestamp", 0) if statuses else 0
                if msg_ts_ms > sent_after_ms:
                    return msg
            time.sleep(interval)
            elapsed += interval
        if attempt < retries - 1:
            time.sleep(retry_gap)
    return None


def get_contact_fields(contact_id: str) -> dict:
    """Get all fields for a contact including lifecycle, department, stock number etc."""
    resp = requests.get(
        f"{BASE_URL}/contact/id:{contact_id}",
        headers=_headers(),
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def delete_contact(contact_id: str) -> bool:
    resp = requests.delete(
        f"{BASE_URL}/contact/id:{contact_id}",
        headers=_headers(),
        timeout=10,
    )
    if resp.status_code in (200, 204, 404):
        return True
    resp.raise_for_status()
    return False


def get_contact_id_for_test(your_phone: str) -> Optional[str]:
    """Helper: find the contact Respond.io created from your phone number."""
    contact = get_contact_by_phone(your_phone)
    if not contact:
        return None
    return contact.get("id")
