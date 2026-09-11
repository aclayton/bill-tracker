#!/usr/bin/env bash
set -euo pipefail

# Bill Tracker v3 — Installer
# This script:
# 1. Checks Python >= 3.11
# 2. Creates a virtual environment if it doesn't exist
# 3. Installs the package in editable mode
# 4. Runs the interactive config setup
# 5. Prints next steps

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "============================================"
echo "  Bill Tracker v3 — Installer"
echo "============================================"
echo ""

# --- Check Python version ---
PYTHON=""
for candidate in python3 python3.11 python3.12 python3.13 python; do
    if command -v "$candidate" &>/dev/null; then
        ver=$("$candidate" -c 'import sys; print(sys.version_info[:2])' 2>/dev/null || true)
        if [[ "$ver" == "(3, 11)" || "$ver" == "(3, 12)" || "$ver" == "(3, 13)" ]]; then
            PYTHON="$candidate"
            break
        fi
    fi
done

if [[ -z "$PYTHON" ]]; then
    echo "ERROR: Python 3.11+ is required. Install it and try again."
    exit 1
fi

echo "Using Python: $PYTHON ($($PYTHON --version))"
echo ""

# --- Create virtual environment ---
VENV_DIR=".venv"
if [[ ! -d "$VENV_DIR" ]]; then
    echo "Creating virtual environment in $VENV_DIR..."
    "$PYTHON" -m venv "$VENV_DIR"
    echo "Virtual environment created."
else
    echo "Virtual environment already exists at $VENV_DIR"
fi

# Activate
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"
echo "Activated virtual environment."
echo ""

# --- Install package ---
echo "Installing bill-tracker in editable mode with dev dependencies..."
pip install -e ".[dev]" 2>&1 | tail -5
echo ""

# --- Run interactive setup ---
echo "Running interactive setup..."
echo ""

# Use expect-like behavior: if stdin is a terminal, run interactively.
# Otherwise, skip and print instructions.
if [[ -t 0 ]]; then
    bill-tracker install
else
    echo "Non-interactive mode detected. Skipping setup wizard."
    echo "Run 'bill-tracker install' later to configure your setup."
fi

echo ""
echo "============================================"
echo "  Installation Complete!"
echo "============================================"
echo ""
echo "Next steps:"
echo "  1. Edit vendors.yaml to add your known vendors"
echo "  2. Review config.yaml and report.yaml"
echo "  3. Test: echo 'test' | bill-tracker scan --subject 'Test' --email-id 'test123'"
echo "  4. Set up Hermes cron job for daily scanning"
echo "  5. Run: bill-tracker --help"
echo ""