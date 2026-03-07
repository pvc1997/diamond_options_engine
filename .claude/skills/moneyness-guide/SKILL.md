---
description: Explains moneyness and helps with strike selection
auto_trigger: true
triggers:
  - user asks which strike to choose
  - user asks about ITM, ATM, OTM
  - user is selecting strikes for a strategy
---

Moneyness guide:

1. Definitions:
   - ITM: Call strike < spot, Put strike > spot
   - ATM: Strike ≈ spot (within 0.5%)
   - OTM: Call strike > spot, Put strike < spot
   - Deep ITM: |moneyness| > 5%
   - Far OTM: |moneyness| > 5%

2. Strike selection by strategy type:
   - **Directional long:** ATM or 1 strike OTM (best delta/cost ratio)
   - **Credit spread short leg:** 1-2 strikes OTM (probability edge)
   - **Iron condor short strikes:** ~1 standard deviation OTM (~16% ITM probability)
   - **Protective puts:** 5% OTM (insurance without paying too much)

3. NIFTY strike conventions:
   - 50-point strikes
   - 1 strike OTM = 50 points = ~0.2% OTM
   - 1 standard deviation (weekly) ≈ 200-300 points

4. Use `greeks_comparison` to compare delta/theta across strikes.
5. Use `probability_itm` to show probability for each strike.
