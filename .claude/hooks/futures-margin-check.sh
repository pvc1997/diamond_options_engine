#!/bin/bash
# Futures margin check — runs on weekdays at 11:00 AM IST
# Monitors margin utilization across futures positions

HOUR=$(date +%H)
DOW=$(date +%u)  # 1=Monday, 7=Sunday

# Only run on weekdays at 11 AM
if [ "$DOW" -gt 5 ]; then exit 0; fi
if [ "$HOUR" -ne 11 ]; then exit 0; fi

echo "<user-prompt-submit-hook>FUTURES MARGIN CHECK: Midday margin monitoring. Use futures_portfolio_risk to check total margin utilization. Alert thresholds: >40% moderate, >60% high (no new positions), >80% critical (reduce exposure). Show per-position margin breakdown and suggest adjustments if needed.</user-prompt-submit-hook>"
