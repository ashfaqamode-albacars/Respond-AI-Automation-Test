import os
from datetime import datetime
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from .config import load_config

_service = None

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SA_PATH = os.path.join(os.path.dirname(__file__), "../config/sheets_results_sa.json")

HEADERS = [
    "Timestamp",
    "Test Name",
    "Message Sent",
    "Expected Outcome",
    "Actual Reply",
    "Respond.io Result",
    "Odoo Result",
    "Overall",
    "AI Notes",    
]


def _get_service():
    global _service
    if _service:
        return _service
    creds = Credentials.from_service_account_file(SA_PATH, scopes=SCOPES)
    _service = build("sheets", "v4", credentials=creds)
    return _service


def ensure_headers():
    """Write header row if the sheet is empty."""
    cfg = load_config()
    sheet_id = cfg["sheets"]["results_sheet_id"]
    svc = _get_service()

    result = (
        svc.spreadsheets()
        .values()
        .get(spreadsheetId=sheet_id, range="A1:H1")
        .execute()
    )

    if not result.get("values"):
        svc.spreadsheets().values().update(
            spreadsheetId=sheet_id,
            range="A1",
            valueInputOption="RAW",
            body={"values": [HEADERS]},
        ).execute()


def log_result(
    test_name: str,
    message_sent: str,
    expected: str,
    actual_reply: str,
    respond_result: str,
    odoo_result: str,
    overall: str,
    ai_notes="" 
):
    """Append one result row to the Google Sheet."""
    cfg = load_config()
    sheet_id = cfg["sheets"]["results_sheet_id"]

    row = [
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        test_name,
        message_sent,
        expected,
        actual_reply or "",
        respond_result,
        odoo_result,
        overall,
        ai_notes
    ]

    _get_service().spreadsheets().values().append(
        spreadsheetId=sheet_id,
        range="A1",
        valueInputOption="RAW",
        insertDataOption="INSERT_ROWS",
        body={"values": [row]},
    ).execute()


def log_pass(test_name: str, message_sent: str, expected: str, actual_reply: str,
             respond_detail: str = "PASS", odoo_detail: str = "PASS", ai_notes=""):
    log_result(test_name, message_sent, expected, actual_reply,
               respond_detail, odoo_detail, "✅ PASS", ai_notes=ai_notes)


def log_fail(test_name: str, message_sent: str, expected: str, actual_reply: str,
             respond_detail: str = "", odoo_detail: str = "", ai_notes=""):
    log_result(test_name, message_sent, expected, actual_reply,
               respond_detail, odoo_detail, "❌ FAIL", ai_notes=ai_notes)


def log_partial(test_name: str, message_sent: str, expected: str, actual_reply: str,
                respond_detail: str = "", odoo_detail: str = "", ai_notes=""):
    log_result(test_name, message_sent, expected, actual_reply,
               respond_detail, odoo_detail, "⚠️ PARTIAL", ai_notes=ai_notes)
