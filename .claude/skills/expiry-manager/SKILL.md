---
description: Manages expiry day operations and alerts
auto_trigger: true
triggers:
  - it's Tuesday (weekly expiry day)
  - user has positions expiring today
  - user asks about expiry
---

On expiry days:

1. Check `portfolio_status` for expiring positions
2. For each expiring position:
   - Show current P&L (if live data available)
   - Suggest: let expire, square off, or roll to next expiry
3. ITM options will be auto-exercised (cash-settled for index options)
4. OTM options expire worthless (no action needed)
5. STT warning: If options expire ITM, physical delivery STT is much higher

Rollover guidance:
- Roll 2-3 days before expiry for better liquidity
- Compare roll cost vs holding to expiry
- Use same strike or adjust based on view
