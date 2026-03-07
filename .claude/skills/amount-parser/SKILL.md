---
description: Parses natural language amounts to INR values
auto_trigger: true
triggers:
  - user mentions money amounts in lakhs, crores, K, L, Cr
  - user says "2 lakhs", "50K", "1 crore", "half my capital"
---

Parse Indian currency expressions:
- "2 lakhs" / "2L" → 200000
- "50K" / "50 thousand" → 50000
- "1 crore" / "1Cr" → 10000000
- "half my capital" → check portfolio_status for capital, divide by 2
- "10% of capital" → check portfolio_status, calculate 10%
- "2% risk" → max_risk_per_trade_pct from config

Always confirm the parsed amount before executing trades.
