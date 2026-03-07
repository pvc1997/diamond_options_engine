#!/bin/bash
# VIX spike alert — warns when VIX conditions are extreme
# Runs during market hours on weekdays

HOUR=$(date +%H)
DOW=$(date +%u)

# Only on weekdays during market hours (9:15-15:30 IST)
if [ "$DOW" -gt 5 ]; then exit 0; fi
if [ "$HOUR" -lt 9 ] || [ "$HOUR" -gt 15 ]; then exit 0; fi

# This hook reminds about VIX awareness — actual VIX check happens via MCP tool
echo "<user-prompt-submit-hook>VIX CHECK: Before any trade, check India VIX with /vix. High VIX (>25) means reduce position sizes. Crisis VIX (>35) means hedges only.</user-prompt-submit-hook>"
