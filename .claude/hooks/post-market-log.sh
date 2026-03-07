#!/bin/bash
# Post-market log — runs at 3:30 PM on weekdays
# Reminds to review day's trades and positions

HOUR=$(date +%H)
MINUTE=$(date +%M)
DOW=$(date +%u)

# Only at 3:30 PM on weekdays
if [ "$DOW" -gt 5 ]; then exit 0; fi
if [ "$HOUR" -ne 15 ]; then exit 0; fi
if [ "$MINUTE" -lt 25 ] || [ "$MINUTE" -gt 35 ]; then exit 0; fi

echo "<user-prompt-submit-hook>MARKET CLOSED: Review today's options positions and P&L with /status.</user-prompt-submit-hook>"
