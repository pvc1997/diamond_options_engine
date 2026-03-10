#!/bin/bash
# Futures rollover alert — runs on weekdays at 9:00 AM IST
# Warns when monthly futures expiry is approaching (within 7 days)

HOUR=$(date +%H)
DOW=$(date +%u)  # 1=Monday, 7=Sunday

# Only run on weekdays at 9 AM
if [ "$DOW" -gt 5 ]; then exit 0; fi
if [ "$HOUR" -ne 9 ]; then exit 0; fi

# Check if we're in a rollover window (last 7 days before monthly expiry)
# Monthly expiry is last Tuesday of the month
DAY=$(date +%d)
MONTH_DAYS=$(date -d "$(date +%Y-%m-01) +1 month -1 day" +%d 2>/dev/null || echo "28")

if [ "$DAY" -gt $((MONTH_DAYS - 7)) ]; then
    echo "<user-prompt-submit-hook>FUTURES ROLLOVER WINDOW: Monthly futures expiry approaching. Use /futures-risk to check open futures positions. For each position, run /futures-basis to compare near vs next month carry cost. Consider rolling 2-3 days before expiry for better fills. Stock futures: watch for delivery margin increase.</user-prompt-submit-hook>"
fi
