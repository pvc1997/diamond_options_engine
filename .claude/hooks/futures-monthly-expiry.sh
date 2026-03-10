#!/bin/bash
# Futures monthly expiry — runs on last Tuesday of the month at 9:00 AM IST
# Alerts about monthly futures expiry for all contracts

HOUR=$(date +%H)
DOW=$(date +%u)  # 1=Monday, 2=Tuesday, 7=Sunday

# Only run on Tuesdays at 9 AM
if [ "$DOW" -ne 2 ]; then exit 0; fi
if [ "$HOUR" -ne 9 ]; then exit 0; fi

# Check if this is the last Tuesday of the month
DAY=$(date +%d)
NEXT_TUESDAY=$((DAY + 7))
MONTH_DAYS=$(date -d "$(date +%Y-%m-01) +1 month -1 day" +%d 2>/dev/null || echo "28")

if [ "$NEXT_TUESDAY" -gt "$MONTH_DAYS" ]; then
    echo "<user-prompt-submit-hook>MONTHLY FUTURES EXPIRY: All stock and index futures expire today. INDEX futures (NIFTY, BANKNIFTY, FINNIFTY) will cash-settle automatically. STOCK futures with open positions will go to physical delivery — close before 3:00 PM to avoid. Run /futures-risk for full position review. Use futures_expiry_checklist_tool for each position.</user-prompt-submit-hook>"
fi
