#!/bin/bash
# Position check — midday reminder on weekdays
# Runs at 12:30 PM to check positions during lunch

HOUR=$(date +%H)
MINUTE=$(date +%M)
DOW=$(date +%u)

# Only weekdays at 12:30 PM
if [ "$DOW" -gt 5 ]; then exit 0; fi
if [ "$HOUR" -ne 12 ]; then exit 0; fi
if [ "$MINUTE" -lt 25 ] || [ "$MINUTE" -gt 35 ]; then exit 0; fi

echo "<user-prompt-submit-hook>MIDDAY CHECK: Review open positions with /status. Check if any need adjustment with /risk.</user-prompt-submit-hook>"
