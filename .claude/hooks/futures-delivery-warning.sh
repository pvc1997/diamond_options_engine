#!/bin/bash
# Futures delivery warning — runs on weekdays at 9:00 AM IST
# Warns about physical delivery margin for stock futures near expiry

HOUR=$(date +%H)
DOW=$(date +%u)  # 1=Monday, 7=Sunday

# Only run on weekdays at 9 AM
if [ "$DOW" -gt 5 ]; then exit 0; fi
if [ "$HOUR" -ne 9 ]; then exit 0; fi

# Check if we're within 4 days of monthly expiry
DAY=$(date +%d)
MONTH_DAYS=$(date -d "$(date +%Y-%m-01) +1 month -1 day" +%d 2>/dev/null || echo "28")

if [ "$DAY" -gt $((MONTH_DAYS - 4)) ]; then
    echo "<user-prompt-submit-hook>DELIVERY MARGIN WARNING: Stock futures physical delivery margin increases to 40-50% in the final 4 days before expiry. Review open STOCK futures positions (not index — those are cash settled). Close or roll stock futures to avoid elevated margin. Use /futures-risk for position review and /futures-adjust for rollover guidance.</user-prompt-submit-hook>"
fi
