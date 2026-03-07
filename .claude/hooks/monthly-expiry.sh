#!/bin/bash
# Monthly expiry alert — last Tuesday of month
# Additional warning for stock F&O expiry

HOUR=$(date +%H)
DOW=$(date +%u)
DAY=$(date +%d)
DAYS_IN_MONTH=$(date -v+1m -v1d -v-1d +%d 2>/dev/null || date -d "$(date +%Y-%m-01) +1 month -1 day" +%d 2>/dev/null)

# Only Tuesday
if [ "$DOW" -ne 2 ]; then exit 0; fi
if [ "$HOUR" -ne 9 ]; then exit 0; fi

# Check if this is the last Tuesday (day > days_in_month - 7)
THRESHOLD=$((${DAYS_IN_MONTH:-28} - 7))
if [ "$DAY" -gt "$THRESHOLD" ]; then
    echo "<user-prompt-submit-hook>MONTHLY EXPIRY: This is the monthly F&O expiry. ALL stock options expire today (not just index weeklies). Check stock option positions with /status.</user-prompt-submit-hook>"
fi
