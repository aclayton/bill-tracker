# Bill Tracker - Aaron Clayton (aclayton)

## Current State (2026-03-22)
**Prototype/MVP**: Local file-based tracker for recurring bills (8 tracked: utilities, mobile, subs, insurance; all CAD monthly).
- **Data**: `bills/bills.json` (version 1.0, last_updated 2026-03-19):
  | ID | Name | Category | Amount | Due Day | Status | Next Due | Notes |
  |----|------|----------|--------|---------|--------|----------|-------|
  | cogeco-main | Cogeco Cable/Internet | Utilities | $85.50 | 15 | paid | 2026-04-15 | High-speed + cable |
  | apple-subscription | Apple Services | Subscriptions | $19.95 | varies | paid | - | iCloud/Music |
  | telus-mobility | TELUS Mobility | Mobile | $116.17 | 20 | paid | 2026-04-20 | support.telus.com |
  | niagara-water | Niagara Region Water | Utilities | $100.00 | 15 | paid | 2026-04-15 | niagararegion.ca |
  | enbridge-gas | Enbridge Gas | Utilities | $133.33 | 16 | paid | 2026-04-16 | enbridgegas.com |
  | enercare-main | Enercare Bill | Utilities | -$4.70 | 14 | paid | 2026-04-14 | Credit balance |
  | car-insurance | Car Insurance | Insurance | $188.30 | 15 | auto | 2026-04-15 | Sun Life auto-pay |
  | npe-electricity | NPEI Electricity | Utilities | $108.41 | 7 | pending | 2026-04-07 | npei.ca (balance -$15.50) |
- **Totals (monthly est.)**: ~$751.04 (excl. credits/pending).
- **Dirs**:
  - `bills/`: JSON config (auto_track: true for email parsing).
  - `payments/`: Logs (empty).
  - `reports/`: Outputs (empty).
  - `scripts/`: Utils (TBD).
- **Integrations** (from memory/2026-03-21.md):
  - Merged PR #1 → #3: PR1 (core) + PR3 cron + HEARTBEAT batch/test.
  - GOG Gmail: Scans for bills (label:inbox unread <2h).
  - No live cron/PRs visible (local only; git needed).
- **Repo**: Not git-init'd. GitHub? None found (aclayton/time-tracker separate).

## Usage Guide
1. **View Bills**:
   ```
   cat bills/bills.json | jq '.bills[] | {name,amount,due_day,status,next_due}'
   ```
2. **Add/Edit Bill**:
   - Edit `bills/bills.json` (array of objects).
   - Fields: id, name, category, provider, amount, due_day, next_due, status (paid/pending/auto), notes, auto_track, tags.
3. **Generate Report** (manual):
   ```
   jq '[.bills[] | select(.status != "paid")] | {pending: length, total_due: (map(.amount) | add)}' bills/bills.json > reports/monthly.json
   ```
4. **Test HEARTBEAT/Cron**:
   - Sim: `GOG_ACCOUNT=1boss.ac.bot1@gmail.com gog gmail search 'bill|due|invoice' --max 5`
5. **Pay Bill**:
   - Manual: Update status/next_due in JSON.
   - Auto: Links/providers in notes.

## TODOs (Prioritized from MEMORY.md + Audit)
1. **HIGH**: `git init` + origin `https://github.com/aclayton/bill-tracker` (or new repo). Commit/PR workflow (sub-repos style).
2. **HIGH**: Cron job: Daily due reminders (GCal/Telegram; filter due <7d).
3. **MED**: GOG Gmail parser: Auto-update amounts/status from emails (label:bills).
4. **MED**: Reports: Monthly totals/charts (scripts/report.py → PDF/email).
5. **LOW**: Web UI (Astro? Embed in aaronc.ca).
6. **LOW**: Categories budget (e.g., utilities <20%).
7. **LOW**: Payments log (append paid dates/amounts).
8. **Test**: HEARTBEAT batch (email → bill update).

**Next**: `git init && gh repo create bill-tracker --public --push`? Spawn qwen for parser? 📊