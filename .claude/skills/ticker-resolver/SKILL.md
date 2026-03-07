---
description: Resolves fuzzy stock/index names to exact F&O symbols
auto_trigger: true
triggers:
  - user mentions a stock or index name casually
  - user types partial ticker like "REL", "BN", "NIFTY"
  - user says company name like "Reliance", "TCS", "Infosys"
---

When the user mentions a stock or index name:

1. Use `search_fno` MCP tool to find matching F&O symbols
2. If exact match, use it silently
3. If multiple matches, ask user to clarify
4. If no match, inform that the stock is not in F&O universe
5. Common shortcuts:
   - BN, BNF, BANKNIFTY → BANKNIFTY
   - NF, NIFTY → NIFTY
   - FN, FINNIFTY → FINNIFTY
   - REL → RELIANCE
   - INFY → INFY (exact)

Always confirm the resolved symbol before executing trades.
