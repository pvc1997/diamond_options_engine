---
description: Adapts all recommendations based on current VIX regime
auto_trigger: true
triggers:
  - VIX is checked before a recommendation
  - user enters a trade in high/crisis VIX
  - market conditions change significantly
---

VIX regime adaptation:

| VIX Range | Regime    | Size Mult | Strategy Bias           |
|-----------|-----------|-----------|------------------------|
| < 12      | Low       | 1.0x      | Buy premium, calendars |
| 12-18     | Normal    | 1.0x      | Full strategy menu     |
| 18-25     | Elevated  | 0.75x    | Credit spreads         |
| 25-35     | High      | 0.5x     | Small credit spreads   |
| > 35      | Crisis    | 0.25x    | Hedges only            |

Actions by regime:
- **Low VIX:** Options are cheap — buy straddles, protection. Avoid selling premium.
- **Normal VIX:** All strategies available. Follow IV rank and direction.
- **Elevated VIX:** Lean credit. Reduce size. Wider wings on condors.
- **High VIX:** Only defined-risk credit strategies. Half normal size.
- **Crisis VIX:** No new premium selling. Protective puts, collars only. Quarter size.

Always check VIX before ANY trade recommendation.
