# Bill Tracker Repo Separation Plan

## Current State Analysis

**Current repo:** repos/bill-tracker/
- Contains data only (no code yet)
- bills/index.json - Bill data (18 bills, v1.5 compatible)
- reports/ - Audit report markdown files
- SETUP.md - Documentation
- TELEGRAM_SUMMARY.md - Summary log

**Goal:** Split into two repos:
1. bill-tracker-core/ - Code only
2. bill-tracker-data/ - Data only

---

## Step-by-Step Execution Plan

### Phase 1: Create New Repository Structure

mkdir -p repos/bill-tracker-core/scripts
mkdir -p repos/bill-tracker-data/bills
mkdir -p repos/bill-tracker-data/reports
mkdir -p repos/bill-tracker-data/plans
mkdir -p repos/bill-tracker-data/payments

### Phase 2: Copy Data Files

cp repos/bill-tracker/bills/index.json repos/bill-tracker-data/bills/index.json
cp repos/bill-tracker/reports/*.md repos/bill-tracker-data/reports/
cp repos/bill-tracker/reports/*.timestamp repos/bill-tracker-data/reports/ 2>/dev/null || true

### Phase 3: Create Code Files in bill-tracker-core/

#### Create .gitignore

cat > repos/bill-tracker-core/.gitignore << GITIGNORE
# Data files (in separate repo)
bills/
*.json
reports/
payments/
plans/*.md

# Python cache
__pycache__/
*.pyc
*.pyo
*.so
.Python

# Environment
.env
.venv/
env/
venv/
ENV/

# IDE
.idea/
.vscode/
*.swp
*.swo
*~

# OS
.DS_Store
Thumbs.db
GITIGNORE

#### Create README.md

cat > repos/bill-tracker-core/README.md << README
# Bill Tracker Core

Code for tracking and analyzing bills from email data.

## Installation

pip install -r requirements.txt

## Usage

### Set DATA_PATH

export DATA_PATH=../bill-tracker-data

Or use CLI argument:
python scripts/report.py --data-path ../bill-tracker-data

### Generate Report

python scripts/report.py

### Track Bills

python tracker.py

## Data Structure

- bills/index.json - All bill records (JSON format)
- reports/ - Generated audit reports (Markdown)
- payments/ - Payment history (Markdown)

## Configuration

- DATA_PATH (env): Path to data directory (default: ../bill-tracker-data)
- DATA_FILE (env): Bill data filename (default: index.json)

## Requirements

- Python 3.8+
README

#### Create requirements.txt

cat > repos/bill-tracker-core/requirements.txt << REQS
google-api-python-client>=2.0.0
google-auth-httplib2>=0.1.0
google-auth-oauthlib>=0.5.0
REQS

### Phase 4: Initialize Git Repositories

cd repos/bill-tracker-core && git init && git add . && git commit -m "Initial commit: Bill tracker core code"
cd repos/bill-tracker-data && git init && git add . && git commit -m "Initial commit: Bill tracker data v1.5"
cd ../..
gh repo create aclayton/bill-tracker-core --private --push
gh repo create aclayton/bill-tracker-data --private --push

### Phase 5: Test Integration

cd repos/bill-tracker-core
DATA_PATH=../bill-tracker-data python scripts/report.py

### Phase 6: Cleanup Old Repository

cd ../..
mv bill-tracker bill-tracker.backup
# Verify both new repos work
# Then: rm -rf bill-tracker.backup

---

## Notes

- Version: bill-tracker-data starts at v1.5 (bills/index.json)
- DATA_PATH: Default is ../bill-tracker-data (relative to bill-tracker-core root)
- Backward compatibility: New scripts use argparse for CLI and env vars for configuration

PLAN COMPLETE - Ready for execution.
