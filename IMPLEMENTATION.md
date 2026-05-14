# Bill Tracker v2 - Implementation Status

**Status:** ✅ Core scripts implemented, ready for testing

**Date:** 2026-05-14

---

## Implemented Components

### 1. Directory Structure
```
repos/bill-tracker/
├── bills/
│   └── index.json          # Bill database (mocked Apr-May data)
├── payments/
│   └── YYYYMMDD.json      # Payment records (auto-created on mark_paid)
├── reports/
│   └── bill-tracker-report-YYYYMMDD.{md,html}  # Generated reports
└── scripts/
    ├── parse_bills.py      # Gmail scan → parse → upsert index.json
    ├── mark_paid.py        # Receipt scan → mark paid → update index
    └── report.py           # MD/HTML reports (summaries/projections)
```

### 2. Scripts

#### `scripts/parse_bills.py`
- **Purpose:** Scan Gmail for bills → extract vendor/amount → upsert bills/index.json
- **Usage:** 
  - `python parse_bills.py`
  - `OLDER_THAN=30d MAX_RESULTS=50 python parse_bills.py`
- **Features:**
  - GOG Gmail search (30d bills/unread)
  - Regex patterns for Enbridge/Enercare/NPE/Cogeco/etc.
  - Deduplication (id = vendor + month)
  - Automatic summary recalculation

#### `scripts/mark_paid.py`
- **Purpose:** Process receipt emails → mark bills paid → record payments
- **Usage:**
  - `python mark_paid.py --email-id <msgId>` (single email)
  - `PROCESS_FOLDER=receipts/ python mark_paid.py` (batch)
- **Features:**
  - Regex patterns for payment confirmations
  - Payment records at `payments/{date}.json`
  - Updates `bills[index].paid = true`

#### `scripts/report.py`
- **Purpose:** Generate MD/HTML reports
- **Usage:**
  - `python report.py --format md`
  - `python report.py --format html`
  - `python report.py --format both`
- **Features:**
  - Unpaid/overdue tables (with days late)
  - Category breakdown
  - Payment history (last 10)
  - Projections
  - Visual HTML with CSS styling

---

## Pending / Next Steps

### 1. Test Scripts with GOG
```bash
# Test Gmail scan (needs GOG auth)
cd repos/bill-tracker
source ~/.openclaw/workspace/.env
GOG_ACCOUNT=1boss.ac.bot1@gmail.com python scripts/parse_bills.py
```

### 2. Setup Cron Jobs
**Daily scan (8PM EST):**
```bash
0 20 * * * cd /home/boss/.openclaw/workspace/repos/bill-tracker && source ~/.openclaw/workspace/.env && python scripts/parse_bills.py
```

**15th of month alert (Telegram):**
```bash
# Add to crontab or use OpenClaw cron
0 8 15 * * cd /home/boss/.openclaw/workspace/repos/bill-tracker && python scripts/report.py --format md && cat reports/bill-tracker-report-$(date +\%Y-\%m-\%d).md | telegram-send
```

### 3. Update Cron e46cbfe0-a6eb-4e07-82c1-8193027823bd
Update cron job to use new `parse_bills.py`:
- **Current:** `Daily Bill Tracker Gmail` (error)
- **Fix:** Change payload to run `scripts/parse_bills.py`

### 4. Git Workflow
```bash
cd repos/bill-tracker
git checkout -b feature/v2-implementation
git add bills/index.json scripts/*.py
git commit -m "feat: v2 implementation - parse_bills, mark_paid, report scripts"
git push origin feature/v2-implementation
gh pr create --title "feat: v2 implementation - auto-bill-scan + payment-track" --body "..."

# After testing
git checkout main
git merge feature/v2-implementation
git push
```

### 5. Documentation
- Update README.md with v2 process
- Add example output (sample report.md)
- Document GOG auth troubleshooting

---

## Sample Output (from mocked data)

**Unpaid/Overdue (May 14):**
| Vendor | Amount | Due Date | Days Late |
|--------|--------|----------|-----------|
| Enbridge Gas | $92.45 | 2026-04-14 | 30 |
| Enercare | $24.99 | 2026-04-11 | 33 |
| NPEI Electricity | $108.30 | 2026-04-07 | 37 |
| TD Bank | $12.50 | 2026-04-15 | 29 |

**Total Unpaid:** $393.24 CAD (5 overdue)

**Projections:** ~$400 CAD next cycle (avg $80-100/mo)

---

## Status Check
- [x] Directory structure created
- [x] bills/index.json (mocked)
- [x] scripts/parse_bills.py
- [x] scripts/mark_paid.py
- [x] scripts/report.py
- [ ] GOG test (auth required)
- [ ] Cron update (e46cbfe0...)
- [ ] Git commit/PR
- [ ] README update

**Ready for:** Testing with real Gmail data, cron setup, PR merge
