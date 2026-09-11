# Bill Tracker v3 — Plan

## Overview

A Python package + Hermes skill that:
1. Scans a specific Gmail account daily for new bills AND receipts
2. Parses vendor, amount, due date (bills) or payment date (receipts) from email content
3. Classifies each email as a bill, receipt, or neither
4. Stores structured data in JSON files (bills and receipts in separate collections)
5. Auto-matches receipts to unpaid bills (marks them paid)
6. Generates a report on the 15th of each month (bill payment day)
7. Runs via Hermes cron on the iomarchy server

## What's wrong with v2 (why we're starting fresh)

The archived v2 has fundamental issues:
- **Amount parsing is broken** — regex patterns are too greedy, producing garbage values like `$500011710993.00` for Enercare and `$1684.00` for OpenRouter (likely picking up receipt numbers or invoice IDs instead of actual amounts)
- **Vendor detection is fragile** — simple keyword matching with no context awareness
- **Due date is hardcoded** — always `today + 14 days`, never extracted from the actual email
- **No receipt support** — the separate `mark_paid.py` script tried to scan receipt emails with more fragile regex, but had no integration with the bill scanner and no matching logic
- **No email classification** — promotional emails, account notices, and actual bills all got parsed the same way
- **No LLM-assisted parsing** — pure regex on messy HTML email bodies
- **Tightly coupled to a custom `GmailClient`** that lives in the workspace scripts directory
- **No tests, no package structure, no config file** — hardcoded paths everywhere

## Architecture

```
bill-tracker/                          # v3 branch of existing repo, clean start
├── pyproject.toml                     # Package metadata, dependencies, CLI entry points
├── README.md
├── SKILL.md                           # Hermes skill definition
├── config.example.yaml                # Template — user copies to config.yaml
├── config.yaml                        # User config (gitignored, not committed)
├── report.yaml                        # Report structure + delivery rules
├── vendors.yaml                       # Known + discovered vendors
├── src/
│   └── bill_tracker/
│       ├── __init__.py
│       ├── cli.py                     # CLI: scan, report, mark-paid, list
│       ├── scanner.py                 # Gmail scanning via Hermes Gmail tool
│       ├── classifier.py              # LLM: classify email as bill | receipt | neither
│       ├── parser.py                  # LLM-assisted extraction (bill or receipt fields)
│       ├── matcher.py                 # Match receipts to unpaid bills
│       ├── store.py                   # JSON file read/write (bills, receipts)
│       ├── reporter.py                # Report generation from report.yaml config
│       ├── vendors.py                 # Vendor config loading, matching, auto-discovery
│       └── models.py                  # Pydantic models (Bill, Receipt, Vendor, Report)
├── data/                              # Runtime data (gitignored)
│   ├── bills.json
│   └── receipts.json
├── reports/                           # Generated reports
│   └── bill-tracker-report-2026-09-15.md
└── tests/
    ├── test_scanner.py
    ├── test_classifier.py
    ├── test_parser.py
    ├── test_matcher.py
    ├── test_store.py
    └── test_reporter.py
```

## Key Design Decisions

### 1. LLM-assisted classification + parsing (the core improvement over v2)

The scanner pipeline has two LLM steps per email:

**Step A — Classify:** Is this email a bill, a receipt, or neither?
```
Classify this email. Return JSON:
{type: "bill" | "receipt" | "neither", confidence: 0.0-1.0, reason: string}
```
Emails classified as "neither" are skipped. This prevents the parser from hallucinating bills out of promotional emails, newsletters, or account notices.

**Step B — Parse:** Extract structured data depending on type.

For **bills**:
```
Extract bill information. Return JSON:
{vendor: string, amount: number, dueDate: "YYYY-MM-DD" | null, currency: "CAD"|"USD"|null}
```

For **receipts**:
```
Extract receipt information. Return JSON:
{vendor: string, amount: number, paymentDate: "YYYY-MM-DD" | null, currency: "CAD"|"USD"|null, paymentMethod: "credit"|"debit"|"transfer"|"unknown"|null}
```

Both steps use a **cheap LLM** (e.g., `google/gemini-3-flash-preview`) to keep token costs minimal. The classifier runs first to avoid spending parse tokens on non-bill/non-receipt emails.

### 2. JSON file storage (not MongoDB)

Per your preference. Two collections:

**`data/bills.json`** — bills (money owed):
```json
{
  "version": 3,
  "lastUpdated": "2026-09-11T12:00:00Z",
  "bills": [
    {
      "id": "enbridge-2026-09",
      "vendor": "Enbridge Gas",
      "amount": 92.45,
      "currency": "CAD",
      "dueDate": "2026-09-28",
      "receivedDate": "2026-09-10",
      "paid": false,
      "paidDate": null,
      "receiptId": null,
      "emailId": "abc123",
      "emailSubject": "Your Enbridge bill is ready",
      "category": "utilities",
      "notes": ""
    }
  ]
}
```

**`data/receipts.json`** — receipts (proof of payment):
```json
{
  "version": 3,
  "lastUpdated": "2026-09-11T12:00:00Z",
  "receipts": [
    {
      "id": "enbridge-2026-09-15",
      "vendor": "Enbridge Gas",
      "amount": 92.45,
      "currency": "CAD",
      "paymentDate": "2026-09-15",
      "paymentMethod": "credit",
      "emailId": "def456",
      "emailSubject": "Payment confirmation",
      "matchedBillId": "enbridge-2026-09",
      "category": "utilities",
      "notes": ""
    }
  ]
}
```

The `receiptId` on a bill and `matchedBillId` on a receipt link the two together. When a receipt is matched to a bill, the bill is marked `paid: true` with `paidDate` set to the receipt's payment date.

### 3. Hermes Gmail tool (no custom auth)

Hermes has a built-in `gmail` tool. The skill will instruct Hermes to use it to search for and read bill/receipt emails. The Python package will accept email text as input (via stdin or CLI args) rather than doing its own Gmail auth. This means:

- **Hermes cron job**: "Search Gmail for bills and receipts from the last 24 hours, extract the text, and pipe it to `bill-tracker scan`"
- **Manual**: `bill-tracker scan --email-text "..."` for testing

The Python package itself has zero Gmail dependencies — it's a pure classifier + parser + store + reporter.

### 4. Receipt matching (auto-mark-paid)

When a receipt is parsed, the matcher tries to link it to an unpaid bill:

1. **Vendor match** — receipt vendor must match a bill vendor (via vendor aliases)
2. **Amount match** — receipt amount ≈ bill amount (within a small tolerance, e.g., ±$0.50, to handle rounding)
3. **Date ordering** — receipt payment date must be on/after the bill's received date

If a unique match is found, the bill is marked paid automatically. If multiple candidates match, the receipt is stored unmatched and flagged for manual review. If no bill matches, the receipt is stored standalone (e.g., a one-off purchase with no prior bill).

This replaces v2's `mark_paid.py` with a deterministic, testable matching step rather than regex-based receipt scanning.

### 4. Vendor configuration

Ported and improved from v2's `vendors.json`:

```yaml
# config/vendors.yaml
vendors:
  - name: Enbridge Gas
    patterns: ["enbridge", "enbridge gas"]
    category: utilities
    currency: CAD
    expected_range: [25, 180]

  - name: NPEI Electricity
    patterns: ["npei", "niagara peninsula energy", "niagara energy"]
    category: utilities
    currency: CAD
    expected_range: [35, 220]

  - name: OpenRouter
    patterns: ["openrouter", "openrouter.ai"]
    category: ai
    currency: USD
    expected_range: [5, 200]
    # LLM hint: receipt numbers often look like large dollar amounts — ignore 4+ digit numbers near "receipt" or "invoice #"
    parser_hint: "Ignore numbers that look like receipt/invoice IDs. The actual charge is usually a smaller amount near words like 'charged', 'total', or '$'."

  # ... etc
```

The `parser_hint` field is new — it gets injected into the LLM prompt for vendors that have known parsing pitfalls.

### 5. CLI design

```bash
# Scan: read email text from stdin, classify, parse, store
echo "$EMAIL_BODY" | bill-tracker scan --subject "$SUBJECT" --email-id "$ID"

# Report: generate markdown report
bill-tracker report                    # all unpaid bills + recent receipts
bill-tracker report --month 2026-09    # specific month
bill-tracker report --format html      # HTML output

# Mark paid manually (for unmatched receipts or manual payments)
bill-tracker mark-paid --bill-id "enbridge-2026-09" --date 2026-09-15

# List
bill-tracker list                      # all bills
bill-tracker list --unpaid             # unpaid only
bill-tracker list --vendor enbridge    # filter by vendor
bill-tracker list --receipts           # all receipts
bill-tracker list --unmatched          # receipts with no matching bill

# Vendors
bill-tracker vendors                   # list known vendors
```

### 6. Hermes skill (SKILL.md)

The skill tells Hermes how to orchestrate the daily scan:

```markdown
---
name: bill-tracker
description: Scan Gmail for bills and receipts, track payments, generate reports
---

# Bill Tracker

## Daily Scan
1. Use the Gmail tool to search for bills:
   `newer_than:1d (bill OR invoice OR due OR statement)`
2. Use the Gmail tool to search for receipts:
   `newer_than:1d (receipt OR "payment confirmation" OR "thank you for your payment" OR "paid")`
3. For each result from both searches, get the full message content
4. Pipe subject + body to: `bill-tracker scan --subject "..." --email-id "..."` via stdin
5. Report new bills found AND any receipts that were auto-matched to bills

## 15th of Month Report
1. Run `bill-tracker report`
2. Send the output to the user via Telegram
3. The report includes: unpaid bills table, recently paid bills, unmatched receipts
4. Ask which bills to mark as paid (for any you paid outside tracked receipts)
```

### 7. Cron jobs (in Hermes)

```
# Daily scan at 8 PM EST — checks for both bills and receipts
hermes cron create "every 1d at 20:00 America/New_York" \
  "Run the bill-tracker daily scan skill to check for new bills and receipts" \
  --skill bill-tracker --deliver telegram

# 15th of month report at 9 AM EST
hermes cron create "0 9 15 * * America/New_York" \
  "Run bill-tracker report for all unpaid bills, recent receipts, and unmatched items" \
  --skill bill-tracker --deliver telegram
```

## Implementation Phases

### Phase 1: Package skeleton + models + store
- `pyproject.toml` with dependencies (pydantic, pyyaml, rich for CLI)
- `models.py` — Pydantic models for Bill, Receipt, Vendor, Report
- `store.py` — JSON read/write for both bills.json and receipts.json with atomic writes
- `vendors.py` — Load, match, and auto-discover vendor config
- `config.py` — Load config.yaml with defaults, no hardcoded values
- Tests for store, models, vendors, and config

### Phase 2: Classifier + Parser (LLM-assisted)
- `classifier.py` — LLM prompt to classify email as bill | receipt | neither
- `parser.py` — LLM prompt to extract fields depending on classification
- Prompt templates with vendor hints for tricky parsers (e.g., OpenRouter)
- Validation against vendor list and expected ranges
- Tests with sample bill and receipt emails

### Phase 3: Matcher + CLI
- `matcher.py` — Match receipts to unpaid bills (vendor + amount ± tolerance + date ordering)
- `cli.py` — All commands: scan, list, report, mark-paid, vendors
- `scanner.py` — Orchestrates classify → parse → validate → match → store
- `reporter.py` — Report generation driven by report.yaml (sections, filters, delivery)

### Phase 4: Hermes integration
- `SKILL.md` — Instructions for Hermes (dual Gmail searches, scan pipeline, Telegram payment flow)
- `config.example.yaml` — Template for new users
- Test end-to-end with Hermes Gmail tool

### Phase 5: Cron setup + live test
- Deploy to iomarchy
- Create cron jobs (daily scan + 15th report)
- Run first deep scan, verify results
- Run first report, verify output
- Test Telegram payment flow

## Open Questions (answered)

1. **Gmail account**: `1boss.ac.bot1@gmail.com` — configurable in `config.yaml`, not hardcoded.
2. **Vendor list**: Start with the 8 from v2, but the system **auto-discovers** new vendors from emails. Any vendor found in a bill that's not in the known list gets added to a `discovered` section. The user can promote discovered vendors to known (which adds parser hints, categories, expected ranges).
3. **Report delivery**: Both Telegram + file. Report format is driven by a structured `report.yaml` config — sections, sorting, filters, delivery targets. Extensible by anyone with Hermes.
4. **Payment marking**: Interactive Telegram flow — on the 15th, Hermes sends the report and asks "Pay all these? Mark as paid?" User confirms, bills get marked.
5. **Historical data**: Fresh scan from Gmail, processed with the latest parser. No old JSON import.
6. **Repo**: `v3` branch in the existing `bill-tracker` repo. Start empty, this plan as first commit.
7. **Portability**: The whole system should work for anyone with Hermes + a Gmail account + `config.yaml`. No hardcoded paths, accounts, or vendor assumptions that can't be overridden in config.

---

## Additional Design Decisions (from answers)

### 8. Config-driven architecture

Everything configurable lives in `config.yaml`. No hardcoded values anywhere in Python:

```yaml
# config.yaml — user-editable, checked into repo as config.example.yaml

gmail:
  account: "1boss.ac.bot1@gmail.com"
  search_window: "1d"                # how far back to scan
  bill_query: "bill OR invoice OR due OR statement"
  receipt_query: "receipt OR \"payment confirmation\" OR \"thank you for your payment\""

storage:
  data_dir: "./data"                 # where bills.json and receipts.json live

matching:
  amount_tolerance: 0.50             # ±$0.50 for receipt-to-bill matching
  confidence_threshold: 0.7          # min classifier confidence to accept

parser:
  model: "google/gemini-3-flash-preview"  # cheap model for extraction
  max_tokens: 200
```

### 9. Vendor auto-discovery

The system starts with 8 known vendors (from v2). When a bill email is classified and parsed:

1. The extracted vendor name is checked against known vendors (by name + aliases)
2. If no match, a **discovered** vendor entry is created in `vendors.yaml`:
   ```yaml
   discovered:
     - name: "New Vendor Name"
       first_seen: "2026-09-11"
       occurrences: 1
       sample_amount: 45.00
       sample_currency: "CAD"
   ```
3. The bill is stored with `vendor: "New Vendor Name"` and `category: "uncategorized"`
4. On the report, discovered vendors are flagged so the user can promote them to known
5. Promoting adds `patterns`, `category`, `expected_range`, and optional `parser_hint`

This means the vendor list grows organically without upfront configuration.

### 10. Extensible report configuration

Reports are driven by `report.yaml`, not hardcoded:

```yaml
# report.yaml — defines report structure, sortable/extendable

sections:
  - id: unpaid_bills
    title: "Unpaid Bills"
    filter: "unpaid:true"
    sort: "dueDate:asc"
    columns: [vendor, amount, dueDate, daysLate, category]
    delivery: [telegram, file]

  - id: recently_paid
    title: "Recently Paid (This Month)"
    filter: "paid:true paidDate:this-month"
    sort: "paidDate:desc"
    columns: [vendor, amount, paidDate, paymentMethod]
    delivery: [telegram, file]

  - id: unmatched_receipts
    title: "Unmatched Receipts (Needs Review)"
    filter: "matched:false"
    sort: "paymentDate:desc"
    columns: [vendor, amount, paymentDate, emailSubject]
    delivery: [telegram, file]

  - id: discovered_vendors
    title: "New Vendors Detected"
    filter: "category:uncategorized"
    sort: "receivedDate:desc"
    columns: [vendor, amount, receivedDate]
    delivery: [telegram]

output:
  formats: [md]          # md, html, json
  file_dir: "./reports"
  file_pattern: "bill-tracker-report-{date}.{ext}"

delivery:
  telegram: true
  telegram_target: "8571118658"
```

New sections can be added by anyone by defining filter + columns + delivery rules. No Python changes needed.

### 11. Telegram payment flow

On the 15th (or when triggered manually), Hermes:

1. Runs the report (all unpaid bills)
2. Sends the report to Telegram with a message:
   > *Unpaid bills:* Enbridge $92.45, NPEI $108.30, Cogeco $78.00...  
   > **Total: $278.75**  
   > Mark all as paid? Reply `yes` to confirm, or `enbridge 92.45` to mark individual bills.
3. On confirmation, runs `bill-tracker mark-paid --all` (or `--vendor enbridge`)
4. Sends confirmation: "Marked 3 bills as paid. Paid date: 2026-09-15."

The `mark-paid` command supports:
```bash
bill-tracker mark-paid --all --date 2026-09-15          # all unpaid
bill-tracker mark-paid --vendor enbridge --date 2026-09-15  # specific vendor
bill-tracker mark-paid --bill-id "npe-2026-09" --date 2026-09-15  # specific bill
```

Manual marking exists as a fallback for when auto-matching missed a receipt or you paid outside the tracked system.

### 12. Historical data via fresh Gmail scan

No import of old JSON. Instead, a `--deep-scan` mode:

```bash
bill-tracker scan --deep --window 90d   # scan last 90 days of Gmail
```

This re-processes every email with the latest classifier + parser, building a clean dataset from scratch. The old `bills.json` (if any exists) is moved to `bills.json.bak` before the scan. This means parser improvements automatically fix historical data on the next deep scan.