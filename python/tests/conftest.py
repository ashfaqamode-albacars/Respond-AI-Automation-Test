"""
conftest.py — shared fixtures for all tests.

Every test gets:
  - clean_contact: yields the Respond.io contact ID once a message is sent,
    then deletes the contact in teardown regardless of pass/fail.
"""

import time
import pytest
from utils.config import load_config
from utils import respond, sheets_results


@pytest.fixture(autouse=True)
def ensure_sheet_headers():
    """Make sure the results sheet has headers before any test runs."""
    sheets_results.ensure_headers()


@pytest.fixture
def cfg():
    return load_config()


@pytest.fixture
def your_phone(cfg):
    return cfg["whatsapp"]["your_number"]


@pytest.fixture
def clean_contact(your_phone):
    """
    Fixture that yields a helper to retrieve the contact ID,
    and always deletes the contact after the test.

    Usage in test:
        def test_something(clean_contact, your_phone):
            send_message("hi")
            contact_id = clean_contact(your_phone)
            ...
    """
    contact_ids = []

    def _get_contact_id(phone):
        # Poll briefly — contact may take a moment to appear after first message
        for _ in range(5):
            cid = respond.get_contact_id_for_test(phone)
            if cid:
                contact_ids.append(cid)
                return cid
            time.sleep(2)
        raise RuntimeError(
            f"Contact not found in Respond.io for {phone} after sending message. "
            "Check that the WhatsApp message was delivered and Respond.io received it."
        )

    yield _get_contact_id

    # Teardown: delete all contacts created in this test
    for cid in contact_ids:
        try:
            respond.delete_contact(cid)
        except Exception as e:
            print(f"Warning: could not delete contact {cid}: {e}")


def assert_reply_contains(reply: dict, keywords: list[str], case_sensitive: bool = False) -> tuple[bool, str]:
    """Assert that the AI reply text contains all given keywords."""
    if not reply:
        return False, "No reply received within timeout"
    text = reply.get("text", "") or ""
    if not case_sensitive:
        text = text.lower()
        keywords = [k.lower() for k in keywords]
    missing = [k for k in keywords if k not in text]
    if missing:
        return False, f"Reply missing keywords: {missing}. Got: '{text[:300]}'"
    return True, f"Reply contains all expected keywords. Preview: '{text[:200]}'"


def assert_reply_language(reply: dict, language: str) -> tuple[bool, str]:
    """
    Basic language check. For Arabic, checks for presence of Arabic Unicode characters.
    For English, checks absence of Arabic characters.
    """
    if not reply:
        return False, "No reply received"
    text = reply.get("text", "") or ""

    # Arabic Unicode range: \u0600-\u06FF
    has_arabic = any('\u0600' <= c <= '\u06FF' for c in text)

    if language.lower() == "arabic":
        if has_arabic:
            return True, "Reply is in Arabic"
        return False, f"Expected Arabic reply but got: '{text[:200]}'"
    else:
        if not has_arabic:
            return True, "Reply is in English"
        return False, f"Expected English reply but reply contains Arabic characters"


def assert_reply_has_url(reply: dict, url_fragment: str) -> tuple[bool, str]:
    """Assert the reply contains a URL containing url_fragment."""
    if not reply:
        return False, "No reply received"
    text = reply.get("text", "") or ""
    if url_fragment.lower() in text.lower():
        return True, f"Reply contains URL fragment '{url_fragment}'"
    return False, f"Reply does not contain URL fragment '{url_fragment}'. Got: '{text[:300]}'"
