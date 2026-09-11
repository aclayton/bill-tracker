# Bill Tracker v3

Scan Gmail for bills and receipts, track payments, and generate reports — all driven by config files. Built for [Hermes Agent](https://hermes-agent.nousresearch.com/).

## How It Works

1. Hermes scans your Gmail daily for bills and receipts
2. Each email is classified (bill / receipt / neither) and parsed via LLM
3. Bills are stored in `data/bills.json`, receipts in `data/receipts.json`
4. Receipts auto-match to unpaid bills (vendor + amount ± $0.50)
5. On the 15th of each month, you get a Telegram report and can mark bills paid

## Quick Start

```bash
# Clone and install
git clone https://github.com/aclayton/bill-tracker
cd bill-tracker
git checkout v3
./install.sh

# Interactive setup (config.yaml, vendors.yaml, report.yaml)
bill-tracker install
```

## Requirements

- Python >= 3.11
- Hermes Agent (for Gmail access and cron scheduling)
- OpenRouter API key (or any OpenAI-compatible LLM endpoint)
- Telegram bot (for reports and payment flow)

## Configuration

All behavior is driven by config files — edit them, don't touch the code:

| File | Purpose |
|------|---------|
| `config.yaml` | Gmail account, storage paths, LLM model, matching tolerance |
| `vendors.yaml` | Known vendors + auto-discovered vendors from your emails |
| `report.yaml` | Report sections, filters, sort order, delivery targets |

## CLI Reference

```bash
bill-tracker scan           # Parse email from stdin, classify + store
bill-tracker list           # List bills (--unpaid, --vendor, --receipts, --unmatched)
bill-tracker report         # Generate markdown report (--format html, --month YYYY-MM)
bill-tracker mark-paid      # Mark bills paid (--all, --vendor, --bill-id, --date)
bill-tracker vendors        # List known and discovered vendors
bill-tracker deep-scan      # Instructions for historical Gmail scan
bill-tracker backup         # Backup data files
```

## LICENSE

MIT