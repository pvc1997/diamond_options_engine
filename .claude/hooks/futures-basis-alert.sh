#!/bin/bash
# Futures basis alert — runs on weekdays at 10:00 AM IST
# Checks basis for open futures positions after market opens

HOUR=$(date +%H)
DOW=$(date +%u)  # 1=Monday, 7=Sunday

# Only run on weekdays at 10 AM
if [ "$DOW" -gt 5 ]; then exit 0; fi
if [ "$HOUR" -ne 10 ]; then exit 0; fi

echo "<user-prompt-submit-hook>FUTURES BASIS CHECK: Market is open. Scan basis for open futures positions. Alert if annualized basis > 8% (rich — consider selling) or < 4% (cheap — consider buying). Use basis_analysis tool for each position. Flag any mispricing opportunities.</user-prompt-submit-hook>"
