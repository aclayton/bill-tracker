# Gmail Bill Audit Report
**Generated:** 2026-04-13 16:06:50
**Status:** AUTHENTICATION REQUIRED

## Note

This audit requires Gmail API access which needs OAuth authentication.

## To Complete the Audit

1. Install dependencies:
   pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib

2. Ensure OAuth credentials are at ~/.config/gogcli/credentials.json

3. Run the audit script:
   python3 bill_auditor.py

4. Follow the OAuth prompt to authorize

## Bill Keywords

The script searches for emails containing:
- bill, due, invoice, payment, receipt, statement
- utility, hydro, internet, phone, cell, rogers
- comcast, xfinity, telus, water, gas, electric
- credit card, amex, visa, mastercard, insurance
- subscription, netflix, spotify

## Expected Output Format

### bills/index.json
Array of bill objects with:
- id: Gmail message ID
- from: Sender email
- subject: Email subject
- date: Email date
- amount: Extracted amount
- provider: Service provider name
- due_date: Due date (if found)
- status: paid/unpaid/overdue
- bill_type: utility/internet/phone/credit/subscription/insurance/loan

### reports/gmail-audit-YYYY-MM-DD.md
Markdown report with:
- Summary statistics
- Detailed bill table
- Full JSON data

## Next Steps

Please run the audit script manually to complete the Gmail bill audit.
