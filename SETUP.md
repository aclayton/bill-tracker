# Gmail Bill Audit Setup

## Overview

This script audits your Gmail for bill-related emails and extracts financial data.

## Prerequisites

1. Python 3.8+
2. Google Cloud Project with Gmail API enabled
3. OAuth credentials (client_id, client_secret)

## Setup

### 1. Install Dependencies

pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib

### 2. OAuth Setup

1. Go to Google Cloud Console
2. Create a new project or select an existing one
3. Enable the Gmail API
4. Create OAuth 2.0 credentials:
   - Application type: Desktop app
   - Download the credentials JSON file
5. Copy the credentials to ~/.config/gogcli/credentials.json

### 3. Authorize

Run the audit script and follow the OAuth prompt:

python3 bill_auditor.py

The script will open a browser window for you to authenticate.

## Usage

python3 bill_auditor.py

## Output

- bills/index.json - All extracted bill data
- reports/gmail-audit-YYYY-MM-DD.md - Human-readable report

## Bill Keywords

The script searches for emails containing:
bill, due, invoice, payment, receipt, statement
utility, hydro, internet, phone, cell, rogers
comcast, xfinity, telus, water, gas, electric
credit card, amex, visa, mastercard, insurance
subscription, netflix, spotify
