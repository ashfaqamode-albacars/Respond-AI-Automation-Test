# Alba AI Agent Test Suite (Version 2)

Config-driven automated QA tool for testing Alba's Respond.io AI agent. Define tests in YAML, run with pytest. No Python required to add new test cases.

## Architecture

```
pytest (CLI trigger)
    └── test_suite.py (discovers tests from YAML)
            └── test_runner.py (executes each test)
                    ├── message_generator.py          → generates customer messages via OpenAI
                    ├── Node.js WhatsApp service       → sends messages via whatsapp-web.js
                    ├── Respond.io API                 → reads replies, lifecycle, fields
                    ├── ai_check.py                    → semantic fallback when keywords fail
                    ├── Odoo JSON-RPC                  → asserts leads, activities
                    ├── Google Sheets (stock)           → reads live cars for test data
                    └── Google Sheets (results)         → logs pass/fail per test
```

## What Changed in v2

- **Tests are defined in YAML** — no more writing Python to add a test case
- **Customer messages can be AI-generated** — provide a prompt and OpenAI writes a natural WhatsApp message, or provide a fixed message
- **Single test runner** — `test_suite.py` replaces `test_isolated.py` and `test_flows.py`
- **Data sources are declarative** — specify `data_source: "coming_soon_car"` in YAML instead of calling functions
- **Everything else is the same** — same Respond.io, Odoo, Sheets, WhatsApp infrastructure

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

Scan the QR code with your WhatsApp. Session is saved to `.wwebjs_auth/` and restored automatically.

## Running Tests

Start the Node.js WhatsApp service first (in a separate terminal):

```bash
cd node
node whatsapp_service.js
```

Wait for: `WhatsApp client ready. Service is accepting requests on port 3000`

Then in a second terminal from the project root:

```bash
# Full suite
python -m pytest python/tests/test_suite.py -v

# Only isolated tests
python -m pytest python/tests/test_suite.py::test_isolated -v

# Only flow tests
python -m pytest python/tests/test_suite.py::test_flow -v

# Single test by name
python -m pytest python/tests/test_suite.py::test_isolated[Coming\ Soon\ —\ Callback\ offered] -v
```

After each run, an HTML report is generated at `python/reports/report.html`.

## Project Structure

```
RESPOND AI AUTOMATION TEST/
├── node/
│   ├── whatsapp_service.js          # Express server wrapping whatsapp-web.js
│   ├── package.json
│   └── package-lock.json
├── python/
│   ├── config/
│   │   ├── config.example.yaml      # Template — copy to config.yaml
│   │   ├── config.yaml              # Your credentials (gitignored)
│   │   ├── test_cases.yaml          # ★ All test definitions live here
│   │   ├── test_cases_examples.yaml # Reference showing all available options
│   │   ├── sheets_results_sa.json
│   │   └── sheets_stock_sa.json
│   ├── reports/
│   │   └── report.html              # Auto-generated after each run (gitignored)
│   ├── tests/
│   │   ├── conftest.py              # Shared fixtures and helpers
│   │   └── test_suite.py            # ★ Discovers and runs tests from YAML
│   ├── utils/
│   │   ├── ai_check.py              # OpenAI semantic fallback checker
│   │   ├── config.py                # Config loader
│   │   ├── message_generator.py     # ★ Generates customer messages via OpenAI
│   │   ├── odoo.py                  # Odoo JSON-RPC wrapper
│   │   ├── respond.py               # Respond.io API wrapper
│   │   ├── sheets_results.py        # Results sheet logger
│   │   ├── sheets_stock.py          # Live stock sheet reader
│   │   ├── test_runner.py           # ★ Config-driven test execution engine
│   │   └── whatsapp.py              # Calls Node.js service to send messages
│   ├── debug_odoo.py                # Standalone Odoo connection tester
│   ├── debug_respond.py             # Standalone Respond.io connection tester
│   └── pytest.ini
├── requirements.txt
└── README.md
```

Files marked with ★ are new or changed in v2.

## Adding a New Test

Open `python/config/test_cases.yaml` and add a YAML block. No Python needed.

### Simplest possible test (3 lines):

```yaml
- name: "Video Request"
  fixed_message: "Can I have a video of the car?"
  expected: "AI says no videos available"
```

### Test with AI-generated message from stock data:

```yaml
- name: "Coming Soon Car"
  prompt: "Ask about this coming soon car and whether it's available"
  expected: "Reply should mention a callback"
  keywords: ["callback", "call"]
  data_source: "coming_soon_car"
```

### Test with Odoo assertions:

```yaml
- name: "Callback Requested"
  fixed_message: "Can you call me today at 3pm?"
  expected: "AI confirms callback, Odoo creates call activity"
  keywords: ["call"]
  odoo_checks:
    - "x_studio_stage_id: New"
  odoo_activity: "Phone Call"
```

### Multi-step flow:

```yaml
flows:
  - name: "Book then Cancel"
    data_source: "available_car"
    steps:
      - prompt: "Book an appointment to see this car tomorrow at 2pm"
        expected: "Appointment confirmed"
        keywords: ["appointment"]
      - fixed_message: "Cancel my appointment"
        expected: "Appointment cancelled"
        keywords: ["cancel"]
    odoo_checks:
      - "meeting_removed: true"
```

See `test_cases_examples.yaml` for the full reference of every available field and option.

## Test Case YAML Reference

### Fields for isolated tests

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Display name for reporting |
| `fixed_message` | One of these | Exact message to send |
| `prompt` | One of these | Instruction for AI to generate a message |
| `expected` | Yes | What the reply should convey (used for AI semantic check) |
| `keywords` | No | Fast keyword check — list of strings the reply should contain |
| `reply_language` | No | `"english"` (default) or `"arabic"` |
| `reply_url` | No | URL fragment that should appear in the reply |
| `data_source` | No | Stock sheet function to call for car data |
| `data_params` | No | Parameters for the data source |
| `odoo_checks` | No | List of `"field: expected_value"` strings |
| `odoo_activity` | No | Activity type name to check for (e.g. `"Meeting"`) |
| `no_odoo_activity` | No | If `true`, assert no activities exist |

### Fields for flow tests

Same as isolated, plus:

| Field | Required | Description |
|-------|----------|-------------|
| `steps` | Yes | List of step objects (each has `fixed_message`/`prompt`, `expected`, `keywords`) |
| `data_source` | No | Shared across all steps in the flow |
| `odoo_checks` | No | Checked after all steps complete |
| `odoo_activity` | No | Checked after all steps complete |

### Available data sources

| Value | Returns |
|-------|---------|
| `coming_soon_car` | First car with status CS from stock sheet |
| `available_car` | First car with status AV from stock sheet |
| `eligible_purchase_car` | Hardcoded eligible German car (2022 BMW 530i) |
| `disqualified_purchase_car` | Hardcoded pre-2015 car (2014 Toyota Corolla) |
| `price_range` | First AV car in price range (requires `data_params: {min_price, max_price}`) |
| `monthly_budget` | First AV car within monthly budget (requires `data_params: {max_monthly}`) |

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
  dev_tab_name: "Single Run Test Cases"

whatsapp:
  node_service_url: "http://localhost:3000"
  your_number: "+971XXXXXXXXX"
  alba_number: "+971XXXXXXXXX"

openai:
  api_key: "YOUR_OPENAI_API_KEY"

timing:
  reply_poll_seconds: 15
  odoo_wait_seconds: 60
  message_delay_seconds: 2
```

## How Each Test Works

1. Test runner reads the test definition from `test_cases.yaml`
2. If `data_source` is specified, car data is fetched from the live stock sheet
3. If `prompt` is provided (no `fixed_message`), OpenAI generates a natural customer message using the prompt and car data as context
4. Message is sent to Alba via WhatsApp (Node.js service)
5. Respond.io API is polled for the AI reply (up to 15 seconds per attempt, 2 retries)
6. Keywords are checked first (fast pass). If keywords fail, OpenAI evaluates the reply semantically against the `expected` description
7. Language check and URL check run if specified
8. After a 60 second wait, Odoo is queried for lead and activity assertions (3 retries with 10 second gaps)
9. Result is logged to Google Sheets
10. Contact is deleted from Respond.io to reset for the next test

## Results Sheet Behaviour

- **Single test run** — results logged to the `Single Run Test Cases` tab
- **Full suite run** — a new tab is created named by timestamp e.g. `11 May 03:48PM`

## Results Sheet Format

| Column | Description |
|--------|-------------|
| Timestamp | When the test ran |
| Test Name | From the `name` field in YAML |
| Message Sent | Exact message (fixed or AI-generated) |
| Expected Outcome | From the `expected` field in YAML |
| Actual Reply | First 500 chars of AI reply |
| Respond.io Result | Pass/fail detail per check |
| Odoo Result | Pass/fail detail per check |
| Overall | ✅ PASS / ❌ FAIL |
| AI Notes | Semantic verdict when keyword checks fail |

## HTML Report

After every run, `pytest-html` generates `python/reports/report.html` with a summary, filterable results table, and expandable tracebacks per test. Overwritten each run — historical results are preserved in Google Sheets.

## AI Semantic Check

When a keyword assertion fails, OpenAI (`gpt-4o-mini`) evaluates whether the reply semantically satisfies the `expected` description. Returns `SEMANTICALLY_PASS` or `SEMANTICALLY_FAIL` with a one-sentence explanation. Written to the **AI Notes** column. The overall result remains `❌ FAIL` — the AI check is informational only.

## AI Message Generation

When a test uses `prompt` instead of `fixed_message`, OpenAI generates a natural customer WhatsApp message. The prompt and any car data from the stock sheet are passed as context. This means each test run may send a slightly different message, making the tests more realistic. The exact message sent is always logged to the sheet for traceability.

## Retry Behaviour

| Step | Poll window | Retries | Gap between retries | Max total wait |
|------|------------|---------|---------------------|----------------|
| Respond.io reply | 15 seconds | 2 | 2 seconds | ~46 seconds |
| Odoo lead lookup | 60 second initial wait | 3 | 10 seconds | ~90 seconds |

## Out of Scope (Manual Tests)

- **Dubizzle test** — requires browser interaction with Dubizzle listing
- **Don't double message on assign** — requires specific pre-existing contact state
- **Instagram / Facebook channels** — WhatsApp only

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `pytest` not recognised | Use `python -m pytest` instead |
| WhatsApp session expired | Delete `.wwebjs_auth/`, restart node service, scan QR |
| Port 3000 already in use | `netstat -ano \| findstr :3000` then `taskkill /PID <pid> /F` |
| Cannot connect to Node.js service | Ensure `node whatsapp_service.js` is running first |
| Reply poll timeout after retries | Increase `timing.reply_poll_seconds` in config |
| Odoo assertion fails after retries | Increase `timing.odoo_wait_seconds` |
| Contact not deleted after crash | Manually delete in Respond.io before re-running |
| Odoo authentication failed | Check `odoo.db`, `odoo.username`, `odoo.api_key` |
| Google Sheets 403 | Share the sheet with the service account email |
| New tab not created | Service account needs Editor access on results sheet |
| HTML report not generated | Create `python/reports/` folder manually |
| AI message generation fails | Check `openai.api_key` in config |
| Test not found by name | Escape spaces in test name: `Coming\ Soon\ —\ Callback\ offered` |