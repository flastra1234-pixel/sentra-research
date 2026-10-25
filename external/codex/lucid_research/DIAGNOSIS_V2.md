# What the first research batch teaches us

Prepared 25 October 2026 from the saved trade logs and search results. **All 2026 performance described here is now research/development evidence. It must not be relabeled untouched or forward-tested in the next iteration.** No strategy has been retuned in this diagnosis.

## The immediate problem is a thin and unstable payoff margin

E028's two-MES 2026 baseline net was $715.66 across 158 trades, just $4.53 per trade. Its actual exit totals were:

| Exit | Trades | Total net | Mean net |
|---|---:|---:|---:|
| Target | 78 | $9,026.56 | $115.73 |
| Stop | 68 | −$8,651.14 | −$127.22 |
| Time | 12 | $340.24 | $28.35 |

Thus a nominal 1R target did not create a symmetric net payoff. The average stopped trade lost more than the average target earned. Baseline target trades averaged +0.9525R after costs, while stopped trades averaged −1.0443R. The ratio of average dollar target gain to average stop loss was 0.910. A target/stop-only system at that payoff would need about 52.37% winning exits just to break even; E028 achieved 53.42% among its target/stop exits, leaving little margin.

Stress changed net from +$715.66 to −$526.84, a $1,242.50 deterioration. Holding every outcome fixed, an extra tick per side would correspond to roughly $790 over 158 two-MES trades; actual execution was rerun and **five trades changed exit outcome**, including one target becoming a stop. This is a fill-sensitive edge, not merely an accounting fee problem.

Research implication: test larger net reward/risk, trailing/time exits, and entries with more room relative to spread/friction. Do not try to rescue this result by substituting optimistic target fills.

## Profit concentration and later deterioration

The five largest winners contributed $955.10. Removing those five changes 2026 baseline net to **−$239.44**. Removing the ten largest changes it to −$1,122.04. This does not by itself invalidate a strategy—trend-following often needs outliers—but a nominal 1R system with small overall profit has little resilience.

January–July produced +$1,707.20 across 110 trades, with a 58.18% positive-trade rate. August–the observed October produced −$991.54 across 48 trades, with a 47.92% positive-trade rate. Mean stop distance fell from 13.17 to 10.43 ES points. The adverse period therefore had both worse directional success and tighter risk distances; it was not simply the same win rate scaled to a lower-volatility contract.

Use coarse, causal regime hypotheses in new research, with a common rule tested across many chronological folds. A regime label assigned after observing the day's result is not tradeable.

## Tempting filters are unstable across periods

Two-MES baseline results by approximate opening-range width (twice the rounded stop distance):

| Opening range | Development net / trades | Validation net / trades | 2026 net / trades |
|---|---:|---:|---:|
| Up to 10 points | −$142.34 / 8 | −$52.48 / 1 | +$132.56 / 3 |
| 10–20 points | +$175.72 / 36 | −$374.60 / 20 | −$149.04 / 48 |
| 20–30 points | +$1,302.88 / 19 | +$500.38 / 19 | −$696.24 / 63 |
| 30–40 points | −$492.40 / 5 | +$570.26 / 13 | +$1,428.38 / 44 |

The development winner, 20–30 points, lost in 2026. Selecting the 2026 winner, 30–40 points, would reverse the development evidence. This is a clear example of why winner-only bin filters can mislead. If testing volatility filters, normalize the range to prior known volatility and test broad neighboring thresholds, rather than memorizing these dollar-point bins.

Entry-time results show a more interpretable but still posthoc hypothesis:

| Entry window, New York | Development net / trades | Validation net / trades | 2026 net / trades |
|---|---:|---:|---:|
| 10:00–10:29 | +$393.36 / 43 | −$439.40 / 30 | −$387.98 / 101 |
| 10:30–10:59 | −$147.20 / 15 | +$1,000.28 / 14 | +$1,360.66 / 33 |
| 11:00–11:59 | +$637.64 / 7 | −$27.34 / 8 | −$169.60 / 20 |
| 12:00–15:00 | −$39.94 / 3 | +$110.02 / 1 | −$87.42 / 4 |

The first opening-range break is often near 10:05, while waiting for a retest or confirmation may move entry later. Testing that structural behavior is preferable to calling the 10:30 bin a proven edge. The samples are small and its development result was negative.

Direction also changed: shorts generated $645.58 of the $843.86 development net, while longs generated $596.66 of the $715.66 2026 net. Under stressed execution, 2026 longs were −$38.34 and shorts −$488.50. Simply switching to long-only is not a demonstrated solution.

## Fixed contracts concealed changing account risk

E028's mean stop increased from 8.76 points in development to 11.81 points in validation and 12.34 points in 2026. At two MES, nominal stop risk is $10 per ES point, so a 20-point stop risks about $200 before exit friction. A short losing streak can consume much of Lucid's $1,000 allowance.

New research should test fixed cash risk—e.g. $60, $80 or $100 per trade—with integer micro sizing, conservative cost allowance and a maximum daily loss. If even one contract exceeds the risk budget, skip the trade. Do not force one contract or scale up after losses.

Lucid's five $100 profitable-day condition creates a practical tradeoff: reducing risk while retaining a 1R target can make winning days too small to qualify. A larger target such as 1.5R or 2R can create $100-plus net days with lower initial stop risk, but its hit rate must be measured, not assumed.

## What the Nasdaq failures add

- One-minute VWAP reversion had **0/81 profitable development variants**, median PF 0.85. A simple "price far from VWAP plus one reversal close" was weak before later validation, so adding tiny filters to that exact trigger has little evidential basis.
- One-minute failed-opening-range breakout had only **2/81 profitable development variants**. A one-bar poke back inside the range may be too weak a definition of a failed auction.
- One-minute ORB was positive in **54/81 development variants**, median PF 1.07; yet the eligible candidate lost in late-2025 validation. That broad development pattern is worth investigating through rolling regimes, not treating its best backtest as universal.
- Higher-timeframe EMA pullback had a development median PF 1.115, but its shortlisted examples subsequently returned PF 0.399 and 0.967. Most early studies reset EMAs each RTH day and used fast/slow crosses or simple pullbacks; richer trend-state definitions may be needed.
- Time-entry variants had development median PF 0.97 at 1R and 1.00 at 2R. The opening-momentum candidate T093 was effectively flat in validation (−$5.50, PF 0.998) and became −$309 under stress. It provides no robust time-of-day edge on its own.

## Six next hypotheses, not verified winners

1. **Breakout then retest:** establish an opening range, require a completed close outside, wait for a pullback to that boundary, and enter on rejection. Coarse retest windows and a few confirmation rules can test whether chasing the first breakout caused the loss.
2. **Trend-conditioned continuation:** combine a simple directional signal with information already available at entry, such as opening drive efficiency, VWAP slope and intraday trend alignment. Avoid layering every indicator together.
3. **A stronger failed-auction reversion:** require displacement outside an opening range, reclaim, and a confirmed move toward VWAP or the range midpoint; compare with the failed one-bar-poke definition.
4. **Volatility-normalized opportunity selection:** compare current opening range with prior-session range/ATR and enforce a minimum expected reward relative to friction. Use only prior completed sessions for rolling volatility and contract-aware handling for cross-day price levels.
5. **Exit architecture:** compare 1.5R/2R targets, time exits and simple trailing exits on the same causal entries. Evaluate payout-sized winning days and drawdown after fixed cash risk, not just gross P&L.
6. **A complementary session/market family:** evaluate afternoon momentum and separate micro-compatible markets using the same conservative execution model. A fleet should require low loss correlation and central exposure limits, rather than adding correlated equity-index breakouts.

Predeclare each expanded search, record every attempted configuration, prefer broad neighboring parameter stability and rolling chronological evaluation, and preserve genuinely new data for assessment when available. If no sufficiently new data exist, describe the next results as revised historical research with a prospective forward test still required.

Numeric source files: `diagnosis_trade_features.csv`, `diagnosis_tables.txt`, saved `final_results` trade logs, and each branch's `development_all.csv` / `validation_shortlist.csv`. No live orders or broker actions were performed.
