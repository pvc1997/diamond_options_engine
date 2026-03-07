#!/bin/bash
# Expiry alert — Monday evening reminder for Tuesday expiry
# Runs at 6 PM on Mondays

HOUR=$(date +%H)
DOW=$(date +%u)

# Only Monday at 6 PM
if [ "$DOW" -ne 1 ]; then exit 0; fi
if [ "$HOUR" -ne 18 ]; then exit 0; fi

echo "<user-prompt-submit-hook>EXPIRY TOMORROW: Weekly options expire tomorrow (Tuesday). Review positions with /status and plan: square off, roll, or let expire.</user-prompt-submit-hook>"
