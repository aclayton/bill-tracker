#!/usr/bin/env python3
"""
Bill Tracker - Report Generator (Phase 4)
Generates various reports from bill data including monthly summaries,
upcoming bills, overdue bills, yearly projections, and CSV exports.
"""

import json
import os
import csv
import sys
from datetime import datetime, date, timedelta
from pathlib import Path
from collections import defaultdict

WORKSPACE = Path("/home/boss/.openclaw/workspace")
BILLS_DIR = WORKSPACE / "bill-tracker" / "bills"
REPORTS_DIR = WORKSPACE / "bill-tracker" / "reports"


def load_bills():
    """Load all bills from index file."""
    index_path = BILLS_DIR / "index.json"
    if index_path.exists():
        with open(index_path, "r") as f:
            return json.load(f)
    return {"bills": []}


def get_today():
    """Get today's date."""
    return date.today()


def parse_month(month_str):
    """Parse YYYY-MM format to year, month tuple."""
    try:
        parts = month_str.split("-")
        return int(parts[0]), int(parts[1])
    except (ValueError, IndexError):
        return None, None


def get_month_range(year, month):
    """Get first and last day of a month."""
    start = date(year, month, 1)
    if month == 12:
        end = date(year + 1, 1, 1)
    else:
        end = date(year, month + 1, 1)
    return start, end


def calculate_next_due_date(bill, reference_date=None):
    """Calculate the next due date for a bill."""
    if reference_date is None:
        reference_date = get_today()
    
    # Use next_due field if available
    next_due_str = bill.get("next_due")
    if next_due_str:
        return datetime.fromisoformat(next_due_str).date()
    
    # Calculate from due_day
    due_day = bill.get("due_day")
    if due_day == "varies":
        return None
    
    try:
        due_day = int(due_day)
    except (ValueError, TypeError):
        return None
    
    current = reference_date
    due_date = date(current.year, current.month, due_day)
    
    if due_date < current:
        # Move to next month
        if current.month == 12:
            due_date = date(current.year + 1, 1, due_day)
        else:
            due_date = date(current.year, current.month + 1, due_day)
    
    return due_date


def format_currency(amount, currency="CAD"):
    """Format amount as currency string."""
    symbol = "$" if currency == "CAD" else f"{currency} "
    return f"{symbol}{amount:.2f}"


def generate_monthly_summary(data, year, month, category=None):
    """Generate monthly bill summary."""
    start, end = get_month_range(year, month)
    
    categories = defaultdict(lambda: {"paid": 0.0, "pending": 0.0, "bills": []})
    total_paid = 0.0
    total_pending = 0.0
    
    for bill in data.get("bills", []):
        bill_category = bill.get("category", "Uncategorized")
        
        # Filter by category if specified
        if category and bill_category.lower() != category.lower():
            continue
        
        next_due = calculate_next_due_date(bill)
        if next_due and start <= next_due < end:
            amount = float(bill.get("amount", 0))
            status = bill.get("status", "pending")
            
            if status == "paid":
                categories[bill_category]["paid"] += amount
                total_paid += amount
            else:
                categories[bill_category]["pending"] += amount
                total_pending += amount
            
            categories[bill_category]["bills"].append({
                "name": bill["name"],
                "amount": amount,
                "status": status,
                "due_date": next_due
            })
    
    return {
        "period": f"{year}-{month:02d}",
        "total_paid": total_paid,
        "total_pending": total_pending,
        "categories": dict(categories)
    }


def generate_upcoming_bills(data, days=7, category=None):
    """Find bills due within the next N days."""
    today = get_today()
    end_date = today + timedelta(days=days)
    
    upcoming = []
    
    for bill in data.get("bills", []):
        bill_category = bill.get("category", "Uncategorized")
        
        # Filter by category if specified
        if category and bill_category.lower() != category.lower():
            continue
        
        next_due = calculate_next_due_date(bill)
        if next_due and today <= next_due <= end_date:
            amount = float(bill.get("amount", 0))
            days_left = (next_due - today).days
            
            upcoming.append({
                "bill": bill,
                "due_date": next_due,
                "days_left": days_left,
                "amount": amount
            })
    
    return sorted(upcoming, key=lambda x: x["due_date"])


def generate_overdue_bills(data, category=None):
    """Find overdue bills."""
    today = get_today()
    
    overdue = []
    
    for bill in data.get("bills", []):
        bill_category = bill.get("category", "Uncategorized")
        
        # Filter by category if specified
        if category and bill_category.lower() != category.lower():
            continue
        
        # Skip already paid bills
        if bill.get("status") == "paid":
            continue
        
        next_due = calculate_next_due_date(bill)
        if next_due and next_due < today:
            days_overdue = (today - next_due).days
            
            overdue.append({
                "bill": bill,
                "due_date": next_due,
                "days_overdue": days_overdue,
                "amount": float(bill.get("amount", 0))
            })
    
    return sorted(overdue, key=lambda x: x["days_overdue"], reverse=True)


def generate_yearly_projection(data, year=None):
    """Generate yearly spending projection."""
    if year is None:
        year = get_today().year
    
    monthly_totals = defaultdict(lambda: {"paid": 0.0, "pending": 0.0})
    category_breakdown = defaultdict(float)
    
    for bill in data.get("bills", []):
        next_due = calculate_next_due_date(bill, date(year, 1, 1))
        if next_due and next_due.year == year:
            amount = float(bill.get("amount", 0))
            category = bill.get("category", "Uncategorized")
            
            if bill.get("status") == "paid":
                monthly_totals[next_due.month]["paid"] += amount
            else:
                monthly_totals[next_due.month]["pending"] += amount
            
            category_breakdown[category] += amount
    
    # Calculate yearly totals
    yearly_paid = sum(m["paid"] for m in monthly_totals.values())
    yearly_pending = sum(m["pending"] for m in monthly_totals.values())
    
    return {
        "year": year,
        "monthly_totals": dict(monthly_totals),
        "category_breakdown": dict(category_breakdown),
        "total_paid": yearly_paid,
        "total_pending": yearly_pending
    }


def export_to_csv(data, filepath, reports=None):
    """Export report data to CSV format."""
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        
        if reports:
            for report_name, report_data in reports.items():
                writer.writerow([f"# {report_name}"])
                if isinstance(report_data, dict) and "period" in report_data:
                    writer.writerow(["Period", report_data["period"]])
                    writer.writerow(["Total Paid", f"${report_data['total_paid']:.2f}"])
                    writer.writerow(["Total Pending", f"${report_data['total_pending']:.2f}"])
                    writer.writerow([])
                    writer.writerow(["Category", "Paid", "Pending", "Bill Name", "Status", "Due Date"])
                    
                    for cat, cat_data in report_data.get("categories", {}).items():
                        for bill in cat_data.get("bills", []):
                            writer.writerow([
                                cat,
                                f"${cat_data['paid']:.2f}",
                                f"${cat_data['pending']:.2f}",
                                bill["name"],
                                bill["status"],
                                str(bill["due_date"])
                            ])
                writer.writerow([])
        else:
            # Export bills directly
            writer.writerow(["ID", "Name", "Category", "Provider", "Amount", "Currency", 
                           "Due Day", "Status", "Next Due", "Payment Method"])
            for bill in data.get("bills", []):
                writer.writerow([
                    bill.get("id", ""),
                    bill.get("name", ""),
                    bill.get("category", ""),
                    bill.get("provider", ""),
                    bill.get("amount", ""),
                    bill.get("currency", ""),
                    bill.get("due_day", ""),
                    bill.get("status", ""),
                    bill.get("next_due", ""),
                    bill.get("payment_method", "")
                ])
    
    return filepath


def print_summary(summary):
    """Print monthly summary in readable format."""
    print(f"\n{'=' * 60}")
    print(f"📊 MONTHLY SUMMARY: {summary['period']}")
    print(f"{'=' * 60}")
    print(f"💰 Total Paid:    {format_currency(summary['total_paid'])}")
    print(f"💳 Total Pending: {format_currency(summary['total_pending'])}")
    print(f"📊 Grand Total:   {format_currency(summary['total_paid'] + summary['total_pending'])}")
    print()
    
    if summary['categories']:
        for category, cat_data in sorted(summary['categories'].items()):
            print(f"📁 {category}")
            print(f"   Paid:    {format_currency(cat_data['paid'])}")
            print(f"   Pending: {format_currency(cat_data['pending'])}")
            print()
            
            for bill in cat_data.get("bills", []):
                status_icon = "✅" if bill["status"] == "paid" else "⏳"
                print(f"   {status_icon} {bill['name']}: {format_currency(bill['amount'])} "
                      f"(Due: {bill['due_date']})")
            print()
    else:
        print("No bills found for this period.")


def print_upcoming(upcoming, days):
    """Print upcoming bills in readable format."""
    print(f"\n{'=' * 60}")
    print(f"📅 BILLS DUE WITHIN NEXT {days} DAYS")
    print(f"{'=' * 60}")
    
    if upcoming:
        for item in upcoming:
            bill = item["bill"]
            days_left = item["days_left"]
            due_date = item["due_date"]
            
            print(f"• {bill['name']} ({bill['provider']})")
            print(f"  Due: {due_date} ({days_left} days)")
            print(f"  Amount: {format_currency(item['amount'])}")
            print(f"  Category: {bill.get('category', 'Uncategorized')}")
            print()
    else:
        print("✅ No bills due in the next {} days!".format(days))


def print_overdue(overdue):
    """Print overdue bills in readable format."""
    print(f"\n{'=' * 60}")
    print(f"⚠️  OVERDUE BILLS")
    print(f"{'=' * 60}")
    
    if overdue:
        for item in overdue:
            bill = item["bill"]
            days_overdue = item["days_overdue"]
            
            print(f"• {bill['name']} ({bill['provider']})")
            print(f"  Overdue by {days_overdue} days")
            print(f"  Amount: {format_currency(item['amount'])}")
            print(f"  Category: {bill.get('category', 'Uncategorized')}")
            print(f"  Last Due: {item['due_date']}")
            print()
    else:
        print("✅ All bills are current!")


def print_projection(projection):
    """Print yearly projection in readable format."""
    print(f"\n{'=' * 60}")
    print(f"📈 YEARLY PROJECTION: {projection['year']}")
    print(f"{'=' * 60}")
    print(f"💰 Projected Total (Paid):   {format_currency(projection['total_paid'])}")
    print(f"💳 Projected Total (Pending): {format_currency(projection['total_pending'])}")
    print(f"📊 Projected Annual Total:    {format_currency(projection['total_paid'] + projection['total_pending'])}")
    print()
    
    # Monthly breakdown
    print("📅 Monthly Breakdown:")
    print("-" * 40)
    for month in range(1, 13):
        month_data = projection['monthly_totals'].get(month, {"paid": 0.0, "pending": 0.0})
        if month_data["paid"] > 0 or month_data["pending"] > 0:
            month_name = datetime(2024, month, 1).strftime("%B")
            total = month_data["paid"] + month_data["pending"]
            print(f"  {month_name:12} Paid: {format_currency(month_data['paid']):>10} "
                  f"Pending: {format_currency(month_data['pending']):>10} Total: {format_currency(total):>10}")
    print()
    
    # Category breakdown
    print("📁 Category Breakdown:")
    print("-" * 40)
    for category, amount in sorted(projection['category_breakdown'].items(), key=lambda x: -x[1]):
        print(f"  {category:20} {format_currency(amount)}")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Bill Tracker - Report Generator (Phase 4)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Monthly summary for March 2026
  python report.py --month 2026-03

  # Bills due in next 7 days
  python report.py --due 7

  # Overdue bills
  python report.py --overdue

  # Yearly projection for 2026
  python report.py --year 2026

  # Category-specific reports
  python report.py --month 2026-03 --category utilities
  python report.py --due 7 --category mobile

  # Export to CSV
  python report.py --month 2026-03 --export csv
  python report.py --export csv --output bills_export.csv

  # Multiple reports at once
  python report.py --month 2026-03 --due 7 --overdue --year 2026
        """
    )
    
    # Report selection
    parser.add_argument("--month", type=str, help="Generate monthly summary (format: YYYY-MM)")
    parser.add_argument("--due", type=int, help="Show bills due within N days")
    parser.add_argument("--overdue", action="store_true", help="Show overdue bills")
    parser.add_argument("--year", type=int, help="Generate yearly projection for specified year")
    parser.add_argument("--category", type=str, help="Filter by category (e.g., utilities, mobile)")
    
    # Export options
    parser.add_argument("--export", choices=["csv"], help="Export format (currently CSV only)")
    parser.add_argument("--output", "-o", type=str, default=None, help="Output file path for export")
    
    # List option
    parser.add_argument("--list", action="store_true", help="List all bills (simple output)")
    
    args = parser.parse_args()
    
    # Load bills data
    data = load_bills()
    
    if not data.get("bills"):
        print("❌ No bills found!")
        sys.exit(1)
    
    # Collect reports to export
    reports = {}
    
    # Generate requested reports
    if args.month:
        year, month = parse_month(args.month)
        if year is None:
            print(f"❌ Invalid month format: {args.month} (use YYYY-MM)")
            sys.exit(1)
        
        summary = generate_monthly_summary(data, year, month, args.category)
        reports["monthly_summary"] = summary
        
        if not args.export:
            print_summary(summary)
    
    if args.due:
        upcoming = generate_upcoming_bills(data, args.due, args.category)
        reports["upcoming"] = upcoming
        
        if not args.export:
            print_upcoming(upcoming, args.due)
    
    if args.overdue:
        overdue = generate_overdue_bills(data, args.category)
        reports["overdue"] = overdue
        
        if not args.export:
            print_overdue(overdue)
    
    if args.year:
        projection = generate_yearly_projection(data, args.year)
        reports["yearly_projection"] = projection
        
        if not args.export:
            print_projection(projection)
    
    if args.list:
        print("📋 All Bills:")
        print("-" * 60)
        for bill in data.get("bills", []):
            status = f"[{bill['status'].upper()}]"
            amount = format_currency(bill.get("amount", 0))
            print(f"  {status} {bill['name']:30} {amount:>12} "
                  f"({bill.get('category', 'Uncategorized')})")
    
    # Export if requested
    if args.export:
        output_path = args.output or REPORTS_DIR / f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        try:
            export_to_csv(data, output_path, reports if reports else None)
            print(f"\n✅ Exported to: {output_path}")
        except Exception as e:
            print(f"❌ Export failed: {e}")
            sys.exit(1)
    
    # Print help if no action specified
    if not any([args.month, args.due, args.overdue, args.year, args.list]):
        parser.print_help()


if __name__ == "__main__":
    main()
