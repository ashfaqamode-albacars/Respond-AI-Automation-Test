# Alba AI Agent Test Suite

Automated QA tool for testing Alba's Respond.io AI agent. Simulates customer WhatsApp messages and asserts AI responses, Respond.io lifecycle changes, and Odoo side effects.

## Architecture

```
pytest (CLI trigger)
    └── Python orchestrator
            ├── Node.js WhatsApp service (whatsapp-web.js) → sends messages as customer
            ├── Respond.io API                             → reads replies, lifecycle, fields
            ├── Odoo JSON-RPC                              → asserts leads, activities
            ├── Google Sheets (stock)                      → reads live cars for test data
            └── Google Sheets (results)                    → logs pass/fail per test
```

## Prerequisites

- Python 3.10+
- Node.js 18+
- A WhatsApp number (yours) for simulating customer messages
- Credentials for: Respond.io, Odoo, Google Sheets (two service accounts)

## Installation

### 1. Clone and install Python dependencies

```bash
cd alba-test-suite
pip install -r requirements.txt
```

### 2. Install Node.js dependencies

```bash
cd node
npm install
```

### 3. Configure credentials

Copy the example config and fill in your credentials:

```bash
cp python/config/config.example.yaml python/config/config.yaml
```

Edit `config.yaml` with your actual values (see Configuration section below).

### 4. Place Google service account JSON files

- `python/config/sheets_results_sa.json` — your account, read/write access to results sheet
- `python/config/sheets_stock_sa.json`   — read-only access to live stock sheet

### 5. First-time WhatsApp setup (one-time QR scan)

```bash
cd node
node whatsapp_service.js
```

Scan the QR code that appears with your WhatsApp. Session is saved locally — you won't need to scan again unless the session expires.

## Running Tests

Start the Node.js WhatsApp service first (in a separate terminal):

```bash
cd node
node whatsapp_service.js
```

Then in another terminal, run the full test suite:

```bash
cd python
pytest tests/ -v
```

Run a specific test:

```bash
pytest tests/test_isolated.py::test_coming_soon -v
pytest tests/test_flows.py::test_book_then_cancel -v
```

Run by category:

```bash
pytest tests/test_isolated.py -v
pytest tests/test_flows.py -v
```

## Project Structure

```
RESPOND AI AUTOMATION TEST/
├── node/
│   ├── whatsapp_service.js
│   └── package.json
├── python/
│   ├── config/
│   │   └── config.example.yaml
│   ├── tests/
│   │   ├── conftest.py          ← move here from root
│   │   ├── test_isolated.py
│   │   └── test_flows.py
│   ├── utils/
│   │   ├── config.py
│   │   ├── odoo.py
│   │   ├── respond.py
│   │   ├── sheets_results.py
│   │   ├── sheets_stock.py
│   │   └── whatsapp.py
│   └── pytest.ini               ← move here from root
├── requirements.txt
└── README.md
```

## Configuration Reference

```yaml
# python/config/config.yaml

respond:
  api_key: "YOUR_RESPOND_IO_API_KEY"
  inbox_id: "YOUR_INBOX_ID"           # WhatsApp inbox ID in Respond.io
  alba_phone: "+971XXXXXXXXX"         # Alba's WhatsApp number

odoo:
  url: "https://your-odoo-instance.com"
  db: "your_db_name"
  username: "your@email.com"
  api_key: "YOUR_ODOO_API_KEY"

sheets:
  results_sheet_id: "YOUR_RESULTS_GOOGLE_SHEET_ID"
  stock_sheet_id: "YOUR_STOCK_GOOGLE_SHEET_ID"
  stock_sheet_name: "Sheet1"           # Tab name in stock sheet

whatsapp:
  node_service_url: "http://localhost:3000"
  your_number: "+971XXXXXXXXX"         # Your number (customer simulator)
  alba_number: "+971XXXXXXXXX"         # Alba's WhatsApp number

timing:
  reply_poll_seconds: 15               # Max wait for AI reply
  odoo_wait_seconds: 60                # Wait before querying Odoo
  message_delay_seconds: 2             # Delay between messages in flows
```

## How Each Test Works

1. Python reads stock sheet if test needs a car
2. Python calls Node.js to send WhatsApp message from your number to Alba
3. Python polls Respond.io API every 2 seconds for up to 15 seconds waiting for AI reply
4. Python asserts reply content, language, URLs
5. Python waits 60 seconds then queries Odoo to assert side effects
6. Python logs result row to Google Sheets
7. Python deletes Respond.io contact (resets for next test)

## Test Cases

### Isolated Tests (`tests/test_isolated.py`)

| Test | Scenario |
|------|----------|
| `test_coming_soon` | Ask about a CS car — callback offered, no Odoo activity |
| `test_aftercare_pre_form` | Warranty issue — form link sent |
| `test_aftercare_post_form` | Already submitted form — aftercare WhatsApp link sent |
| `test_not_interested` | Customer leaving UAE — lifecycle = Not Interested |
| `test_job_seeker` | Asking about sales job — disqualified, not AI assigned |
| `test_purchase_eligible` | Sell eligible German car — consignment, Odoo lead |
| `test_purchase_leaving_country` | Same + leaving UAE — CRM lead created |
| `test_purchase_disqualified` | Sell pre-2015 car — rejected |
| `test_banking_rep` | Ask about bank reps — finance team reply |
| `test_callback_requested` | Request call at specific time — Odoo activity |
| `test_appointment_no_time` | Tomorrow but no time — callback to confirm |
| `test_appointment_far_date` | Book >1 week out — booked + callback offered |
| `test_video_request` | Ask for car video — no videos reply |
| `test_price_buffer` | Budget 100k-120k — cars shown from 80k-144k range |
| `test_monthly_budget` | Max 2000/month — options within budget |
| `test_on_my_way` | On my way — address reply, conversation closed |
| `test_arabic_text` | Message in Arabic — Arabic reply + Arabic URL |
| `test_arabic_name` | Arabic WhatsApp name — Arabic reply |
| `test_ai_fallback` | Trigger fallback — lifecycle = Help Emma |
| `test_uae_number_request` | Non-UAE number format — AI asks for UAE number |

### Sequential Flow Tests (`tests/test_flows.py`)

| Flow | Steps |
|------|-------|
| `test_book_then_cancel` | Book appointment → cancel it |
| `test_book_then_reschedule` | Book appointment → reschedule (9:30 last slot edge case) |
| `test_aftercare_flow` | Send warranty issue → follow up saying already submitted form |
| `test_purchase_flow` | Send eligible car details → proceed with consignment |

## Results Sheet Format

Each test logs one row:

| Timestamp | Test Name | Message Sent | Expected | Actual Reply | Respond.io | Odoo | Overall |
|-----------|-----------|--------------|----------|--------------|------------|------|---------|

## Adding New Tests

1. Add a test function to `tests/test_isolated.py` or `tests/test_flows.py`
2. Use the helpers from `utils/` — see existing tests for patterns
3. Define expected outcomes as a dict and pass to `assert_respond()` and `assert_odoo()`

## Troubleshooting

**WhatsApp session expired** — re-run `node whatsapp_service.js` and scan the QR code again.

**Reply poll timeout** — the AI took longer than 15 seconds. Check Respond.io manually. You can increase `timing.reply_poll_seconds` in config.

**Odoo assertion fails but action happened** — increase `timing.odoo_wait_seconds`. Some actions take longer to sync.

**Contact not deleted** — if a test crashes mid-run, the contact may remain. Delete it manually in Respond.io before re-running.
