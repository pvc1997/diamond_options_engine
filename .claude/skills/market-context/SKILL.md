---
description: Provides market context before any trading action
auto_trigger: true
triggers:
  - user asks about market conditions
  - user wants to trade or analyze options
  - user asks "should I trade today?"
---

Before any trade suggestion:

1. Check `market_status` — is market open? Is it expiry day?
2. Check `is_expiry_today` — flag if positions need attention
3. Consider the day:
   - Monday: Fresh week, new positions OK
   - Tuesday: Expiry day for weekly options — avoid opening new weekly positions
   - Friday: Plan for next week
4. If market is closed, note that prices are from last close

Provide context naturally without overwhelming the user.
