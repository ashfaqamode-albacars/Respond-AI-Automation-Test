"""
test_flows.py — sequential flow tests.

Each flow uses the same contact throughout. The contact is deleted after the
full flow completes (via the clean_contact fixture).
"""

import time
import pytest
from utils import whatsapp, respond, odoo, sheets_stock, sheets_results, ai_check
from utils.config import load_config
from tests.conftest import assert_reply_contains, assert_reply_language


def _poll(contact_id, sent_at, step_name):
    """Poll for a reply and assert one was received."""
    reply = respond.poll_for_reply(contact_id, sent_after_ts=sent_at)
    assert reply is not None, f"No reply received for step: '{step_name}'"
    return reply


# ---------------------------------------------------------------------------
# Flow 1: Book → Cancel appointment
# ---------------------------------------------------------------------------

def test_book_then_cancel(your_phone, clean_contact, cfg):
    test_name = "Flow — Book then Cancel"
    car = sheets_stock.get_available_car()
    assert car, "No available car in stock"

    results = []

    # Step 1: Book appointment
    msg1 = f"I'd like to come see the {car['Brand']} {car['Model']} tomorrow at 2pm."
    t1 = time.time()
    whatsapp.send_message(msg1)
    contact_id = clean_contact(your_phone)

    reply1 = _poll(contact_id, t1, "Book appointment")
    ok1, detail1 = assert_reply_contains(reply1, ["appointment", "confirm"])
    results.append(("book_reply", ok1, detail1))

    if not ok1:
        actual_text = reply1.get("message", {}).get("text", "") if reply1 else ""
        verdict, explanation = ai_check.ai_check_reply(actual_text, "Appointment should be booked and confirmed")
        results.append((f"ai_check_book_reply", True, f"AI: {verdict}: {explanation}"))

    # Check Odoo: appointment activity created
    lead = odoo.wait_and_get_lead(your_phone)
    if lead:
        activities = odoo.get_activities_for_lead(lead["id"])
        has_meeting = odoo.has_activity_of_type(activities, "Visit")
        results.append(("odoo_visit_created", has_meeting,
                         f"Visit activity: {'found ✅' if has_meeting else 'NOT found ❌'}"))
    else:
        results.append(("odoo_lead", False, "No lead found in Odoo after booking"))

    # Step 2: Cancel appointment
    msg2 = "Actually, can you cancel my appointment?"
    t2 = time.time()
    whatsapp.send_message(msg2, delay_after=cfg["timing"]["message_delay_seconds"])
    reply2 = _poll(contact_id, t2, "Cancel appointment")
    ok2, detail2 = assert_reply_contains(reply2, ["cancel"])
    results.append(("cancel_reply", ok2, detail2))

    
    if not ok2:
        actual_text = reply2.get("message", {}).get("text", "") if reply2 else ""
        verdict, explanation = ai_check.ai_check_reply(actual_text, "Appointment should be cancelled")
        results.append((f"ai_check_cancel_reply", True, f"AI: {verdict}: {explanation}"))

    # Check Odoo: activity should be gone
    time.sleep(30)
    if lead:
        activities_after = odoo.get_activities_for_lead(lead["id"])
        no_visit = not odoo.has_activity_of_type(activities_after, "Visit")
        results.append(("odoo_visit_removed", no_visit,
                         f"Visit removed: {'✅' if no_visit else '❌ still present'}"))

    # Log and assert
    all_passed = all(p for _, p, _ in results)
    respond_detail = " | ".join(f"{n}={'✅' if p else '❌'} {d}" for n, p, d in results if "odoo" not in n and "ai_check" not in n)
    odoo_detail = " | ".join(f"{n}={'✅' if p else '❌'} {d}" for n, p, d in results if "odoo" in n)
    reply_preview = (reply2.get("message", {}).get("text", "") if reply2 else "NO REPLY")[:300]
    ai_notes = " | ".join(d for n, _, d in results if "ai_check" in n)
    if all_passed:
        sheets_results.log_pass(test_name, f"1: {msg1} | 2: {msg2}",
                                "Appointment booked then cancelled in Odoo",
                                reply_preview, respond_detail, odoo_detail, ai_notes=ai_notes)
    else:
        sheets_results.log_fail(test_name, f"1: {msg1} | 2: {msg2}",
                                "Appointment booked then cancelled in Odoo",
                                reply_preview, respond_detail, odoo_detail, ai_notes=ai_notes)

    for name, passed, detail in results:
        assert passed, f"[{test_name}] step '{name}' failed: {detail}"


# ---------------------------------------------------------------------------
# Flow 2: Book → Reschedule (last slot 9:30 edge case)
# ---------------------------------------------------------------------------

def test_book_then_reschedule(your_phone, clean_contact, cfg):
    test_name = "Flow — Book then Reschedule"
    car = sheets_stock.get_available_car()
    assert car, "No available car in stock"

    results = []

    # Step 1: Book appointment
    msg1 = f"I'd like to come see the {car['Brand']} {car['Model']} today at 3pm."
    t1 = time.time()
    whatsapp.send_message(msg1)
    contact_id = clean_contact(your_phone)

    reply1 = _poll(contact_id, t1, "Book initial appointment")
    ok1, detail1 = assert_reply_contains(reply1, ["appointment"])
    results.append(("book_reply", ok1, detail1))
    if not ok1:
        actual_text = reply1.get("message", {}).get("text", "") if reply1 else ""
        verdict, explanation = ai_check.ai_check_reply(actual_text, "Appointment should be booked")
        results.append(("ai_check_book_reply", True, f"AI: {verdict}: {explanation}"))
    # Step 2: Try to reschedule to 10pm (after last slot)
    msg2 = "Can I come see the car at 10pm instead?"
    t2 = time.time()
    whatsapp.send_message(msg2, delay_after=cfg["timing"]["message_delay_seconds"])
    reply2 = _poll(contact_id, t2, "Reschedule to 10pm")
    # AI should mention last slot is 9:30
    ok2, detail2 = assert_reply_contains(reply2, ["9:30", "last"])
    results.append(("last_slot_reply", ok2, detail2))

    if not ok2:
        actual_text = reply2.get("message", {}).get("text", "") if reply2 else ""
        verdict, explanation = ai_check.ai_check_reply(actual_text, "AI should inform the customer that the last available slot is 9:30 and not allow booking at 10pm")
        results.append(("ai_check_last_slot", True, f"AI: {verdict}: {explanation}"))

    all_passed = all(p for _, p, _ in results)
    respond_detail = " | ".join(f"{n}={'✅' if p else '❌'} {d}" for n, p, d in results if "ai_check" not in n)
    reply_preview = (reply2.get("message", {}).get("text", "") if reply2 else "NO REPLY")[:300]
    ai_notes = " | ".join(d for n, _, d in results if "ai_check" in n)

    if all_passed:
        sheets_results.log_pass(test_name, f"1: {msg1} | 2: {msg2}",
                                "AI says last slot is 9:30 when 10pm requested",
                                reply_preview, respond_detail, "N/A", ai_notes=ai_notes)
    else:
        sheets_results.log_fail(test_name, f"1: {msg1} | 2: {msg2}",
                                "AI says last slot is 9:30 when 10pm requested",
                                reply_preview, respond_detail, "N/A", ai_notes=ai_notes)

    for name, passed, detail in results:
        assert passed, f"[{test_name}] step '{name}' failed: {detail}"


# ---------------------------------------------------------------------------
# Flow 3: Aftercare pre-form → post-form
# ---------------------------------------------------------------------------

def test_aftercare_flow(your_phone, clean_contact, cfg):
    test_name = "Flow — Aftercare Pre then Post Form"
    results = []

    # Step 1: Pre-form (warranty issue)
    msg1 = "Hey I have an issue with my car and since it's still under warranty I'm hoping you could help. There is a knocking sound from the engine bay."
    t1 = time.time()
    whatsapp.send_message(msg1)
    contact_id = clean_contact(your_phone)

    reply1 = _poll(contact_id, t1, "Aftercare pre-form")
    ok1, detail1 = assert_reply_contains(reply1, ["form"])
    results.append(("pre_form_reply", ok1, detail1))

    if not ok1:
        actual_text = reply1.get("message", {}).get("text", "") if reply1 else ""
        verdict, explanation = ai_check.ai_check_reply(actual_text, "AI should send a form link for the customer to submit their warranty/aftercare issue")
        results.append(("ai_check_pre_form", True, f"AI: {verdict}: {explanation}"))

    # Step 2: Post-form (already submitted)
    msg2 = "I've already submitted the form."
    t2 = time.time()
    whatsapp.send_message(msg2, delay_after=cfg["timing"]["message_delay_seconds"])
    reply2 = _poll(contact_id, t2, "Aftercare post-form")
    ok2, detail2 = assert_reply_contains(reply2, ["whatsapp"])
    results.append(("post_form_reply", ok2, detail2))

    if not ok2:
        actual_text = reply2.get("message", {}).get("text", "") if reply2 else ""
        verdict, explanation = ai_check.ai_check_reply(actual_text, "AI should send a WhatsApp link to the aftercare team since the form was already submitted")
        results.append(("ai_check_post_form", True, f"AI: {verdict}: {explanation}"))

    all_passed = all(p for _, p, _ in results)
    respond_detail = " | ".join(f"{n}={'✅' if p else '❌'} {d}" for n, p, d in results if "ai_check" not in n)
    reply_preview = (reply2.get("message", {}).get("text", "") if reply2 else "NO REPLY")[:300]
    ai_notes = " | ".join(d for n, _, d in results if "ai_check" in n)
    if all_passed:
        sheets_results.log_pass(test_name, f"1: {msg1} | 2: {msg2}",
                                "Form link sent then aftercare WhatsApp link or number/contact sent",
                                reply_preview, respond_detail, "N/A", ai_notes=ai_notes)
    else:
        sheets_results.log_fail(test_name, f"1: {msg1} | 2: {msg2}",
                                "Form link sent then aftercare WhatsApp link or number/contact sent",
                                reply_preview, respond_detail, "N/A", ai_notes=ai_notes)

    for name, passed, detail in results:
        assert passed, f"[{test_name}] step '{name}' failed: {detail}"


# ---------------------------------------------------------------------------
# Flow 4: Purchase — full consignment flow
# ---------------------------------------------------------------------------

def test_purchase_flow(your_phone, clean_contact, cfg):
    test_name = "Flow — Purchase Consignment Full Flow"
    car = sheets_stock.get_eligible_purchase_car()
    results = []

    # Step 1: Introduce the car for sale
    msg1 = (
        f"I would like to sell my {car['Year']} {car['Brand']} {car['Model']} "
        f"GCC specs, it has {car['Mileage']}."
    )
    t1 = time.time()
    whatsapp.send_message(msg1)
    contact_id = clean_contact(your_phone)

    reply1 = _poll(contact_id, t1, "Purchase intro")
    ok1, detail1 = assert_reply_contains(reply1, ["consignment"])
    results.append(("consignment_offered", ok1, detail1))

    if not ok1:
        actual_text = reply1.get("message", {}).get("text", "") if reply1 else ""
        verdict, explanation = ai_check.ai_check_reply(actual_text, "AI should offer a consignment arrangement to the customer wanting to sell their car")
        results.append(("ai_check_consignment", True, f"AI: {verdict}: {explanation}"))

    # Step 2: Proceed with consignment
    msg2 = "Yes I would like to proceed with the consignment."
    t2 = time.time()
    whatsapp.send_message(msg2, delay_after=cfg["timing"]["message_delay_seconds"])
    reply2 = _poll(contact_id, t2, "Proceed consignment")
    ok2, detail2 = assert_reply_contains(reply2, ["appointment", "visit"])
    results.append(("proceed_reply", ok2, detail2))

    if not ok2:
        actual_text = reply2.get("message", {}).get("text", "") if reply2 else ""
        verdict, explanation = ai_check.ai_check_reply(actual_text, "AI should book an appointment or ask the customer to visit after they agreed to proceed with consignment")
        results.append(("ai_check_proceed", True, f"AI: {verdict}: {explanation}"))
        
    # Odoo checks
    lead = odoo.wait_and_get_lead(your_phone)
    if lead:
        p, d = odoo.assert_lead_field(lead, "x_studio_department", "Purchasing")
        results.append(("odoo_department", p, d))
        activities = odoo.get_activities_for_lead(lead["id"])
        has_meeting = odoo.has_activity_of_type(activities, "Meeting")
        results.append(("odoo_activity", has_meeting,
                         f"Meeting activity: {'found ✅' if has_meeting else '❌ not found'}"))
    else:
        results.append(("odoo_lead", False, "No lead found in Odoo"))

    all_passed = all(p for _, p, _ in results)
    respond_detail = " | ".join(f"{n}={'✅' if p else '❌'} {d}" for n, p, d in results if "odoo" not in n and "ai_check" not in n)
    odoo_detail = " | ".join(f"{n}={'✅' if p else '❌'} {d}" for n, p, d in results if "odoo" in n)
    reply_preview = (reply2.get("message", {}).get("text", "") if reply2 else "NO REPLY")[:300]
    ai_notes = " | ".join(d for n, _, d in results if "ai_check" in n)
    if all_passed:
        sheets_results.log_pass(test_name, f"1: {msg1} | 2: {msg2}",
                                "Consignment offered, appointment set, Odoo updated",
                                reply_preview, respond_detail, odoo_detail, ai_notes=ai_notes)
    else:
        sheets_results.log_fail(test_name, f"1: {msg1} | 2: {msg2}",
                                "Consignment offered, appointment set, Odoo updated",
                                reply_preview, respond_detail, odoo_detail, ai_notes=ai_notes)

    for name, passed, detail in results:
        assert passed, f"[{test_name}] step '{name}' failed: {detail}"
