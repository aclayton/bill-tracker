#!/usr/bin/env python3
"""
Mark Paid - Process receipt emails to mark bills as paid and record payments

Usage:
  python mark_paid.py --email-id <msgId>
  python mark_paid.py --folder receipts/ --process-all
"""

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Optional


def load_index(path: Path) -> dict:
    """Load bills/index.json."""
    if path.exists():
        with open(path, 'r') as f:
            return json.load(f)
    return {"lastUpdated": "", "bills": [], "summary": {"totalUnpaid": 0, "overdueCount": 0, "monthlyAverage": 0}}


def save_index(path: Path, data: dict) -> None:
    """Save bills/index.json with pretty formatting."""
    data["lastUpdated"] = datetime.utcnow().isoformat() + "Z"
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)


def find_bill_by_vendor_amount(index: dict, vendor: str, amount: float) -> Optional[dict]:
    """Find a matching unpaid bill."""
    for bill in index['bills']:
        if (bill['vendor'].lower() == vendor.lower() and 
            abs(bill['amount'] - amount) < 0.01 and 
            not bill['paid']):
            return bill
    return None


def process_receipt_email(email: dict, index: dict, payments_dir: Path) -> Optional[dict]:
    """Process a receipt email to mark a bill as paid."""
    # Extract payment info from email
    body = email.get('snippet', '') + ' ' + email.get('body', '')
    subject = email.get('subject', '')
    
    # Common patterns for payment confirmations
    patterns = {
        "enbridge": r"enbridge.*?(?:payment|confirmed|received)\s*[:\$]?\s*(\d+\.?\d*)",
        "enercare": r"enercare.*?(?:payment|confirmed|received)\s*[:\$]?\s*(\d+\.?\d*)",
        "npei|npe|hydro": r"(?:npei|npe|hydro).*?(?:payment|confirmed|received)\s*[:\$]?\s*(\d+\.?\d*)",
        "cogeco": r"cogeco.*?(?:payment|confirmed|received)\s*[:\$]?\s*(\d+\.?\d*)",
        "td": r"td.*?(?:payment|confirmed|received)\s*[:\$]?\s*(\d+\.?\d*)",
    }
    
    for vendor, pattern in patterns.items():
        match = re.search(pattern, body, re.IGNORECASE)
        if match:
            vendor_name = vendor.title()
            amount = float(match.group(1))
            
            # Find matching bill
            bill = find_bill_by_vendor_amount(index, vendor_name, amount)
            if bill:
                # Create payment record
                payment_id = f"{bill['id']}-{datetime.utcnow().strftime('%Y%m%d')}"
                payment = {
                    "id": payment_id,
                    "billId": bill['id'],
                    "date": datetime.utcnow().strftime("%Y-%m-%d"),
                    "amount": amount,
                    "method": email.get('from', 'unknown'),
                    "receiptEmail": email.get('id', ''),
                    "notes": f"Receipt from {subject}"
                }
                
                # Save payment record
                payments_dir.mkdir(parents=True, exist_ok=True)
                payment_file = payments_dir / f"{payment['date']}.json"
                
                # Load existing payments or create new
                payments = []
                if payment_file.exists():
                    with open(payment_file, 'r') as f:
                        payments = json.load(f)
                
                payments.append(payment)
                with open(payment_file, 'w') as f:
                    json.dump(payments, f, indent=2)
                
                # Update bill status
                bill['paid'] = True
                bill['paidDate'] = payment['date']
                bill['paymentId'] = payment['id']
                
                return bill
    
    return None


def process_folder(folder: Path, index: dict, payments_dir: Path) -> list:
    """Process all receipt emails in a folder."""
    processed = []
    
    if not folder.exists():
        print(f"Folder not found: {folder}")
        return processed
    
    for email_file in folder.glob("*.json"):
        try:
            with open(email_file, 'r') as f:
                email = json.load(f)
            
            bill = process_receipt_email(email, index, payments_dir)
            if bill:
                processed.append(bill)
                print(f"Marked paid: {bill['vendor']} - ${bill['amount']}")
        except Exception as e:
            print(f"Error processing {email_file}: {e}")
    
    return processed


def main():
    email_id = os.environ.get("EMAIL_ID")
    process_folder_path = os.environ.get("PROCESS_FOLDER")
    
    # Paths
    workspace = Path("/home/boss/.openclaw/workspace")
    index_path = workspace / "repos/bill-tracker/bills/index.json"
    payments_dir = workspace / "repos/bill-tracker/payments"
    
    # Load index
    index = load_index(index_path)
    print(f"Loaded {len(index['bills'])} bills")
    
    if email_id:
        # Process single email
        email = {"id": email_id, "subject": "Receipt", "snippet": "", "body": ""}
        bill = process_receipt_email(email, index, payments_dir)
        if bill:
            save_index(index_path, index)
            print(f"Marked paid: {bill['vendor']} - ${bill['amount']}")
        else:
            print("No matching bill found")
    
    elif process_folder_path:
        # Process folder
        folder = Path(process_folder_path)
        processed = process_folder(folder, index, payments_dir)
        if processed:
            save_index(index_path, index)
            print(f"Processed {len(processed)} payments")
        else:
            print("No payments processed")
    
    else:
        print("Usage: python mark_paid.py --email-id <msgId>")
        print("       python mark_paid.py --folder <receipts_folder>")
    
    # Update summary
    unpaid = [b for b in index['bills'] if not b['paid']]
    index['summary'] = {
        "totalUnpaid": round(sum(b['amount'] for b in unpaid), 2),
        "overdueCount": len(unpaid),
        "monthlyAverage": round(sum(b['amount'] for b in unpaid) / max(len(unpaid), 1), 2)
    }
    save_index(index_path, index)


if __name__ == "__main__":
    main()
