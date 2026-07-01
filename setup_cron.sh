#!/bin/bash
# Set up a daily cron job that triages your inbox and pushes a Telegram summary.
# Usage: bash setup_cron.sh
#
# Customize before running:
#   INBOX_PYTHON  path to python that has inbox-to-action installed (default: which python3)
#   INBOX_CRON    cron schedule (default: "0 8 * * *" = 8:00 AM daily)
#   INBOX_SINCE   look-back window (default: 24h)

PYTHON="${INBOX_PYTHON:-$(command -v python3)}"
CRON_TIME="${INBOX_CRON:-0 8 * * *}"
SINCE="${INBOX_SINCE:-24h}"

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG="$PROJECT_DIR/scan.log"

if ! command -v "$PYTHON" &>/dev/null; then
    echo "Error: Python not found at '$PYTHON'. Set INBOX_PYTHON=/path/to/python and re-run."
    exit 1
fi

CRON_LINE="$CRON_TIME cd \"$PROJECT_DIR\" && \"$PYTHON\" -m inbox_to_action.main run --since $SINCE --telegram >> \"$LOG\" 2>&1"

if crontab -l 2>/dev/null | grep -qF "inbox_to_action.main run"; then
    echo "Cron job already set up. Edit with: crontab -e"
    exit 0
fi

(crontab -l 2>/dev/null; echo "$CRON_LINE") | crontab -
echo "Cron job added: $CRON_TIME  (window: $SINCE)"
echo "Python: $PYTHON"
echo "Logs:   $LOG"
echo "Remove with: crontab -e  (delete the inbox_to_action line)"
