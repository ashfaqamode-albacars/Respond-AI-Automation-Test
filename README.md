# Alba AI Agent Test Suite (Version 1.0)

Automated QA tool for testing Alba's Respond.io AI agent. Simulates customer WhatsApp messages and asserts AI responses, Respond.io lifecycle changes, and Odoo side effects.

## Architecture

```
pytest (CLI trigger)
    └── Python orchestrator
            ├── Node.js WhatsApp service (whatsapp-web.js) → sends messages as customer
            ├── Respond.io API                             → reads replies, lifecycle, fields
            ├── Odoo JSON-RPC                              → asserts leads, activities
            ├── OpenAI API                                 → semantic fallback check on failed assertions
            ├── Google Sheets (stock)                      → reads live cars for test data
            └── Google Sheets (results)                    → logs pass/fail per test
```

## Prerequisites

- Python 3.10+
- Node.js 18+
- A WhatsApp number (yours) for simulating customer messages
- Credentials for: Respond.io, Odoo, OpenAI, Google Sheets (two service accounts)

## Installation

### 1. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 2. Install Node.js dependencies

```bash
cd node
npm install
```

### 3. Configure credentials

```bash
cp python/config/config.example.yaml python/config/config.yaml
```

Edit `config.yaml` with your actual values (see Configuration Reference below).

### 4. Place Google service account JSON files

- `python/config/sheets_results_sa.json` — read/write access to results sheet
- `python/config/sheets_stock_sa.json` — read-only access to live stock sheet

### 5. First-time WhatsApp setup (one-time QR scan)

```bash
cd node
node whatsapp_service.js
```

Scan the QR code that appears with your WhatsApp. Session is saved to `.wwebjs_auth/` and restored automatically on subsequent runs.

## Running Tests

Start the Node.js WhatsApp service first (in a separate terminal):

```bash
cd node
node whatsapp_service.js
```

Wait for: `WhatsApp client ready. Service is accepting requests on port 3000`

Then in a second terminal run tests from the project root:

```bash
# Full suite
python -m pytest python/tests/ -v

# Isolated tests only
python -m pytest python/tests/test_isolated.py -v

# Sequential flows only
python -m pytest python/tests/test_flows.py -v

# Single test
python -m pytest python/tests/test_isolated.py::test_coming_soon -v
python -m pytest python/tests/test_flows.py::test_book_then_cancel -v
```

After each run, an HTML report is automatically generated at `python/reports/report.html`. Open it in any browser for a detailed view of results including tracebacks and logs per test.

## Project Structure

```
RESPOND AI AUTOMATION TEST/
├── node/
│   ├── whatsapp_service.js       # Express server wrapping whatsapp-web.js
│   ├── package.json
│   └── package-lock.json
├── python/
│   ├── config/
│   │   ├── config.example.yaml   # Template — copy to config.yaml
│   │   ├── config.yaml           # Your credentials (gitignored)
│   │   ├── sheets_results_sa.json
│   │   └── sheets_stock_sa.json
│   ├── reports/
│   │   └── report.html           # Auto-generated after each run (gitignored)
│   ├── tests/
│   │   ├── conftest.py           # Shared fixtures and assert helpers
│   │   ├── test_isolated.py      # ~20 isolated test cases
│   │   └── test_flows.py         # 4 sequential flow tests
│   ├── utils/
│   │   ├── ai_check.py           # OpenAI semantic fallback checker
│   │   ├── config.py             # Config loader
│   │   ├── odoo.py               # Odoo JSON-RPC wrapper
│   │   ├── respond.py            # Respond.io API wrapper
│   │   ├── sheets_results.py     # Results sheet logger
│   │   ├── sheets_stock.py       # Live stock sheet reader
│   │   └── whatsapp.py           # Calls Node.js service to send messages
│   ├── debug_odoo.py             # Standalone Odoo connection tester
│   ├── debug_respond.py          # Standalone Respond.io connection tester
│   └── pytest.ini
├── requirements.txt
└── README.md
```

## Configuration Reference

```yaml
respond:
  api_key: "YOUR_RESPOND_IO_API_KEY"
  inbox_id: "YOUR_INBOX_ID"
  alba_phone: "+971XXXXXXXXX"

odoo:
  url: "https://your-odoo-instance.odoo.com"
  db: "your_db_name"
  username: "your@email.com"
  api_key: "YOUR_ODOO_API_KEY"

sheets:
  results_sheet_id: "YOUR_RESULTS_GOOGLE_SHEET_ID"
  stock_sheet_id: "YOUR_STOCK_GOOGLE_SHEET_ID"
  stock_sheet_name: "Sheet1"
  dev_tab_name: "Single Run Test Cases"  # Tab used when running a single test

whatsapp:
  node_service_url: "http://localhost:3000"
  your_number: "+971XXXXXXXXX"    # Your number — simulates the customer
  alba_number: "+971XXXXXXXXX"    # Alba's WhatsApp number

openai:
  api_key: "YOUR_OPENAI_API_KEY"

timing:
  reply_poll_seconds: 15          # Max wait per poll attempt for AI reply
  odoo_wait_seconds: 60           # Initial wait before querying Odoo
  message_delay_seconds: 2        # Delay between messages in sequential flows
```

## How Each Test Works

1. Python reads live stock sheet if the test requires a specific car
2. Python calls Node.js service to send a WhatsApp message from your number to Alba
3. Python polls Respond.io API every 2 seconds for up to 15 seconds waiting for the AI reply — if no reply is found, it retries up to 2 more times with a 2 second gap between attempts
4. Python asserts reply content, language, and URLs
5. If a keyword assertion fails, OpenAI Structured Outputs is called to semantically evaluate the reply; its `PASS`/`FAIL` becomes the final result for that reply check and is written to AI Notes with confidence
6. Python waits up to 60 seconds then queries Odoo via JSON-RPC to assert side effects — if no lead is found, it retries up to 3 times with a 10 second gap between attempts
7. Python logs the full result row to Google Sheets
8. Python deletes the Respond.io contact to reset for the next test

## Retry Behaviour

Both Respond.io polling and Odoo querying have built-in retries to handle timing variability:

| Step | Poll window | Retries | Gap between retries | Max total wait |
|------|------------|---------|---------------------|----------------|
| Respond.io reply | 15 seconds | 2 | 2 seconds | ~46 seconds |
| Odoo lead lookup | 60 second initial wait | 3 | 10 seconds | ~90 seconds |

## Results Sheet Behaviour

- **Single test run** — results are logged to the `Single Run Test Cases` tab (always the same tab, appended on each single run)
- **Full suite run** — a new tab is automatically created and named by timestamp e.g. `11 May 03:48PM`, keeping each suite run's results separate

## Results Sheet Format

Each test appends one row:

| Column | Description |
|--------|-------------|
| Timestamp | When the test ran |
| Test Name | e.g. `Coming Soon — Callback offered` |
| Message Sent | Exact message(s) sent to Alba |
| Expected Outcome | Human-readable expected result |
| Actual Reply | First 500 chars of AI reply |
| Respond.io Result | Pass/fail detail per Respond.io check |
| Odoo Result | Pass/fail detail per Odoo check |
| Overall | ✅ PASS / ❌ FAIL / ⚠️ PARTIAL |
| AI Notes | OpenAI semantic verdict payload for keyword-miss overrides e.g. `PASS (0.92) - reply conveys callback intent` |

## HTML Report

After every run, `pytest-html` generates a report at `python/reports/report.html`. Open it in any browser. It shows:

- Summary of passed, failed, errors, and duration
- Filterable results table — one row per test
- Expandable rows with full tracebacks, logs, and stdout per test
- Environment info (Python version, platform, pytest version)

The report is overwritten on each run. Historical results are preserved in Google Sheets.

## AI Semantic Check

When a keyword assertion fails, the suite calls OpenAI (`gpt-4o-mini`) using Structured Outputs (`response_format` with strict JSON schema). OpenAI returns `{ pass_fail, confidence, notes }`. The `pass_fail` value is used as the effective result of that reply assertion, and the confidence/notes are written to **AI Notes**.

## Test Cases

### Isolated Tests (`tests/test_isolated.py`)

Each test runs with a fresh Respond.io contact which is deleted after the test completes.

| Test | Message Scenario | Key Assertions |
|------|-----------------|----------------|
| `test_coming_soon` | Ask about a CS car from stock sheet | Reply: callback offered. Odoo: no activity |
| `test_aftercare_pre_form` | Warranty/engine issue message | Reply: form link sent |
| `test_aftercare_post_form` | Already submitted the form | Reply: aftercare WhatsApp link sent |
| `test_not_interested` | Customer leaving UAE | Respond.io: lifecycle = Not Interested |
| `test_job_seeker` | Ask about sales agent position | Respond.io: disqualified, not AI assigned |
| `test_purchase_eligible` | Sell 2022 German GCC car under 40k km | Reply: consignment offered. Odoo: department, activity |
| `test_purchase_leaving_country` | Same + leaving country soon | Odoo: CRM lead created |
| `test_purchase_disqualified` | Sell pre-2015 car | Reply: car not accepted. Odoo: disqualified |
| `test_banking_rep` | Ask about bank/lease reps on site | Reply mentions dedicated finance team |
| `test_callback_requested` | Request a call at specific time | Reply: affirmative. Odoo: call activity |
| `test_appointment_no_time` | Tomorrow but not sure what time | Reply: callback offered to confirm time |
| `test_appointment_far_date` | Book appointment more than 1 week away | Odoo: meeting activity. Reply: callback offered |
| `test_video_request` | Ask for a video of the car | Reply: no videos available |
| `test_price_buffer` | Budget 100k-120k AED | Reply: cars shown from 80k-144k range |
| `test_monthly_budget` | Max 2,000 AED/month for Audi Q5 | Reply: options within monthly budget |
| `test_on_my_way` | I'm on my way | Reply: address + conversation closed |
| `test_arabic_text` | Message sent in Arabic | Reply in Arabic + Arabic URL |
| `test_arabic_name` | Arabic WhatsApp contact name | Reply in Arabic |
| `test_ai_fallback` | Trigger fallback scenario | Respond.io: lifecycle = Help Emma |
| `test_uae_number_request` | Appointment request, non-UAE context | Reply: asks for UAE number |

### Sequential Flow Tests (`tests/test_flows.py`)

Each flow uses the same Respond.io contact throughout. Contact is deleted only after the full flow completes.

| Flow | Steps | Key Assertions |
|------|-------|----------------|
| `test_book_then_cancel` | Book appointment → cancel it | Odoo: meeting created then removed |
| `test_book_then_reschedule` | Book appointment → request 10pm slot | Reply: last slot is 9:30 |
| `test_aftercare_flow` | Report engine issue → say form already submitted | Reply 1: form link. Reply 2: aftercare WhatsApp link |
| `test_purchase_flow` | Offer eligible car → proceed with consignment | Odoo: department = Purchasing, meeting activity |

## Out of Scope (Manual Tests)

- **Dubizzle test** — requires clicking WhatsApp on a Dubizzle listing which triggers a specific flow that cannot be automated
- **Don't double message on assign** — requires a specific pre-existing contact state that is complex to set up programmatically
- **Instagram / Facebook channels** — WhatsApp only is tested

## Adding New Tests

1. Add a new function to `tests/test_isolated.py` or `tests/test_flows.py`
2. Use `run_test()` for isolated tests or follow the flow pattern in `test_flows.py`
3. Define `reply_keywords`, `odoo_checks`, and `odoo_activity_type` as needed
4. Run in isolation first: `python -m pytest python/tests/test_isolated.py::your_test -v`

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `pytest` not recognised | Use `python -m pytest` instead |
| WhatsApp session expired | Delete `.wwebjs_auth/` folder, restart node service, scan QR again |
| Port 3000 already in use | Run `netstat -ano \| findstr :3000` then `taskkill /PID <pid> /F` |
| Cannot connect to Node.js service | Ensure `node whatsapp_service.js` is running before pytest |
| Reply poll timeout after retries | AI consistently taking too long. Check Respond.io manually. Increase `timing.reply_poll_seconds` in config |
| Odoo assertion fails after retries | Increase `timing.odoo_wait_seconds`. Default is 60s |
| Contact not deleted after crash | Manually delete the contact in Respond.io for your number before re-running |
| Odoo authentication failed | Verify `odoo.db`, `odoo.username`, and `odoo.api_key` in config.yaml |
| Google Sheets 403 error | Share the sheet with the service account email from the SA JSON file |
| New tab not created on full suite run | Check that the service account has Editor access on the results spreadsheet |
| HTML report not generated | Make sure `python/reports/` folder exists — create it manually if needed |