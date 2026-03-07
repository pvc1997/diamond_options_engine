---
description: Detects when positions need adjustment
auto_trigger: true
triggers:
  - position P&L is checked
  - spot price has moved significantly from entry
  - position is within 2 days of expiry
  - user checks position status
---

Automatic adjustment detection:

1. Check each open position:
   - Has spot moved > 1% from entry?
   - Is current P&L > 50% of max loss?
   - Is it within 2 days of expiry with ITM legs?
   - Has VIX spiked since entry?

2. If triggered, use `adjustment_advisor` with:
   - Current spot vs entry spot
   - Days remaining
   - Current P&L
   - Strategy type

3. Urgency levels:
   - Monitor: P&L < 25% of max loss, > 3 DTE
   - Consider: P&L 25-50% of max loss
   - Act: P&L > 50% of max loss or < 2 DTE with ITM
   - Immediate: P&L > 75% of max loss or expiry day with ITM

4. Always show the cost of adjusting vs doing nothing.
