#!/usr/bin/env python3
"""
Gmail Bill Scanner - Auto-parse bills from Gmail search and update index.json

Usage:
  python parse_bills.py --older-than 30d --max-results 50
"""

import json
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import subprocess


def load_index(path: Path) -> dict:
    """Load bills/index.json or return empty structure."""
    if path.exists():
        with open(path, 'r') as f:
            return json.load(f)
    return {"lastUpdated": "", "bills": [], "summary": {"totalUnpaid": 0, "overdueCount": 0, "monthlyAverage": 0}}


def save_index(path: Path, data: dict) -> None:
    """Save bills/index.json with pretty formatting."""
    data["lastUpdated"] = datetime.utcnow().isoformat() + "Z"
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)


def extract_vendor_and_amount(text: str) -> Optional[dict]:
    """Extract vendor and amount from email body using regex patterns."""
    text = text.lower()
    
    # Common bill vendors with patterns
    patterns = {
        "enbridge": r"enbridge.*(?:bill|statement|amount)\s*[:\$]?\s*(\d+\.?\d*)",
        "enercare": r"enercare.*(?:bill|statement|amount)\s*[:\$]?\s*(\d+\.?\d*)",
        "npei|npe|hydro": r"(?:npei|npe|hydro).*?(?:bill|statement|amount)\s*[:\$]?\s*(\d+\.?\d*)",
        "cogeco": r"cogeco.*(?:bill|statement|amount)\s*[:\$]?\s*(\d+\.?\d*)",
        "schoolcash": r"schoolcash.*(?:bill|statement|amount)\s*[:\$]?\s*(\d+\.?\d*)",
        "td|td bank": r"(?:td|td bank).*?(?:bill|statement|amount)\s*[:\$]?\s*(\d+\.?\d*)",
        "apple": r"apple.*(?:bill|statement|amount)\s*[:\$]?\s*(\d+\.?\d*)",
        "openrouter": r"openrouter.*(?:bill|statement|amount)\s*[:\$]?\s*(\d+\.?\d*)",
        "new balance": r"new balance.*(?:bill|statement|amount)\s*[:\$]?\s*(\d+\.?\d*)",
    }
    
    for vendor, pattern in patterns.items():
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return {"vendor": vendor, "amount": float(match.group(1))}
    
    return None


def scan_gmail(older_than: str = "30d", max_results: int = 50) -> list:
    """
    Scan Gmail for bills using gog CLI.
    Returns list of email subjects and snippets.
    """
    # Build gog command
    query = f'newer_than:{older_than} (bill OR invoice OR payment OR due OR statement OR receipt OR "overdue" OR Enbridge OR Enercare OR Cogeco OR NPE OR "NPEI" OR SchoolCash OR TD OR "hydro one")'
    
    cmd = [
        "gog", "gmail", "search", query,
        f"--max={max_results}",
        "--json"
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode == 0:
            # Parse JSON output
            lines = result.stdout.strip().split('\n')
            emails = []
            for line in lines:
                if line.strip():
                    try:
                        emails.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
            return emails
        else:
            print(f"GOG error: {result.stderr}", file=sys.stderr)
            return []
    except Exception as e:
        print(f"Error scanning Gmail: {e}", file=sys.stderr)
        return []


def parse_email_body(email: dict) -> str:
    """Extract body text from email."""
    # Try multiple fields that might contain the body
    for field in ['snippet', 'body', 'text', 'raw']:
        if field in email:
            return email[field]
    return ""


def process_emails(emails: list, existing_bills: dict) -> list:
    """Process emails, extract bill info, merge with existing."""
    new_bills = []
    
    for email in emails:
        body = parse_email_body(email)
        vendor_data = extract_vendor_and_amount(body)
        
        if not vendor_data:
            continue
        
        # Create bill ID from vendor and amount
        bill_id = f"{vendor_data['vendor'].replace(' ', '-').lower()}-{datetime.utcnow().strftime('%Y%m')}"
        
        # Check if bill already exists
        exists = any(b['id'] == bill_id for b in existing_bills)
        if exists:
            continue
        
        new_bills.append({
            "id": bill_id,
            "vendor": vendor_data['vendor'].title(),
            "amount": vendor_data['amount'],
            "dueDate": (datetime.utcnow() + timedelta(days=14)).strftime("%Y-%m-%d"),
            "paid": False,
            "receipt": None,
            "category": "utilities" if "npe" in vendor_data['vendor'].lower() or "enbridge" in vendor_data['vendor'].lower() else "other"
        })
    
    return new_bills


def main():
    older_than = os.environ.get("OLDER_THAN", "30d")
    max_results = int(os.environ.get("MAX_RESULTS", "50"))
    
    # Paths
    workspace = Path("/home/boss/.openclaw/workspace")
    index_path = workspace / "repos/bill-tracker/bills/index.json"
    
    # Load existing bills
    existing = load_index(index_path)
    print(f"Loaded {len(existing['bills'])} existing bills")
    
    # Scan Gmail
    print(f"Scanning Gmail for bills (newer than {older_than})...")
    emails = scan_gmail(older_than, max_results)
    print(f"Found {len(emails)} potential bill emails")
    
    # Process new bills
    new_bills = process_emails(emails, existing['bills'])
    print(f"Extracted {len(new_bills)} new bills")
    
    # Merge and save
    existing['bills'].extend(new_bills)
    save_index(index_path, existing)
    
    # Update summary
    unpaid = [b for b in existing['bills'] if not b['paid']]
    existing['summary'] = {
        "totalUnpaid": round(sum(b['amount'] for b in unpaid), 2),
        "overdueCount": len(unpaid),
        "monthlyAverage": round(sum(b['amount'] for b in unpaid) / max(len(unpaid), 1), 2)
    }
    save_index(index_path, existing)
    
    print(f"Updated index.json with {len(existing['bills'])} total bills")
    print(f"Unpaid: {existing['summary']['overdueCount']} | Total: ${existing['summary']['totalUnpaid']}")


if __name__ == "__main__":
    main()
