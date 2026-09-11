#!/usr/bin/env python3
"""Batch process bill scan IDs from a file."""

import subprocess
import sys
import email
from email import policy
from pathlib import Path

HIMALAYA = "/home/boss/.local/bin/himalaya"
IDS_FILE = Path("/tmp/bill_scan_ids.txt")

if not IDS_FILE.exists():
    print(f"ERROR: {IDS_FILE} not found")
    sys.exit(1)

uids = [line.strip() for line in IDS_FILE.read_text().splitlines() if line.strip()]
total = len(uids)
print(f"Processing {total} emails...")

bills = receipts = skipped = errors = 0

for i, uid in enumerate(uids):
    # Read raw message
    result = subprocess.run(
        [HIMALAYA, "message", "read", uid, "--raw"],
        capture_output=True, timeout=30,
    )
    if result.returncode != 0 or not result.stdout:
        errors += 1
        continue

    # Parse email
    try:
        msg = email.message_from_bytes(result.stdout, policy=policy.default)
    except Exception:
        errors += 1
        continue

    subject = msg.get("Subject", "")
    # Get body as string
    body_str = ""
    for part in msg.walk():
        if part.get_content_type() == "text/plain":
            try:
                content = part.get_content()
                body_str = content.decode("utf-8", errors="replace") if isinstance(content, bytes) else str(content or "")
            except Exception:
                pass
            break

    # Fallback: HTML-only emails
    if not body_str:
        for part in msg.walk():
            if part.get_content_type() == "text/html":
                try:
                    content = part.get_content()
                    html = content.decode("utf-8", errors="replace") if isinstance(content, bytes) else str(content or "")
                    # Strip HTML tags to plain text
                    import re
                    body_str = re.sub(r"<[^>]+>", " ", html)
                    body_str = re.sub(r"\s+", " ", body_str).strip()
                except Exception:
                    pass
                break

    if not body_str:
        skipped += 1
        continue

    # Run bill-tracker scan
    scan = subprocess.run(
        ["bill-tracker", "scan", "--subject", str(subject), "--email-id", str(uid)],
        input=body_str.encode("utf-8"),
        capture_output=True, timeout=60,
        cwd="/home/boss/bill-tracker",
        env={**__import__("os").environ, "VIRTUAL_ENV": "/home/boss/bill-tracker/.venv",
             "PATH": "/home/boss/bill-tracker/.venv/bin:" + __import__("os").environ.get("PATH", "")}
    )

    output = scan.stdout.decode("utf-8", errors="replace") + scan.stderr.decode("utf-8", errors="replace")
    if "bill_stored" in output:
        bills += 1
    elif "receipt_stored" in output or "receipt_matched" in output:
        receipts += 1
    elif "skipped" in output or "neither" in output:
        skipped += 1
    else:
        errors += 1

    if (i + 1) % 10 == 0:
        print(f"[{i+1}/{total}] bills={bills} receipts={receipts} skipped={skipped} errors={errors}")

print(f"\n=== DONE ===")
print(f"Total: {total} | Bills: {bills} | Receipts: {receipts} | Skipped: {skipped} | Errors: {errors}")