#!/usr/bin/env python3
"""
Bill Tracker - Core Logic
Tracks recurring bills, due dates, and payments
"""

import json
import os
from datetime import datetime, date, timedelta
from pathlib import Path

WORKSPACE = Path("/home/boss/.openclaw/workspace")
BILLS_DIR = WORKSPACE / "bill-tracker" / "bills"
PAYMENTS_DIR = WORKSPACE / "bill-tracker" / "payments"

def load_bills():
    """Load all bills from index file."""
    index_path = BILLS_DIR / "index.json"
    if index_path.exists():
        with open(index_path, "r") as f:
            return json.load(f)
    return {"bills": []}

def save_bills(data):
    """Save bills to index file."""
    data["last_updated"] = datetime.now().isoformat()
    index_path = BILLS_DIR / "index.json"
    with open(index_path, "w") as f:
        json.dump(data, f, indent=2)

def get_today():
    """Get today's date."""
    return date.today()

def get_due_date(bill):
    """Calculate next due date for a bill."""
    next_due = bill.get("next_due", "")
    if next_due:
        return datetime.fromisoformat(next_due).date()
    
    # Fallback: calculate from due_day
    due_day = bill.get("due_day")
    if due_day == "varies":
        return None
    
    today = get_today()
    due_date = date(today.year, today.month, int(due_day))
    if due_date < today:
        # Move to next month
        if today.month == 12:
            due_date = date(today.year + 1, 1, int(due_day))
        else:
            due_date = date(today.year, today.month + 1, int(due_day))
    
    return due_date

def check_due_bills(days_ahead=3):
    """Find bills due within specified days."""
    data = load_bills()
    today = get_today()
    due_bills = []
    
    for bill in data.get("bills", []):
        if bill.get("status") == "paid":
            continue
        
        due_date = get_due_date(bill)
        if due_date and today <= due_date <= (today + timedelta(days=days_ahead)):
            due_bills.append({
                "bill": bill,
                "due_date": due_date,
                "days_left": (due_date - today).days
            })
    
    return sorted(due_bills, key=lambda x: x["due_date"])

def check_overdue_bills():
    """Find bills that are overdue."""
    data = load_bills()
    today = get_today()
    overdue = []
    
    for bill in data.get("bills", []):
        if bill.get("status") == "paid":
            continue
        
        due_date = get_due_date(bill)
        if due_date and due_date < today:
            overdue.append({
                "bill": bill,
                "due_date": due_date,
                "days_overdue": (today - due_date).days
            })
    
    return sorted(overdue, key=lambda x: x["days_overdue"])

def mark_paid(bill_id, amount=None, method=None):
    """Mark a bill as paid."""
    data = load_bills()
    today = get_today().isoformat()
    
    for bill in data.get("bills", []):
        if bill["id"] == bill_id:
            # Update bill status
            bill["status"] = "paid"
            bill["last_paid"] = today
            
            # Update history
            if "history" not in bill:
                bill["history"] = []
            
            payment = {
                "date": today,
                "status": "paid",
                "amount": amount or bill["amount"],
                "method": method or bill.get("payment_method", "unknown"),
                "note": "Marked paid via tracker"
            }
            bill["history"].append(payment)
            
            # Calculate next due date
            billing_period = bill.get("billing_period", "monthly")
            if billing_period == "monthly":
                next_month = today[:7]  # YYYY-MM
                year, month = map(int, next_month.split("-"))
                if month == 12:
                    month = 1
                    year += 1
                else:
                    month += 1
                bill["next_due"] = f"{year}-{month:02d}-{bill.get('due_day', 1):02d}"
            elif billing_period == "quarterly":
                # Simplified quarterly: add 3 months
                pass
            
            save_bills(data)
            return bill
    
    return None

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Bill Tracker CLI")
    parser.add_argument("--check-due", type=int, help="Check bills due within N days")
    parser.add_argument("--check-overdue", action="store_true", help="Check overdue bills")
    parser.add_argument("--mark-paid", help="Mark bill as paid (bill_id)")
    parser.add_argument("--amount", type=float, help="Payment amount")
    parser.add_argument("--method", help="Payment method")
    parser.add_argument("--list", action="store_true", help="List all bills")
    
    args = parser.parse_args()
    
    if args.check_due:
        due = check_due_bills(args.check_due)
        if due:
            print(f"📅 Bills due within {args.check_due} days:")
            for item in due:
                bill = item["bill"]
                print(f"  • {bill['name']} ({bill['provider']})")
                print(f"    Due: {item['due_date']} ({item['days_left']} days left)")
                print(f"    Amount: ${bill['amount']:.2f} {bill['currency']}")
        else:
            print("✅ No bills due soon!")
    
    elif args.check_overdue:
        overdue = check_overdue_bills()
        if overdue:
            print("⚠️  OVERDUE BILLS:")
            for item in overdue:
                bill = item["bill"]
                print(f"  • {bill['name']} ({bill['provider']})")
                print(f"    Overdue by {item['days_overdue']} days")
                print(f"    Amount: ${bill['amount']:.2f} {bill['currency']}")
        else:
            print("✅ All bills current!")
    
    elif args.list:
        data = load_bills()
        print("📋 All Bills:")
        for bill in data.get("bills", []):
            status = f"[{bill['status'].upper()}]"
            print(f"  {status} {bill['name']} ({bill['provider']}) - ${bill['amount']}")
    
    elif args.mark_paid:
        bill = mark_paid(args.mark_paid, args.amount, args.method)
        if bill:
            print(f"✅ Marked {bill['name']} as paid!")
        else:
            print("❌ Bill not found")
    
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
