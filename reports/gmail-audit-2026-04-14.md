# Gmail Bill Audit Report
**Generated:** 2026-04-14 18:49:21 UTC
**Status:** AUTHENTICATION REQUIRED

## Note

This audit requires Gmail API access which needs OAuth authentication.

## Authentication Required

The `gog` CLI tool is not currently authenticated. To complete the audit:

### Option 1: Using gog CLI (Recommended)
1. Get OAuth credentials from Google Cloud Console:
   - Go to Google Cloud Console
   - Create/select a project
   - Enable Gmail API
   - Create OAuth 2.0 credentials (Desktop app)
   - Download credentials JSON

2. Authenticate gog:
```bash
gog auth credentials /path/to/client_secret.json
gog auth add aaronc@protonmail.ch --services gmail
```

3. Run search commands:
```bash
gog gmail search from:(TD.com OR enbridge.com OR enercare.ca OR cogeco.ca OR npeicanada.ca OR niagarawater.ca) newer_than:30d --max 100
```

### Option 2: Python Script
If you prefer the Python script approach:
```bash
pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib
python3 bill_auditor.py
```

## Bill Keywords to Search

The audit searches for emails containing these keywords:
- **General:** bill, due, invoice, payment, receipt, statement
- **Utilities:** hydro, utility, water, gas, electric
- **Providers:** TD, Enbridge, Enercare, Cogeco, NPEI, Niagara Water
- ** Telecom:** phone, cell, rogers, comcast, xfinity, telus
- **Financial:** credit card, amex, visa, mastercard, insurance
- **Subscriptions:** netflix, spotify, subscription

## Next Steps

1. Complete OAuth authentication using one of the methods above
2. Run the search commands for your bill providers
3. Extract bill details (amount, due date, provider, status)
4. Update `bills/index.json` with the data
5. Run this audit again for a complete report

## Last Checked
2026-04-14 18:49:21 UTC
