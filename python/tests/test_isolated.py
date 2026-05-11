"""
test_isolated.py — ~20 isolated test cases.

Each test:
  1. Sends a WhatsApp message from your number to Alba
  2. Polls Respond.io for the AI reply (up to 15s)
  3. Asserts reply content / language / URLs
  4. Waits 60s then asserts Odoo side effects
  5. Logs result to Google Sheets
  6. Deletes the Respond.io contact (via clean_contact fixture)
"""

import time
import pytest
from python.utils import ai_check
from utils import whatsapp, respond, odoo, sheets_stock, sheets_results
from utils.config import load_config
from tests.conftest import assert_reply_contains, assert_reply_language, assert_reply_has_url


# ---------------------------------------------------------------------------
# Helper: run a full isolated test end-to-end
# ---------------------------------------------------------------------------

def run_test(
    test_name: str,
    message: str,
    expected_description: str,
    your_phone: str,
    clean_contact,
    reply_keywords: list[str] = None,
    reply_language: str = "english",
    reply_url_fragment: str = None,
    odoo_checks: dict = None,    # e.g. {"x_studio_stage_id": "Not Interested"}
    odoo_activity_type: str = None,
    expect_no_odoo_activity: bool = False,
):
    sent_at = time.time()

    # 1. Send message
    whatsapp.send_message(message)

    # 2. Get contact ID
    contact_id = clean_contact(your_phone)

    # 3. Poll for reply
    reply = respond.poll_for_reply(contact_id, sent_after_ts=sent_at)

    # 4. Assert reply
    respond_parts = []

    ai_notes_parts = []

    if reply_keywords:
        passed, detail = assert_reply_contains(reply, reply_keywords)
        respond_parts.append(("keywords", passed, detail))
        if not passed:
            actual_text = reply.get("message", {}).get("text", "") if reply else ""
            verdict, explanation = ai_check.ai_check_reply(actual_text, expected_description)
            ai_notes_parts.append(f"Keyword check failed → AI: {verdict}: {explanation}")
    lang_passed, lang_detail = assert_reply_language(reply, reply_language)
    respond_parts.append(("language", lang_passed, lang_detail))

    if reply_url_fragment:
        url_passed, url_detail = assert_reply_has_url(reply, reply_url_fragment)
        respond_parts.append(("url", url_passed, url_detail))

    # Check Respond.io contact fields if needed
    if odoo_checks and any(k.startswith("x_") or k in ("lifecycle",) for k in odoo_checks):
        contact_fields = respond.get_contact_fields(contact_id)
        for field, expected_val in odoo_checks.items():
            actual = contact_fields.get(field, "")
            if isinstance(actual, dict):
                actual = actual.get("name", actual)
            passed = str(actual).lower() == str(expected_val).lower()
            respond_parts.append((f"respond.{field}", passed,
                                   f"{field}: expected '{expected_val}', got '{actual}'"))

    respond_all_passed = all(p for _, p, _ in respond_parts)
    respond_summary = " | ".join(f"{n}={'✅' if p else '❌'} {d}" for n, p, d in respond_parts)

    # 5. Odoo assertions
    odoo_parts = []
    lead = None

    if odoo_checks or odoo_activity_type or expect_no_odoo_activity is not None:
        cfg = load_config()
        lead = odoo.wait_and_get_lead(your_phone)

        if odoo_checks:
            for field, expected_val in odoo_checks.items():
                if lead:
                    passed, detail = odoo.assert_lead_field(lead, field, expected_val)
                    odoo_parts.append((field, passed, detail))
                else:
                    odoo_parts.append((field, False, "No lead found in Odoo"))

        if odoo_activity_type:
            if lead:
                activities = odoo.get_activities_for_lead(lead["id"])
                has_act = odoo.has_activity_of_type(activities, odoo_activity_type)
                odoo_parts.append((
                    "activity",
                    has_act,
                    f"Activity type '{odoo_activity_type}': {'found ✅' if has_act else 'NOT found ❌'}",
                ))
            else:
                odoo_parts.append(("activity", False, "No lead found in Odoo to check activities"))

        if expect_no_odoo_activity:
            if lead:
                activities = odoo.get_activities_for_lead(lead["id"])
                has_any = len(activities) > 0
                odoo_parts.append((
                    "no_activity",
                    not has_any,
                    f"Expected no activities: {'✅ none found' if not has_any else f'❌ found {len(activities)}'}",
                ))

    odoo_all_passed = all(p for _, p, _ in odoo_parts) if odoo_parts else True
    odoo_summary = " | ".join(f"{n}={'✅' if p else '❌'} {d}" for n, p, d in odoo_parts) or "N/A"

    # 6. Log to Sheets
    actual_reply_text = (reply.get("message", {}).get("text", "") if reply else "NO REPLY")[:500]
    overall_pass = respond_all_passed and odoo_all_passed
    ai_notes = " | ".join(ai_notes_parts)
    if overall_pass:
        sheets_results.log_pass(test_name, message, expected_description,
                                actual_reply_text, respond_summary, odoo_summary, ai_notes=ai_notes)
    else:
        sheets_results.log_fail(test_name, message, expected_description,
                                actual_reply_text, respond_summary, odoo_summary, ai_notes=ai_notes)

    # 7. Pytest assertion (causes test to fail in runner if something is wrong)
    assert reply is not None, f"[{test_name}] No reply received within timeout"
    for name, passed, detail in respond_parts:
        assert passed, f"[{test_name}] Respond.io check '{name}' failed: {detail}"
    for name, passed, detail in odoo_parts:
        assert passed, f"[{test_name}] Odoo check '{name}' failed: {detail}"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_coming_soon(your_phone, clean_contact):
    car = sheets_stock.get_coming_soon_car()
    assert car, "No coming soon car found in stock sheet"
    msg = f"Hi, I'm interested in the {car['Year']} {car['Brand']} {car['Model']}. Is it available?"
    run_test(
        test_name="Coming Soon — Callback offered",
        message=msg,
        expected_description="Callback offered in 3 days, no Odoo activity created",
        your_phone=your_phone,
        clean_contact=clean_contact,
        reply_keywords=["callback", "call"],
        expect_no_odoo_activity=True,
    )


def test_aftercare_pre_form(your_phone, clean_contact):
    run_test(
        test_name="Aftercare — Pre form submission",
        message="Hey I have an issue with my car and since it's still under warranty with you guys I'm hoping you could help. There is some weird knocking in the engine bay.",
        expected_description="Form link sent to customer",
        your_phone=your_phone,
        clean_contact=clean_contact,
        reply_keywords=["form"],
    )


def test_aftercare_post_form(your_phone, clean_contact):
    run_test(
        test_name="Aftercare — Post form submission",
        message="I've already submitted the form.",
        expected_description="WhatsApp aftercare link sent",
        your_phone=your_phone,
        clean_contact=clean_contact,
        reply_keywords=["whatsapp"],
    )


def test_not_interested(your_phone, clean_contact):
    run_test(
        test_name="Not Interested — Left UAE",
        message="I've left the UAE and will not be proceeding.",
        expected_description="Lifecycle changed to Not Interested/Disqualified",
        your_phone=your_phone,
        clean_contact=clean_contact,
        reply_keywords=["understand", "thank"],
        odoo_checks={"x_studio_stage_id": "Not Interested"},
    )


def test_job_seeker(your_phone, clean_contact):
    run_test(
        test_name="Job Seeker — Disqualified",
        message="I was wondering if you had any position for sales agents.",
        expected_description="Marked as disqualified, not assigned to AI",
        your_phone=your_phone,
        clean_contact=clean_contact,
        reply_keywords=["career", "position"],
        odoo_checks={"x_studio_stage_id": "Disqualified"},
    )


def test_purchase_eligible(your_phone, clean_contact):
    car = sheets_stock.get_eligible_purchase_car()
    msg = (
        f"I would like to come in and sell my {car['Year']} {car['Brand']} {car['Model']} "
        f"GCC specs, it has {car['Mileage']}."
    )
    run_test(
        test_name="Purchase — Eligible Car",
        message=msg,
        expected_description="Consignment offered, department=Purchasing, Odoo: lead, appointment activity",
        your_phone=your_phone,
        clean_contact=clean_contact,
        reply_keywords=["consignment"],
        odoo_checks={"x_studio_department": "Purchasing"},
        odoo_activity_type="Meeting",
    )


def test_purchase_leaving_country(your_phone, clean_contact):
    car = sheets_stock.get_eligible_purchase_car()
    msg = (
        f"I would like to come in and sell my {car['Year']} {car['Brand']} {car['Model']} "
        f"GCC specs, it has {car['Mileage']} and I'm leaving the country soon."
    )
    run_test(
        test_name="Purchase — Leaving Country",
        message=msg,
        expected_description="Consignment offered, CRM lead created in Odoo",
        your_phone=your_phone,
        clean_contact=clean_contact,
        reply_keywords=["consignment"],
        odoo_checks={"x_studio_department": "Purchasing"},
        odoo_activity_type="Meeting",
    )


def test_purchase_disqualified(your_phone, clean_contact):
    car = sheets_stock.get_disqualified_purchase_car()
    msg = (
        f"Hi I want to sell my {car['Brand']} {car['Model']} {car['Year']}."
    )
    run_test(
        test_name="Purchase — Disqualified Car",
        message=msg,
        expected_description="Car not accepted, lifecycle Lost/Disqualified",
        your_phone=your_phone,
        clean_contact=clean_contact,
        reply_keywords=["unfortunately", "criteria"],
        odoo_checks={"x_studio_stage_id": "Disqualified"},
    )


def test_banking_rep(your_phone, clean_contact):
    run_test(
        test_name="Banking Rep Inquiry",
        message="Do you have bank and lease representatives on site?",
        expected_description="Reply mentions dedicated finance team",
        your_phone=your_phone,
        clean_contact=clean_contact,
        reply_keywords=["finance"],
    )


def test_callback_requested(your_phone, clean_contact):
    run_test(
        test_name="Callback Requested",
        message="Can you call me today at 3pm to discuss further?",
        expected_description="Affirmative response, call activity created in Odoo",
        your_phone=your_phone,
        clean_contact=clean_contact,
        reply_keywords=["call", "3"],
        odoo_activity_type="Phone Call",
    )


def test_appointment_no_time(your_phone, clean_contact):
    car = sheets_stock.get_available_car()
    assert car, "No available car in stock sheet"
    msg = f"Can I come see the {car['Brand']} {car['Model']} tomorrow but I'm not sure what time?"
    run_test(
        test_name="Appointment — No Time Given",
        message=msg,
        expected_description="Callback offered to confirm appointment time",
        your_phone=your_phone,
        clean_contact=clean_contact,
        reply_keywords=["callback", "confirm", "time"],
    )


def test_appointment_far_date(your_phone, clean_contact):
    car = sheets_stock.get_available_car()
    assert car, "No available car in stock sheet"
    msg = f"Can I come see the {car['Brand']} {car['Model']} on the 15th of next month?"
    run_test(
        test_name="Appointment — Far Date (>1 week)",
        message=msg,
        expected_description="Appointment booked, callback offered to confirm",
        your_phone=your_phone,
        clean_contact=clean_contact,
        reply_keywords=["appointment", "confirm"],
        odoo_activity_type="Meeting",
    )


def test_video_request(your_phone, clean_contact):
    run_test(
        test_name="Video Request",
        message="Can I have a video of the car?",
        expected_description="AI says no videos available",
        your_phone=your_phone,
        clean_contact=clean_contact,
        reply_keywords=["video", "unfortunately"],
    )


def test_price_buffer(your_phone, clean_contact):
    # Budget 100k-120k → AI should offer cars from ~80k to ~144k (+/-20%)
    run_test(
        test_name="Price Buffer +/-20%",
        message="For a 4 series BMW my strict budget is 100,000 to 120,000 AED, anything in that range?",
        expected_description="AI offers cars in 80k-144k range (20% buffer applied)",
        your_phone=your_phone,
        clean_contact=clean_contact,
        reply_keywords=["budget", "aed"],
    )


def test_monthly_budget(your_phone, clean_contact):
    run_test(
        test_name="Monthly Budget",
        message="I actually want to get an Audi Q5 and my budget is max 2,000 AED per month. What options do you have?",
        expected_description="Options within monthly budget shown",
        your_phone=your_phone,
        clean_contact=clean_contact,
        reply_keywords=["month", "aed"],
    )


def test_on_my_way(your_phone, clean_contact):
    run_test(
        test_name="On My Way",
        message="I'm on my way.",
        expected_description="Address reply sent, conversation closed",
        your_phone=your_phone,
        clean_contact=clean_contact,
        reply_keywords=["alba", "warehouse"],
    )


def test_arabic_text(your_phone, clean_contact):
    run_test(
        test_name="Arabic — Text Message",
        message="مرحبا، أنا مهتم بشراء سيارة. هل يمكنك مساعدتي؟",
        expected_description="Reply in Arabic, Arabic URL included",
        your_phone=your_phone,
        clean_contact=clean_contact,
        reply_language="arabic",
        reply_url_fragment="albacars.ae/ar",
    )


def test_arabic_name(your_phone, clean_contact):
    """
    This test relies on the WhatsApp display name being Arabic.
    The name cannot be changed programmatically, so this test sends a normal message
    but the WhatsApp contact name on Alba's side should appear as Arabic.
    Note: manually verify the name is Arabic in Respond.io.
    """
    run_test(
        test_name="Arabic — WhatsApp Name",
        message="Hello, I'm interested in your cars.",
        expected_description="AI replies in Arabic due to Arabic contact name",
        your_phone=your_phone,
        clean_contact=clean_contact,
        reply_language="arabic",
    )


def test_ai_fallback(your_phone, clean_contact):
    run_test(
        test_name="AI Fallback",
        message="I need to discuss something very specific about a custom vehicle modification and insurance implications for an imported vehicle with non-standard specs that requires manual evaluation.",
        expected_description="Lifecycle changed to Help Emma, Odoo stage change",
        your_phone=your_phone,
        clean_contact=clean_contact,
        reply_keywords=["moment", "back"],
        odoo_checks={"x_studio_stage_id": "Help Emma"},
    )


def test_uae_number_request(your_phone, clean_contact):
    """
    Simulates a lead coming from a non-UAE number format.
    Note: Since we're sending from a real number, this test works best if your
    number is a non-UAE number. Otherwise adjust the message to make the AI
    suspect a non-UAE context.
    """
    run_test(
        test_name="UAE Number Request",
        message="Can I come in tonight at 7pm for a test drive?",
        expected_description="AI asks for UAE number to proceed",
        your_phone=your_phone,
        clean_contact=clean_contact,
        reply_keywords=["uae", "number"],
    )
