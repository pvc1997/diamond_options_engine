#!/bin/bash
# Friday review reminder — runs at 4 PM on Fridays
# Prompts weekly portfolio review

HOUR=$(date +%H)
DOW=$(date +%u)

# Only Friday at 4 PM
if [ "$DOW" -ne 5 ]; then exit 0; fi
if [ "$HOUR" -ne 16 ]; then exit 0; fi

echo "<user-prompt-submit-hook>WEEKLY REVIEW: It's Friday — time to review this week's options trades. Use /status for positions and /history for trade log. Plan next week's strategy.</user-prompt-submit-hook>"
