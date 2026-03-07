#!/bin/bash
# Pre-market scan — runs on weekdays between 8:45-9:30 AM IST
# Checks if today is expiry day and flags positions needing attention

HOUR=$(date +%H)
MINUTE=$(date +%M)
DOW=$(date +%u)  # 1=Monday, 7=Sunday

# Only run on weekdays, 8:45-9:30 AM
if [ "$DOW" -gt 5 ]; then exit 0; fi
if [ "$HOUR" -lt 8 ] || [ "$HOUR" -gt 9 ]; then exit 0; fi
if [ "$HOUR" -eq 8 ] && [ "$MINUTE" -lt 45 ]; then exit 0; fi
if [ "$HOUR" -eq 9 ] && [ "$MINUTE" -gt 30 ]; then exit 0; fi

# Tuesday = expiry day alert
if [ "$DOW" -eq 2 ]; then
    echo "<user-prompt-submit-hook>EXPIRY DAY: Weekly options expire today (Tuesday). Check open positions with /status and decide: square off, let expire, or roll.</user-prompt-submit-hook>"
fi
