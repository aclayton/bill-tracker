"""CLI entry points for bill-tracker."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime

from bill_tracker.models import BillStore, ReceiptStore
from bill_tracker.config import load_config, load_vendors, load_report_config
from bill_tracker.store import (
    load_bills,
    save_bills,
    load_receipts,
    save_receipts,
    mark_bill_paid,
    backup_store,
)
from bill_tracker.scanner import scan_email, process_scan_result
from bill_tracker.reporter import generate_report, apply_filter, apply_sort, format_bill_row
from bill_tracker.vendors import save_vendors


def cmd_scan(args: argparse.Namespace) -> int:
    """Scan an email: read from stdin, classify, parse, store."""
    config = load_config()
    vendors = load_vendors()
    data_dir = config.get("storage", {}).get("data_dir", "./data")

    subject = args.subject
    email_id = args.email_id
    if not subject or not email_id:
        print("Error: --subject and --email-id are required", file=sys.stderr)
        return 1

    body = sys.stdin.read()
    if not body.strip():
        print("Error: no email body on stdin", file=sys.stderr)
        return 1

    store_bills = load_bills(data_dir)
    store_receipts = load_receipts(data_dir)

    print(f"Scanning email: {subject[:60]}...")

    result = scan_email(subject, body, email_id, config, vendors)
    summary = process_scan_result(result, store_bills, store_receipts, vendors, config)

    save_bills(data_dir, store_bills)
    save_receipts(data_dir, store_receipts)

    print(f"Type: {result['type']}")
    print(f"Action: {summary['action']}")
    print(f"Details: {summary['details']}")
    if result.get("warnings"):
        for w in result["warnings"]:
            print(f"  Warning: {w}")

    return 0


def cmd_list(args: argparse.Namespace) -> int:
    """List bills and/or receipts with optional filters."""
    config = load_config()
    data_dir = config.get("storage", {}).get("data_dir", "./data")

    store_bills = load_bills(data_dir)
    store_receipts = load_receipts(data_dir)

    if args.receipts:
        items = list(store_receipts.receipts)
    else:
        items = list(store_bills.bills)

    # Apply filters
    if args.unpaid and not args.receipts:
        items = [b for b in items if not b.paid]
    if args.unmatched and args.receipts:
        items = [r for r in items if r.matchedBillId is None]
    if args.vendor:
        vendor_lower = args.vendor.lower()
        items = [i for i in items if vendor_lower in i.vendor.lower()]

    if not items:
        print("No items found.")
        return 0

    if args.receipts:
        columns = ["vendor", "amount", "currency", "paymentDate", "paymentMethod", "matchedBillId"]
        print(format_table_header(columns))
        for r in items:
            print(format_receipt_row(r, columns))
    else:
        columns = ["vendor", "amount", "currency", "dueDate", "paid", "category"]
        print(format_table_header(columns))
        for b in items:
            print(format_bill_row(b, columns))

    return 0


def format_table_header(columns: list[str]) -> str:
    header = "| " + " | ".join(columns) + " |"
    sep = "|" + "|".join(" --- " for _ in columns) + "|"
    return header + "\n" + sep


def format_receipt_row(receipt, columns: list[str]) -> str:
    from bill_tracker.reporter import format_receipt_row as frr
    return frr(receipt, columns)


def cmd_report(args: argparse.Namespace) -> int:
    """Generate and print a report."""
    config = load_config()
    vendors = load_vendors()
    report_config = load_report_config()
    data_dir = config.get("storage", {}).get("data_dir", "./data")

    store_bills = load_bills(data_dir)
    store_receipts = load_receipts(data_dir)

    bills = list(store_bills.bills)
    receipts = list(store_receipts.receipts)

    # Filter by month if specified
    if args.month:
        bills = [b for b in bills if b.receivedDate.startswith(args.month)]
        receipts = [r for r in receipts if r.paymentDate.startswith(args.month)]

    report = generate_report(bills, receipts, report_config, vendors)
    print(report)

    return 0


def cmd_mark_paid(args: argparse.Namespace) -> int:
    """Mark bills as paid."""
    config = load_config()
    data_dir = config.get("storage", {}).get("data_dir", "./data")

    store_bills = load_bills(data_dir)
    paid_date = args.date or date.today().isoformat()
    count = 0

    if args.all:
        for bill in store_bills.bills:
            if not bill.paid:
                bill.paid = True
                bill.paidDate = paid_date
                count += 1
    elif args.bill_id:
        if mark_bill_paid(store_bills, args.bill_id, paid_date):
            count = 1
    elif args.vendor:
        vendor_lower = args.vendor.lower()
        for bill in store_bills.bills:
            if not bill.paid and vendor_lower in bill.vendor.lower():
                bill.paid = True
                bill.paidDate = paid_date
                count += 1
    else:
        # Interactive mode: list unpaid and ask
        unpaid = [b for b in store_bills.bills if not b.paid]
        if not unpaid:
            print("No unpaid bills.")
            return 0
        print("Unpaid bills:")
        for b in unpaid:
            print(f"  {b.id}: {b.vendor} — {b.currency} {b.amount:.2f} due {b.dueDate}")
        print()
        answer = input(f"Mark all {len(unpaid)} as paid? [y/N]: ")
        if answer.lower() in ("y", "yes"):
            for b in unpaid:
                b.paid = True
                b.paidDate = paid_date
                count = len(unpaid)

    if count > 0:
        save_bills(data_dir, store_bills)
        print(f"Marked {count} bill(s) as paid on {paid_date}.")
    else:
        print("No bills matched.")

    return 0


def cmd_vendors(args: argparse.Namespace) -> int:
    """List known and discovered vendors."""
    vendors = load_vendors()

    print("\n=== Known Vendors ===")
    if vendors.known:
        for v in vendors.known:
            extras = []
            if v.expected_range:
                extras.append(f"range: {v.expected_range}")
            if v.parser_hint:
                extras.append(f"hint: {v.parser_hint[:50]}...")
            extra_str = f" ({', '.join(extras)})" if extras else ""
            print(f"  {v.name} — {v.category} ({v.currency}){extra_str}")
    else:
        print("  No known vendors.")

    print("\n=== Discovered Vendors ===")
    if vendors.discovered:
        for d in vendors.discovered:
            name = d.get("name", "Unknown")
            occurrences = d.get("occurrences", 1)
            sample = d.get("sample_amount", 0)
            currency = d.get("sample_currency", "CAD")
            print(f"  {name} — seen {occurrences}x, sample: {currency} {sample}")
    else:
        print("  No discovered vendors.")

    return 0


def cmd_deep_scan(args: argparse.Namespace) -> int:
    """Print instructions for Hermes to perform a deep scan."""
    window = args.window or "90d"
    print(f"""
=== Deep Scan Instructions ===

To perform a deep scan of the last {window}, ask Hermes:

"Use the Gmail tool to search for all bills and receipts from the last {window}.
For each result, get the full message content and pipe it to:
  bill-tracker scan --subject 'SUBJECT' --email-id 'ID'

This will re-process all historical emails with the latest classifier and parser."

Before running, back up your data:
  bill-tracker backup
""")
    return 0


def cmd_backup(args: argparse.Namespace) -> int:
    """Backup bills.json and receipts.json."""
    config = load_config()
    data_dir = config.get("storage", {}).get("data_dir", "./data")
    backup_store(data_dir)
    print(f"Backup created in {data_dir}/ (bills.json.bak, receipts.json.bak)")
    return 0


def cmd_install(args: argparse.Namespace) -> int:
    """Interactive installer — set up config files."""
    print("\n=== Bill Tracker v3 Installer ===\n")

    gmail_account = input("Gmail account email (e.g. user@gmail.com): ").strip()
    data_dir = input("Data directory [./data]: ").strip() or "./data"
    reports_dir = input("Reports directory [./reports]: ").strip() or "./reports"
    telegram_target = input("Telegram target chat ID (leave blank to skip): ").strip()

    # Write config.yaml
    config_content = f"""# Bill Tracker v3 Configuration
# Generated by bill-tracker install

gmail:
  account: "{gmail_account}"
  search_window: "1d"
  bill_query: "bill OR invoice OR due OR statement"
  receipt_query: 'receipt OR "payment confirmation" OR "thank you for your payment"'

storage:
  data_dir: "{data_dir}"

matching:
  amount_tolerance: 0.50
  confidence_threshold: 0.7

parser:
  model: "google/gemini-3-flash-preview"
  max_tokens: 200
"""

    config_path = "config.yaml"
    if os.path.exists(config_path):
        print(f"\n{config_path} already exists. Overwrite? [y/N]: ", end="")
        if input().lower() != "y":
            print("Skipping config.yaml.")
        else:
            with open(config_path, "w") as f:
                f.write(config_content)
            print(f"Wrote {config_path}")
    else:
        with open(config_path, "w") as f:
            f.write(config_content)
        print(f"Wrote {config_path}")

    # Write vendors.yaml template if not exists
    vendors_path = "vendors.yaml"
    if not os.path.exists(vendors_path):
        vendors_content = """# Bill Tracker — Vendor Configuration
# Add known vendors here with patterns, categories, and parsing hints.
# Discovered vendors are auto-added below.

vendors: []

discovered: []
"""
        with open(vendors_path, "w") as f:
            f.write(vendors_content)
        print(f"Wrote {vendors_path} (template)")

    # Write report.yaml template if not exists
    report_path = "report.yaml"
    if not os.path.exists(report_path):
        report_content = f"""# Bill Tracker — Report Configuration
# Define report sections with filters, sorting, and columns.

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
  formats: [md]
  file_dir: "{reports_dir}"
  file_pattern: "bill-tracker-report-{{date}}.{{ext}}"

delivery:
  telegram: true
  telegram_target: "{telegram_target}"
"""
        with open(report_path, "w") as f:
            f.write(report_content)
        print(f"Wrote {report_path} (template)")

    # Create directories
    os.makedirs(data_dir, exist_ok=True)
    os.makedirs(reports_dir, exist_ok=True)

    print("\n=== Installation Complete ===")
    print("Next steps:")
    print(f"  1. Edit vendors.yaml to add your known vendors")
    print(f"  2. Run: bill-tracker scan --help")
    print(f"  3. Set up Hermes cron job for daily scanning")
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    """Export bills and receipts as JSON."""
    config = load_config()
    data_dir = config.get("storage", {}).get("data_dir", "./data")

    store_bills = load_bills(data_dir)
    store_receipts = load_receipts(data_dir)

    output = {
        "bills": [b.model_dump() for b in store_bills.bills],
        "receipts": [r.model_dump() for r in store_receipts.receipts],
    }

    if args.output:
        with open(args.output, "w") as f:
            json.dump(output, f, indent=2)
        print(f"Exported to {args.output}")
    else:
        print(json.dumps(output, indent=2))

    return 0


def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="bill-tracker",
        description="Bill Tracker v3 — LLM-assisted bill and receipt tracking",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # scan
    p_scan = subparsers.add_parser("scan", help="Scan an email for bill/receipt")
    p_scan.add_argument("--subject", required=True, help="Email subject")
    p_scan.add_argument("--email-id", required=True, help="Unique email ID")

    # list
    p_list = subparsers.add_parser("list", help="List bills and receipts")
    p_list.add_argument("--unpaid", action="store_true", help="Show only unpaid bills")
    p_list.add_argument("--vendor", help="Filter by vendor name")
    p_list.add_argument("--receipts", action="store_true", help="Show receipts instead of bills")
    p_list.add_argument("--unmatched", action="store_true", help="Show unmatched receipts")

    # report
    p_report = subparsers.add_parser("report", help="Generate report")
    p_report.add_argument("--month", help="Filter by month (YYYY-MM)")
    p_report.add_argument("--format", choices=["md", "html"], default="md", help="Output format")

    # mark-paid
    p_paid = subparsers.add_parser("mark-paid", help="Mark bills as paid")
    p_paid.add_argument("--all", action="store_true", help="Mark all unpaid bills paid")
    p_paid.add_argument("--vendor", help="Mark bills for a specific vendor paid")
    p_paid.add_argument("--bill-id", help="Mark a specific bill paid")
    p_paid.add_argument("--date", help="Payment date (YYYY-MM-DD, default: today)")

    # vendors
    subparsers.add_parser("vendors", help="List known and discovered vendors")

    # deep-scan
    p_deep = subparsers.add_parser("deep-scan", help="Instructions for deep scan")
    p_deep.add_argument("--window", default="90d", help="Time window (default: 90d)")

    # backup
    subparsers.add_parser("backup", help="Backup bills.json and receipts.json")

    # install
    subparsers.add_parser("install", help="Interactive setup wizard")

    # export
    p_export = subparsers.add_parser("export", help="Export data as JSON")
    p_export.add_argument("--output", "-o", help="Output file path")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    commands = {
        "scan": cmd_scan,
        "list": cmd_list,
        "report": cmd_report,
        "mark-paid": cmd_mark_paid,
        "vendors": cmd_vendors,
        "deep-scan": cmd_deep_scan,
        "backup": cmd_backup,
        "install": cmd_install,
        "export": cmd_export,
    }

    handler = commands.get(args.command)
    if handler:
        sys.exit(handler(args))
    else:
        print(f"Unknown command: {args.command}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()