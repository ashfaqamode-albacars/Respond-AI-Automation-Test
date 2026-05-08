import requests
import time
from .config import load_config

def send_message(message: str, delay_after: float = None) -> bool:
    """
    Send a WhatsApp message from your number to Alba via the Node.js whatsapp-web.js service.

    Args:
        message: The text to send.
        delay_after: Optional seconds to wait after sending (defaults to config value).

    Returns:
        True if sent successfully, raises on failure.
    """
    cfg = load_config()
    url = cfg["whatsapp"]["node_service_url"]
    alba_number = cfg["whatsapp"]["alba_number"]

    # Node.js service expects the number in international format without +
    # whatsapp-web.js uses format: "9715XXXXXXXX@c.us"
    number_clean = alba_number.replace("+", "").replace(" ", "")
    chat_id = f"{number_clean}@c.us"

    payload = {"chatId": chat_id, "message": message}

    try:
        resp = requests.post(f"{url}/send", json=payload, timeout=10)
        resp.raise_for_status()
    except requests.exceptions.ConnectionError:
        raise RuntimeError(
            "Cannot connect to Node.js WhatsApp service. "
            "Is it running? Start it with: cd node && node whatsapp_service.js"
        )

    wait = delay_after if delay_after is not None else cfg["timing"]["message_delay_seconds"]
    if wait:
        time.sleep(wait)

    return True
