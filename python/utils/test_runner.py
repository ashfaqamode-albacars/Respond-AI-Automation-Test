"""
test_runner.py — config-driven test execution engine.

Reads test definitions from test_cases.yaml and runs them using the existing
utility modules (whatsapp, respond, odoo, sheets_stock, sheets_results, ai_check).
"""

import time
import os
import yaml
from typing import Optional
from utils import whatsapp, respond, odoo, sheets_stock, sheets_results, ai_check
from utils.message_generator import generate_message
from utils.config import load_config


# ---------------------------------------------------------------------------
# Data source registry
# ---------------------------------------------------------------------------

DATA_SOURCES = {
    "coming_soon_car": lambda params: sheets_stock.get_coming_soon_car(),
    "available_car": lambda params: sheets_stock.get_available_car(),
    "eligible_purchase_car": lambda params: sheets_stock.get_eligible_purchase_car(),
    "disqualified_purchase_car": lambda params: sheets_stock.get_disqualified_purchase_car(),
    "price_range": lambda params: sheets_stock.get_car_in_price_range(
        params.get("min_price", 0), params.get("max_price", 999999)
    ),
    "monthly_budget": lambda params: sheets_stock.get_car_by_monthly_budget(
        params.get("max_monthly", 9999)
    ),
}


def load_test_cases() -> dict:
    """Load test case definitions from test_cases.yaml."""
    config_path = os.path.join(os.path.dirname(__file__), "config/test_cases.yaml")
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _get_car_data(test_case: dict) -> Optional[dict]:
    """Fetch car data from the stock sheet if the test requires it."""
    source = test_case.get("data_source")
    if not source:
        return None
    if source not in DATA_SOURCES:
        raise ValueError(f"Unknown data_source: {source}")
    params = test_case.get("data_params", {})
    return DATA_SOURCES[source](params)


def _get_message(step: dict, car_data: dict = None) -> str:
    """Get the message to send — either fixed or AI-generated."""
    if "fixed_message" in step:
        return step["fixed_message"]
    if "prompt" in step:
        return generate_message(step["prompt"], car_data)
    raise ValueError(f"Test step has neither 'fixed_message' nor 'prompt': {step.get('name', 'unnamed')}")


def _assert_keywords(reply: dict, keywords: list) -> tuple:
    """Check if reply contains all keywords. Returns (passed, detail)."""
    if not reply:
        return False, "No reply received within timeout"
    text = reply.get("message", {}).get("text", "") or ""
    text_lower = text.lower()
    keywords_lower = [k.lower() for k in keywords]
    missing = [k for k in keywords_lower if k not in text_lower]
    if missing:
        return False, f"Reply missing keywords: {missing}. Got: '{text[:300]}'"
    return True, f"Reply contains all expected keywords. Preview: '{text[:200]}'"


def _assert_language(reply: dict, language: str) -> tuple:
    """Check reply language. Returns (passed, detail)."""
    if not reply:
        return False, "No reply received"
    text = reply.get("message", {}).get("text", "") or ""
    has_arabic = any('\u0600' <= c <= '\u06FF' for c in text)
    if language.lower() == "arabic":
        return (True, "Reply is in Arabic") if has_arabic else (False, f"Expected Arabic: '{text[:200]}'")
    return (True, "Reply is in English") if not has_arabic else (False, "Unexpected Arabic in reply")


def _assert_url(reply: dict, url_fragment: str) -> tuple:
    """Check if reply contains a URL fragment. Returns (passed, detail)."""
    if not reply:
        return False, "No reply received"
    text = reply.get("message", {}).get("text", "") or ""
    if url_fragment.lower() in text.lower():
        return True, f"Reply contains URL fragment '{url_fragment}'"
    return False, f"URL fragment '{url_fragment}' not found in reply"


def _parse_odoo_check(check_str: str) -> tuple:
    """Parse 'field: value' string into (field, value) tuple."""
    parts = check_str.split(":", 1)
    if len(parts) != 2:
        raise ValueError(f"Invalid odoo_check format: '{check_str}'. Expected 'field: value'")
    return parts[0].strip(), parts[1].strip()


# ---------------------------------------------------------------------------
# Main runners
# ---------------------------------------------------------------------------

def run_isolated_test(test_case: dict, your_phone: str, get_contact_id) -> dict:
    """
    Run a single isolated test case.

    Returns:
        dict with keys: passed, respond_detail, odoo_detail, ai_notes, actual_reply, message_sent
    """
    cfg = load_config()
    respond_parts = []
    odoo_parts = []
    ai_notes_parts = []

    # 1. Get car data if needed
    car_data = _get_car_data(test_case)

    # 2. Get message
    message = _get_message(test_case, car_data)

    # 3. Send message
    sent_at = time.time()
    whatsapp.send_message(message)

    # 4. Get contact ID
    contact_id = get_contact_id(your_phone)

    # 5. Poll for reply
    reply = respond.poll_for_reply(contact_id, sent_after_ts=sent_at)

    # 6. Assert reply — keywords
    keywords = test_case.get("keywords")
    if keywords:
        passed, detail = _assert_keywords(reply, keywords)
        respond_parts.append(("keywords", passed, detail))
        if not passed:
            actual_text = reply.get("message", {}).get("text", "") if reply else ""
            verdict, explanation = ai_check.ai_check_reply(actual_text, test_case["expected"])
            ai_notes_parts.append(f"Keyword check failed → AI: {verdict}: {explanation}")

    # 7. Assert reply — language
    language = test_case.get("reply_language", "english")
    lang_passed, lang_detail = _assert_language(reply, language)
    respond_parts.append(("language", lang_passed, lang_detail))

    # 8. Assert reply — URL
    url_frag = test_case.get("reply_url")
    if url_frag:
        url_passed, url_detail = _assert_url(reply, url_frag)
        respond_parts.append(("url", url_passed, url_detail))

    # 9. Assert Respond.io contact fields (odoo_checks that are also respond fields)
    odoo_checks = test_case.get("odoo_checks", [])
    for check_str in odoo_checks:
        field, expected_val = _parse_odoo_check(check_str)
        contact_fields = respond.get_contact_fields(contact_id)
        actual = contact_fields.get(field, "")
        if isinstance(actual, dict):
            actual = actual.get("name", actual)
        passed = str(actual).lower() == str(expected_val).lower()
        respond_parts.append((f"respond.{field}", passed,
                              f"{field}: expected '{expected_val}', got '{actual}'"))

    # 10. Odoo assertions
    lead = None
    odoo_check_fields = test_case.get("odoo_checks", [])
    odoo_activity = test_case.get("odoo_activity")
    no_odoo_activity = test_case.get("no_odoo_activity", False)

    if odoo_check_fields or odoo_activity or no_odoo_activity:
        lead = odoo.wait_and_get_lead(your_phone)

        for check_str in odoo_check_fields:
            field, expected_val = _parse_odoo_check(check_str)
            if lead:
                passed, detail = odoo.assert_lead_field(lead, field, expected_val)
                odoo_parts.append((field, passed, detail))
            else:
                odoo_parts.append((field, False, "No lead found in Odoo"))

        if odoo_activity:
            if lead:
                activities = odoo.get_activities_for_lead(lead["id"])
                has_act = odoo.has_activity_of_type(activities, odoo_activity)
                odoo_parts.append(("activity", has_act,
                                   f"Activity '{odoo_activity}': {'found ✅' if has_act else 'NOT found ❌'}"))
            else:
                odoo_parts.append(("activity", False, "No lead found"))

        if no_odoo_activity:
            if lead:
                activities = odoo.get_activities_for_lead(lead["id"])
                has_any = len(activities) > 0
                odoo_parts.append(("no_activity", not has_any,
                                   f"Expected no activities: {'✅ none' if not has_any else f'❌ found {len(activities)}'}"))

    # 11. Build results
    respond_all_passed = all(p for _, p, _ in respond_parts)
    odoo_all_passed = all(p for _, p, _ in odoo_parts) if odoo_parts else True
    overall_pass = respond_all_passed and odoo_all_passed

    respond_summary = " | ".join(
        f"{n}={'✅' if p else '❌'} {d}" for n, p, d in respond_parts if "ai_check" not in n
    )
    odoo_summary = " | ".join(
        f"{n}={'✅' if p else '❌'} {d}" for n, p, d in odoo_parts
    ) or "N/A"
    ai_notes = " | ".join(ai_notes_parts)
    actual_reply_text = (reply.get("message", {}).get("text", "") if reply else "NO REPLY")[:500]

    # 12. Log to sheets
    if overall_pass:
        sheets_results.log_pass(test_case["name"], message, test_case["expected"],
                                actual_reply_text, respond_summary, odoo_summary, ai_notes=ai_notes)
    else:
        sheets_results.log_fail(test_case["name"], message, test_case["expected"],
                                actual_reply_text, respond_summary, odoo_summary, ai_notes=ai_notes)

    return {
        "passed": overall_pass,
        "respond_detail": respond_summary,
        "odoo_detail": odoo_summary,
        "ai_notes": ai_notes,
        "actual_reply": actual_reply_text,
        "message_sent": message,
        "reply": reply,
    }


def run_flow_test(test_case: dict, your_phone: str, get_contact_id) -> dict:
    """
    Run a sequential flow test case (multiple steps, same contact).

    Returns:
        dict with keys: passed, respond_detail, odoo_detail, ai_notes, actual_reply, message_sent
    """
    cfg = load_config()
    results = []
    ai_notes_parts = []
    messages = []
    last_reply = None

    # 1. Get car data if needed (shared across all steps)
    car_data = _get_car_data(test_case)

    contact_id = None

    for i, step in enumerate(test_case["steps"]):
        # 2. Get message for this step
        message = _get_message(step, car_data)
        messages.append(f"Step {i+1}: {message}")

        # 3. Send message
        sent_at = time.time()
        if i == 0:
            whatsapp.send_message(message)
            contact_id = get_contact_id(your_phone)
        else:
            whatsapp.send_message(message, delay_after=cfg["timing"]["message_delay_seconds"])

        # 4. Poll for reply
        reply = respond.poll_for_reply(contact_id, sent_after_ts=sent_at)
        last_reply = reply

        # 5. Assert keywords
        keywords = step.get("keywords")
        if keywords:
            passed, detail = _assert_keywords(reply, keywords)
            results.append((f"step{i+1}_keywords", passed, detail))
            if not passed:
                actual_text = reply.get("message", {}).get("text", "") if reply else ""
                verdict, explanation = ai_check.ai_check_reply(actual_text, step["expected"])
                ai_notes_parts.append(f"Step {i+1} AI: {verdict}: {explanation}")

        # 6. Assert language if specified
        language = step.get("reply_language")
        if language:
            lang_passed, lang_detail = _assert_language(reply, language)
            results.append((f"step{i+1}_language", lang_passed, lang_detail))

    # 7. Odoo assertions (after all steps complete)
    odoo_parts = []
    odoo_checks = test_case.get("odoo_checks", [])
    odoo_activity = test_case.get("odoo_activity")

    if odoo_checks or odoo_activity:
        lead = odoo.wait_and_get_lead(your_phone)

        for check_str in odoo_checks:
            field, expected_val = _parse_odoo_check(check_str)
            # Special case: visit_removed
            if field == "visit_removed" and expected_val.lower() == "true":
                if lead:
                    activities = odoo.get_activities_for_lead(lead["id"])
                    no_visit = not odoo.has_activity_of_type(activities, "Visit")
                    odoo_parts.append(("visit_removed", no_visit,
                                       f"Visit removed: {'✅' if no_visit else '❌ still present'}"))
                else:
                    odoo_parts.append(("visit_removed", False, "No lead found"))
            else:
                if lead:
                    passed, detail = odoo.assert_lead_field(lead, field, expected_val)
                    odoo_parts.append((field, passed, detail))
                else:
                    odoo_parts.append((field, False, "No lead found"))

        if odoo_activity:
            if lead:
                activities = odoo.get_activities_for_lead(lead["id"])
                has_act = odoo.has_activity_of_type(activities, odoo_activity)
                odoo_parts.append(("activity", has_act,
                                   f"Activity '{odoo_activity}': {'found ✅' if has_act else 'NOT found ❌'}"))
            else:
                odoo_parts.append(("activity", False, "No lead found"))

    # 8. Build results
    all_respond_passed = all(p for _, p, _ in results)
    all_odoo_passed = all(p for _, p, _ in odoo_parts) if odoo_parts else True
    overall_pass = all_respond_passed and all_odoo_passed

    respond_summary = " | ".join(
        f"{n}={'✅' if p else '❌'} {d}" for n, p, d in results
    )
    odoo_summary = " | ".join(
        f"{n}={'✅' if p else '❌'} {d}" for n, p, d in odoo_parts
    ) or "N/A"
    ai_notes = " | ".join(ai_notes_parts)
    messages_str = " | ".join(messages)
    actual_reply_text = (last_reply.get("message", {}).get("text", "") if last_reply else "NO REPLY")[:500]

    # 9. Log to sheets
    if overall_pass:
        sheets_results.log_pass(test_case["name"], messages_str, test_case.get("expected", "See steps"),
                                actual_reply_text, respond_summary, odoo_summary, ai_notes=ai_notes)
    else:
        sheets_results.log_fail(test_case["name"], messages_str, test_case.get("expected", "See steps"),
                                actual_reply_text, respond_summary, odoo_summary, ai_notes=ai_notes)

    return {
        "passed": overall_pass,
        "respond_detail": respond_summary,
        "odoo_detail": odoo_summary,
        "ai_notes": ai_notes,
        "actual_reply": actual_reply_text,
        "message_sent": messages_str,
    }
