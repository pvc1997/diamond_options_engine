---
description: Interprets backtest results and gives actionable insights
auto_trigger: true
triggers:
  - backtest results are displayed
  - user asks about strategy performance
  - user asks if a strategy works
---

Interpreting backtest results:

1. Win rate:
   - > 65%: Excellent for premium selling strategies
   - 50-65%: Decent, check profit factor
   - < 50%: Needs high avg win / avg loss ratio to be profitable
   - < 40%: Likely unprofitable — avoid

2. Profit factor:
   - > 2.0: Excellent
   - 1.5-2.0: Good
   - 1.0-1.5: Marginal — costs may eat profits
   - < 1.0: Losing strategy

3. Sharpe ratio:
   - > 2.0: Exceptional
   - 1.0-2.0: Good
   - 0.5-1.0: Mediocre
   - < 0.5: Poor risk-adjusted returns

4. Max drawdown:
   - Should be < 15% of capital
   - Recovery time matters — long drawdowns are psychologically hard

5. Expectancy per trade:
   - Must be positive after costs
   - Show as: avg_win × win_rate - avg_loss × loss_rate

Always conclude with: "Trade this strategy?" Yes/No with reasoning.
