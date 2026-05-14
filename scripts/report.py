#!/usr/bin/env python3
"""
Bill Tracker Report Generator

Generates markdown and HTML reports for:
- Unpaid/overdue bills
- Payment history
- Monthly summaries
- Projected totals

Usage:
  python report.py --format md
  python report.py --format html
  python report.py --format both
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional


def load_index(path: Path) -> dict:
    """Load bills/index.json."""
    if path.exists():
        with open(path, 'r') as f:
            return json.load(f)
    return {"lastUpdated": "", "bills": [], "summary": {}}


def load_payments(payments_dir: Path) -> List[dict]:
    """Load all payment records from payments/ directory."""
    payments = []
    if not payments_dir.exists():
        return payments
    
    for payment_file in payments_dir.glob("*.json"):
        try:
            with open(payment_file, 'r') as f:
                payments.extend(json.load(f))
        except Exception as e:
            print(f"Error loading {payment_file}: {e}")
    
    return payments


def categorize_bills(bills: List[dict]) -> Dict[str, List[dict]]:
    """Categorize bills by category."""
    categories = {}
    for bill in bills:
        cat = bill.get('category', 'uncategorized')
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(bill)
    return categories


def format_currency(amount: float) -> str:
    """Format amount as CAD currency."""
    return f"${amount:,.2f} CAD"


def generate_markdown(index: dict, payments: List[dict], output_dir: Path) -> str:
    """Generate markdown report."""
    bills = index.get('bills', [])
    summary = index.get('summary', {})
    
    # Calculate metrics
    unpaid = [b for b in bills if not b['paid']]
    paid = [b for b in bills if b['paid']]
    overdue = [b for b in unpaid if datetime.strptime(b['dueDate'], "%Y-%m-%d").date() < datetime.now().date()]
    
    # Group by category
    categories = categorize_bills(unpaid)
    
    # Build report
    lines = []
    lines.append(f"# Bill Tracker Report - {datetime.now().strftime('%Y-%m-%d')}")
    lines.append("")
    lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"**Data Updated:** {index.get('lastUpdated', 'N/A')}")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"| Metric | Value |")
    lines.append(f"|--------|-------|")
    lines.append(f"| Total Bills | {len(bills)} |")
    lines.append(f"| Unpaid | {len(unpaid)} |")
    lines.append(f"| Paid | {len(paid)} |")
    lines.append(f"| Overdue | {len(overdue)} |")
    lines.append(f"| Total Unpaid | {format_currency(summary.get('totalUnpaid', sum(b['amount'] for b in unpaid)))} |")
    lines.append(f"| Monthly Average | {format_currency(summary.get('monthlyAverage', sum(b['amount'] for b in unpaid) / max(len(unpaid), 1)))} |")
    lines.append("")
    
    # Unpaid/Overdue Section
    lines.append("## Unpaid & Overdue Bills")
    lines.append("")
    
    if overdue:
        lines.append("### 🔴 OVERDUE (Pay Immediately)")
        lines.append("")
        lines.append(f"| Vendor | Amount | Due Date | Days Late |")
        lines.append(f"|--------|--------|----------|-----------|")
        for bill in overdue:
            due = datetime.strptime(bill['dueDate'], "%Y-%m-%d").date()
            days_late = (datetime.now().date() - due).days
            lines.append(f"| {bill['vendor']} | {format_currency(bill['amount'])} | {bill['dueDate']} | {days_late} |")
        lines.append("")
    
    if [b for b in unpaid if b not in overdue]:
        lines.append("### 🟡 Upcoming (Due Soon)")
        lines.append("")
        lines.append(f"| Vendor | Amount | Due Date | Days Until |")
        lines.append(f"|--------|--------|----------|------------|")
        for bill in [b for b in unpaid if b not in overdue]:
            due = datetime.strptime(bill['dueDate'], "%Y-%m-%d").date()
            days_until = (due - datetime.now().date()).days
            lines.append(f"| {bill['vendor']} | {format_currency(bill['amount'])} | {bill['dueDate']} | {days_until} |")
        lines.append("")
    
    # Category Breakdown
    lines.append("## By Category")
    lines.append("")
    for cat, cat_bills in categories.items():
        total = sum(b['amount'] for b in cat_bills)
        lines.append(f"### {cat.title()}")
        lines.append("")
        lines.append(f"| Vendor | Amount |")
        lines.append(f"|--------|--------|")
        for bill in cat_bills:
            lines.append(f"| {bill['vendor']} | {format_currency(bill['amount'])} |")
        lines.append(f"**Total:** {format_currency(total)}")
        lines.append("")
    
    # Payment History
    lines.append("## Payment History")
    lines.append("")
    
    if payments:
        lines.append(f"| Date | Bill | Amount |")
        lines.append(f"|------|------|--------|")
        for payment in sorted(payments, key=lambda x: x.get('date', ''))[-10:]:  # Last 10
            lines.append(f"| {payment.get('date', 'N/A')} | {payment.get('billId', 'N/A')} | {format_currency(payment.get('amount', 0))} |")
    else:
        lines.append("No payments recorded yet.")
    
    lines.append("")
    
    # Projections
    lines.append("## Projections")
    lines.append("")
    projected = sum(b['amount'] for b in overdue) + sum(b['amount'] for b in unpaid if b not in overdue)
    lines.append(f"**Projected for next cycle:** {format_currency(projected)}")
    lines.append("")
    
    # Notes
    lines.append("## Notes")
    lines.append("")
    lines.append("* This report is generated automatically from your Gmail bill scans and manual updates.")
    lines.append("* Contact your bill tracker admin for questions or corrections.")
    
    report = "\n".join(lines)
    
    # Save report
    output_dir.mkdir(parents=True, exist_ok=True)
    md_file = output_dir / f"bill-tracker-report-{datetime.now().strftime('%Y-%m-%d')}.md"
    with open(md_file, 'w') as f:
        f.write(report)
    
    return report


def generate_html(index: dict, payments: List[dict], output_dir: Path) -> str:
    """Generate HTML report."""
    md_report = generate_markdown(index, payments, output_dir)
    
    # Convert markdown to simple HTML
    html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Bill Tracker Report - {datetime.now().strftime('%Y-%m-%d')}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; }}
        h1 {{ color: #333; }}
        h2 {{ color: #555; border-bottom: 1px solid #ddd; padding-bottom: 10px; }}
        table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
        th, td {{ border: 1px solid #ddd; padding: 12px; text-align: left; }}
        th {{ background-color: #4CAF50; color: white; }}
        tr:nth-child(even) {{ background-color: #f2f2f2; }}
        .overdue {{ background-color: #ffebee !important; }}
        .upcoming {{ background-color: #fff8e1 !important; }}
        .summary {{ background-color: #e8f5e9; padding: 20px; border-radius: 8px; margin: 20px 0; }}
        .total {{ font-weight: bold; color: #d32f2f; font-size: 1.2em; }}
    </style>
</head>
<body>
    <h1>Bill Tracker Report - {datetime.now().strftime('%Y-%m-%d')}</h1>
    <p><strong>Generated:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    <p><strong>Data Updated:</strong> {index.get('lastUpdated', 'N/A')}</p>
    
    <div class="summary">
        <h2>Summary</h2>
        <table>
            <tr><th>Metric</th><th>Value</th></tr>
            <tr><td>Total Bills</td><td>{len(index.get('bills', []))}</td></tr>
            <tr><td>Unpaid</td><td>{len([b for b in index.get('bills', []) if not b['paid']])}</td></tr>
            <tr><td>Paid</td><td>{len([b for b in index.get('bills', []) if b['paid']])}</td></tr>
            <tr><td>Total Unpaid</td><td class="total">${index.get('summary', {}).get('totalUnpaid', 0):,.2f} CAD</td></tr>
            <tr><td>Monthly Average</td><td>${index.get('summary', {}).get('monthlyAverage', 0):,.2f} CAD</td></tr>
        </table>
    </div>
    
    <h2>Unpaid Bills</h2>
    <table>
        <tr><th>Vendor</th><th>Amount</th><th>Due Date</th><th>Status</th></tr>
"""
    
    for bill in index.get('bills', []):
        if not bill['paid']:
            status = "OVERDUE" if datetime.strptime(bill['dueDate'], "%Y-%m-%d").date() < datetime.now().date() else "Upcoming"
            classes = "overdue" if status == "OVERDUE" else "upcoming"
            html += f"""        <tr class="{classes}">
            <td>{bill['vendor']}</td>
            <td>${bill['amount']:.2f} CAD</td>
            <td>{bill['dueDate']}</td>
            <td>{status}</td>
        </tr>
"""
    
    html += """    </table>
    
    <h2>Payment History</h2>
    <table>
        <tr><th>Date</th><th>Bill ID</th><th>Amount</th></tr>
"""
    
    for payment in sorted(payments, key=lambda x: x.get('date', ''))[-10:]:
        html += f"""        <tr>
            <td>{payment.get('date', 'N/A')}</td>
            <td>{payment.get('billId', 'N/A')}</td>
            <td>${payment.get('amount', 0):.2f} CAD</td>
        </tr>
"""
    
    html += """    </table>
    
    <h2>Projections</h2>
    <p><strong>Projected for next cycle:</strong> $""" + f"{index.get('summary', {}).get('totalUnpaid', 0):,.2f} CAD</p>"
    
    html += """
</body>
</html>"""
    
    # Save HTML
    output_dir.mkdir(parents=True, exist_ok=True)
    html_file = output_dir / f"bill-tracker-report-{datetime.now().strftime('%Y-%m-%d')}.html"
    with open(html_file, 'w') as f:
        f.write(html)
    
    return html


def main():
    format_type = os.environ.get("FORMAT", "both")
    
    # Paths
    workspace = Path("/home/boss/.openclaw/workspace")
    index_path = workspace / "repos/bill-tracker/bills/index.json"
    payments_dir = workspace / "repos/bill-tracker/payments"
    output_dir = workspace / "repos/bill-tracker/reports"
    
    # Load data
    index = load_index(index_path)
    payments = load_payments(payments_dir)
    
    print(f"Loaded {len(index.get('bills', []))} bills and {len(payments)} payments")
    
    if format_type in ("md", "both"):
        report = generate_markdown(index, payments, output_dir)
        print(f"Markdown report saved to: {output_dir / f'bill-tracker-report-{datetime.now().strftime('%Y-%m-%d')}.md'}")
    
    if format_type in ("html", "both"):
        generate_html(index, payments, output_dir)
        print(f"HTML report saved to: {output_dir / f'bill-tracker-report-{datetime.now().strftime('%Y-%m-%d')}.html'}")
    
    # Print summary to stdout
    print("\nQuick Summary:")
    print(f"  Total Bills: {len(index.get('bills', []))}")
    print(f"  Unpaid: {len([b for b in index.get('bills', []) if not b['paid']])}")
    print(f"  Total Unpaid: ${index.get('summary', {}).get('totalUnpaid', 0):,.2f} CAD")


if __name__ == "__main__":
    main()
