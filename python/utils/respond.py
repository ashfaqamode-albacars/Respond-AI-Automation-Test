import requests
import time
from typing import Optional
from .config import load_config

BASE_URL = "https://app.respond.io/api/v2"


def _headers():
    cfg = load_config()
    return {"Authorization": f"Bearer {cfg['respond']['api_key']}"}


def get_contact_by_phone(phone: str) -> Optional[dict]:
    """Find a contact in Respond.io by phone number."""
    resp = requests.get(
        f"{BASE_URL}/contact",
        params={"phone": phone},
        headers=_headers(),
        timeout=10,
    )
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    data = resp.json()
    contacts = data.get("data", {}).get("items", [])
    return contacts[0] if contacts else None


def get_latest_message(contact_id: str) -> Optional[dict]:
    """Get the most recent message in the contact's conversation."""
    resp = requests.get(
        f"{BASE_URL}/contact/{contact_id}/message",
        headers=_headers(),
        timeout=10,
    )
    resp.raise_for_status()
    messages = resp.json().get("data", {}).get("items", [])
    # Filter to messages sent by the AI/agent (not the customer)
    agent_messages = [m for m in messages if m.get("direction") == "outgoing"]
    return agent_messages[0] if agent_messages else None


def poll_for_reply(contact_id: str, sent_after_ts: float, max_wait: int = None) -> Optional[dict]:
    """
    Poll Respond.io until a new outgoing (AI) message appears after sent_after_ts.

    Args:
        contact_id: Respond.io contact ID.
        sent_after_ts: Unix timestamp — only count messages newer than this.
        max_wait: Max seconds to wait (defaults to config value).

    Returns:
        The new message dict, or None if timeout reached.
    """
    cfg = load_config()
    timeout = max_wait or cfg["timing"]["reply_poll_seconds"]
    interval = 2
    elapsed = 0

    while elapsed < timeout:
        msg = get_latest_message(contact_id)
        if msg:
            msg_ts = msg.get("createdAt", 0)
            # createdAt may be in ms
            if msg_ts > 1e12:
                msg_ts = msg_ts / 1000
            if msg_ts > sent_after_ts:
                return msg
        time.sleep(interval)
        elapsed += interval

    return None


def get_contact_fields(contact_id: str) -> dict:
    """Get all fields for a contact including lifecycle, department, stock number etc."""
    resp = requests.get(
        f"{BASE_URL}/contact/{contact_id}",
        headers=_headers(),
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json().get("data", {})


def delete_contact(contact_id: str) -> bool:
    """Delete a contact from Respond.io to reset for next test."""
    resp = requests.delete(
        f"{BASE_URL}/contact/{contact_id}",
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
    return contact["id"] if contact else None
