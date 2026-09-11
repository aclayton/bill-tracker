---
name: bill-tracker
description: Scan Gmail for bills and receipts, track payments, generate reports
---

# Bill Tracker

## Daily Scan

1. Use the himalaya skill to search for bills:
   `himalaya gmail messages list "bill OR invoice OR due OR statement" --page-size 30`
2. Use the himalaya skill to search for receipts:
   `himalaya gmail messages list "receipt OR payment confirmation OR thank you for your payment" --page-size 30`
3. For each result, read the message content:
   `himalaya gmail messages get <id>`
4. Pipe subject + body to: `bill-tracker scan --subject "..." --email-id "..."` via stdin
5. Report new bills found AND any receipts that were auto-matched to bills

## 15th of Month Report

1. Run `bill-tracker report`
2. Send the output to the user via Telegram
3. The report includes: unpaid bills table, recently paid bills, unmatched receipts, discovered vendors
4. Ask: "Pay all these? Reply `yes` to mark all as paid, or `vendor amount` for individual bills."
5. On confirmation, run `bill-tracker mark-paid --all --date YYYY-MM-15`

## Deep Scan (historical data)

To rebuild the database from Gmail history:
1. Use the himalaya skill to search: `himalaya gmail messages list "bill OR invoice OR receipt OR payment" --page-size 50`
2. Run `bill-tracker backup` first to preserve existing data
3. Pipe each email through `bill-tracker scan` as in the daily scan
4. Run `bill-tracker report` to verify results

## Manual Commands

- `bill-tracker list --unpaid` — show all unpaid bills
- `bill-tracker list --receipts` — show all receipts
- `bill-tracker list --unmatched` — show receipts with no matching bill
- `bill-tracker vendors` — list known and discovered vendors
- `bill-tracker mark-paid --vendor "Enbridge Gas" --date YYYY-MM-DD` — mark specific vendor paid
- `bill-tracker report --month YYYY-MM` — report for a specific month