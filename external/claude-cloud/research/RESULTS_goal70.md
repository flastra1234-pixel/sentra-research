# The "$100-150 on 70% of days" goal on LucidFlex 25K (2026-10-25)

Research only, not financial advice. Nothing here places orders.

## Bottom line
- **Can any strategy tested so far approach the goal? No.** The search covered 25,062 round-1
  variants and 86,898 round-2 variants with day filters, over 2020-2024 and any size up to 10
  micros. No round-2 variant reaches a 70% hit rate on the days it trades. Among the round-1
  variants, 26 reach a 70% hit rate: 23 09:30 gap fades and 3 Asia/London fades. 16 of those
  lose money. The 10 profitable ones make at most $38 a session at 10 micros and trade 12-36% of
  days. The goal needs a mean of roughly $40-60 a day with losing days capped near $100.
- **What the goal requires.** Simulated under the actual LucidFlex rules, 70% of days at +$125
  and every other day at -$100 gives an annualised Sharpe of about 9. Such an account survives
  81% of funded years and pays the owner about $940 a month. If losing days are -$150
  instead of -$100, survival falls to 13%. At -$200, it falls to 0.1%. For comparison, in
  2020-2024, before any deterioration:
  - the canonical strategy's Sharpe was about 1.2-1.5;
  - the frozen funded fleet reached 2.6 in-sample;
  - blind walk-forward fleets reached 0.6-2.3 in single years (2023-2024).

  The goal needs a Sharpe of about 6-9 (section 1). That is 3-4 times the best single blind
  year and 5-7 times the canonical strategy. No fleet was re-optimised for the 70% goal, because
  no combination of these sleeves comes close to that Sharpe.
- **Why noise-area momentum stopped working in 2025-2026.** Every year the median variant
  makes $73-198 per trend day and loses $38-80 on other days. Two things changed:
  - **Fewer trend days:** 45% in 2022, 34% in 2025, 32% in 2026.
  - **Less profit per trend day:** $126 in 2024, $105 in 2025, $82 in 2026.

  They contribute about equally, and smaller losses on other days partly offset them. Against
  the 2020-2024 average, an order-independent split of 2026's -$17.5 a session is: fewer trend
  days -$11.8, lower trend-day profit -$16.1, other days +$10.3. Against 2024, lower trend-day
  profit is the larger factor.

  The fall in trend days is not explained by VIX, VXN, VVIX or the VIX term structure (monthly
  Spearman correlations -0.02 to 0.12), and nothing tested predicts whether the rest of a day,
  after 10:00, will trend. Opening-range breakouts were marginal in every year. The other fleet
  families (drives, Asia/London breakouts) were not decomposed.
- **New predictive information.** Four hypotheses were pre-registered and tested on 2020-2024 with
  Holm control:
  - The canonical strategy earns more on CPI and jobs-report days.
  - It earns differently on FOMC days.
  - The rest of the day trends more often on event days.
  - It earns more when SPY's first 30 minutes agree in sign with NQ's.

  **None qualified.** The closest was SPY agreement: +$22 a session, with the same sign in all 5
  years, but p 0.19 (Holm 0.76). A second pre-registered round added three more signals:
  - VIX9D/VIX stress (N1);
  - QQQ's beta-adjusted lead (N2);
  - overnight agreement (N3).

  None qualified. N2 and N3 came close: p 0.018 and 0.027, same sign in 5 of 5 years, but Holm
  p 0.054 within the round and 0.13-0.16 across all seven tests. N1 went strongly the opposite
  way. Under the pre-registered rules, 2025-2026 was not used for either round. No new
  information has been *verified* to improve these strategies. The sources tested were:
  - NQ's own price and volume;
  - VIX and its term structure;
  - CPI, NFP and FOMC dates;
  - SPY and QQQ 1-minute bars.

  Order flow, bid/ask data, ES and options/0DTE data were not tested. A "confirmation" pattern (N2, N3,
  X1) and stress-day avoidance (N1) remain preliminary candidates for a forward test.
- **Recommendation.** **Do not buy an evaluation for this goal.** Nothing here gives convincing
  independent evidence. The forward-test protocol at the end says what would.

## 1. What the goal demands under LucidFlex rules (verified: rule simulation)
**Definitions and conventions.**
- **Eligible trading day:** a session the strategy's ex-ante rules allow it to trade. For a
  single variant those are its traded days. For a fleet or an account, every session is
  eligible.
- **Hit rates:** each table says whether it uses eligible days or all sessions. A hit means at
  least $100 net.
- **Costs:** all $ figures are net of costs:
  - $2.00 per round trip per micro;
  - 1 tick of slippage per fill;
  - 1 extra tick on stop exits;
  - about $1 per micro to flatten when a daily stop or lock triggers.
- **Price level:** every trade is priced at NQ 29,000 ($58,000 notional per micro, $2 a point).

**LucidFlex 25K rules simulated** (sentra-fleet-engine `fleet_engine/rules.py`):

| rule | value used |
|---|---|
| evaluation target | +$1,250 |
| evaluation consistency | largest day ≤ 50% of profit. The help center gives 40% without the add-on; 40% is shown as a sensitivity, and the add-on's cost is not in the fee |
| max loss | $1,000, trailing the highest end-of-day balance. A breach also counts on the intraday low |
| floor lock | the floor never rises above $25,100, and locks there at the first payout (a harsher reading) |
| payout eligibility | 5 days of at least +$100 since the last payout, and a positive cycle |
| payout request | min($1,000, 50% of profit above $25,000). $500 minimum. The 50% is the default reading |
| split | 90% to the trader |
| failure | the account ends; no reset is modelled |

Daily P&L is a two-point profile: exactly a fraction p of days at +win, the rest at -loss, in
random order. Losing days hit their low at the close. Each row is a 12-month funded account (252 sessions) under the
sentra-fleet-engine rules, simulated over 4,000 bootstrap paths.

| hit rate | win | loss | mean/day | annual Sharpe | 12-month survival | owner $/month |
|---|---|---|---|---|---|---|
| 0.7 | 125 | 100 | 57.5 | 8.9 | 81% | 943 |
| 0.7 | 125 | 150 | 42.5 | 5.4 | 13% | 377 |
| 0.7 | 125 | 200 | 27.5 | 2.9 | 0.1% | 132 |
| 0.7 | 150 | 150 | 60.0 | 6.9 | 27% | 651 |
| 0.7 | 100 | 100 | 40.0 | 6.9 | 52% | 549 |
| 0.8 | 125 | 200 | 60.0 | 7.3 | 23% | 607 |
| 0.6 | 150 | 100 | 50.0 | 6.5 | 44% | 643 |

These are the best case: days are independent, there are no fat tails, and no day loses more
than its stated loss. Real strategies are worse on every one of these points.

**The account is small next to the contract.** At today's price (about 29,000), the median
09:30-16:00 high-low range of one micro (MNQ) is $670-755. That uses 2024-2026 daily ranges
in % of price. The $1,000 trailing drawdown is therefore about 1.4 median days of range for a
single micro.

**What the goal needs** (from the table): survival depends mostly on how small the losing days
are. A mean of $40-60 a day works only with losses near $100. With -$150 losses, the buffer
policy below is needed. The goal's
$100 is about 0.17% of one micro's notional.

### Payout buffer (simulated): a large gain for small-loss profiles, negligible for the real fleets
By default, fleet_engine requests a payout as soon as one is allowed. After the first payout
the floor locks at $25,100, so each withdrawal moves the balance back toward the floor. A
different policy requests only the amount that leaves the balance at least $1,000 above the
locked floor (`goal70.funded_sim(buffer=1000)`):

| profile (p / win / loss) | survival, no buffer → $1,000 buffer | owner $/month, no buffer → $1,000 buffer |
|---|---|---|
| 0.7 / 125 / 100 | 81% → 99.8% | 943 → 991 |
| 0.7 / 125 / 150 | 13% → 88% | 377 → 674 |
| 0.7 / 150 / 150 | 27% → 93% | 651 → 1,009 |
| 0.6 / 150 / 100 | 44% → 97% | 643 → 840 |

The first payout comes about 10-14 sessions later. Buffers above $1,000-1,500 cost more in
delay than they gain in survival. The buffer helps only when daily losses are small compared
with $1,000. On the real walk-forward fleets, whose daily SD is about $450-535, survival rose
only from 4.1% to 4.4% (2023) and from 0.3% to 0.4% (2024).

## 2. Can existing strategies or combinations approach it? (design 2020-2024; 2025-26 scorecard rows descriptive only)
**Single variants.** The search covered 25,062 round-1 variants, 1,267 design sessions, and
at least 150 traded days per variant. The hit rate is measured on eligible days, meaning the
days each variant trades.

| micros | specs with hit ≥ 70% | of those, mean > $0/session | of those, mean ≥ $48 (mid-range of the $40-60 needed) | best mean among them |
|---|---|---|---|---|
| 2 | 12 | 5 | 0 | $7.5 |
| 4 | 23 | 10 | 0 | $15.1 |
| 6 | 25 | 10 | 0 | $22.6 |
| 10 | 26 | 10 | 0 | $37.7 |

The top entries are mostly 09:30 gap fades (0.5-1.0 ATR stop, exit at 15:55), plus one
Asia/London fade. They trade 12-35% of days and are up $100+ on 72-80% of the days they trade.
The gap family produced no gate survivors in the earlier search, so these are not significant
edges.

The 86,898 round-2 variants add ex-ante day filters to these specs. **None** reaches a 70% hit
rate on 150 or more traded days, at any size. The best is 69.6% on 50 or more traded days, and
42.9% on all sessions.

**Fleets with a daily profit lock.** A profit lock does raise the hit rate, but it destroys the
expectancy. The funded fleet frozen on 2020-2024 (8 micros) makes +$125 a day in-sample with no
lock. Locking at $125 with no stop gives a 70% hit rate, but the mean falls to **-$43 a day**.
That is because the momentum edge lives in the few large days a lock cuts off. A zero-edge
version reverses each day's trades at random, marked just as pessimistically. With a $125 lock
and $150-300 stops, the funded fleet's zero-edge version reaches 42-58% hit rates and loses
$36-41 a day. The real fleet under the same lock and stops loses $38-44. This is an in-sample
illustration from a single random draw, not a test. A high hit rate is easy to manufacture.
A high hit rate with positive expectancy is not.
(A $100 lock shows a 0% hit rate only because the overlay books lock minus slippage, $92 for
8 micros, which falls below $100.)

**Walk-forward out-of-sample fleets at reduced size.** Selected on earlier years and traded
blind, with the $1,000 payout buffer. These numbers assume size can be split below one micro,
so they are an upper bound.

| test year | fleet | ~micros | mean/day | hit ≥ $100 | 12-month survival | owner $/month |
|---|---|---|---|---|---|---|
| 2023 | eval | 0.9 | $15 | 22% | 41% | $164 |
| 2023 | funded | 1.0 | $12 | 18% | 68% | $128 |
| 2024 | eval | 1.0 | $13 | 19% | 91% | $159 |
| 2024 | eval | 1.5 (chosen after the fact) | $20 | 25% | 59% | $236 |
| 2024 | funded | 1.0 | $4 | 14% | 29% | $43 |

At full size (3-5 micros), the account survives 0.4-7.6% of funded years, with the buffer.
**At about 1 micro, the best realistic case is $43-164 a month per account, with hit rates of
14-22%.** The $236 row is 1.5 micros, picked after seeing the test year's size frontier. Even
$164 is roughly a sixth of the payout goal and less than a third of the hit-rate goal, and it
comes from years when the edge still worked.

**Complete account economics per evaluation bought** (`goal70_report.scorecard`). Each path buys
an evaluation and trades the eval fleet until it passes. The eval fleet keeps the $600 daily
profit lock it was selected with, scaled down with size. The path then trades the funded fleet.
- **Horizon:** 12 months (252 sessions).
- **Payout policy:** standard, with no buffer.
- **Breach:** ends the account; there is no reset.
- **Days:** resampled from the blind walk-forward year.
- **Fee:** $89-149.

| candidate | mean/day | hit ≥ $100: all days / eligible days | longest losing streak / days under $100 | worst day | max drawdown | eval pass ≤ 10 sessions | payout within 21 / 42 sessions | median sessions to 1st payout, among those paid | funded 12-month survival | owner $ per evaluation, 12 months | net of fee | owner $ per evaluation at 40% consistency |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| walk-forward 2023, full size (3 / 5 micros) | $58 | 39% / same | 8 / 11 | -$1,164 | -$5,230 | 26% | 8.6% / 12% | 18 | 4.1% | $464 | $315-375 | $406 |
| walk-forward 2023, ~1 micro † | $12 | 18% / same | 8 / 17 | -$233 | -$1,046 | 0.1% | 0.0% / 0.6% | 119 | 17% | $600 | $451-511 | $600 |
| walk-forward 2024, full size (5 / 5) | $22 | 45% / same | 6 / 9 | -$2,296 | -$8,146 | 26% | 8.4% / 11% | 17 | 0.3% | $197 | $48-108 | $167 |
| walk-forward 2024, ~1 micro † | $4 | 14% / same | 6 / 22 | -$459 | -$1,629 | 0.0% | 0.0% / 0.0% | 175 | 5.8% | $237 | $88-148 | $237 |
| walk-forward 2025, full size (3 / 6) ‡ | -$10 | 38% / same | 6 / 9 | -$2,199 | -$11,062 | 22% | 4.5% / 5.2% | 16 | 0.2% | $75 | -$74 to -$14 | $62 |
| walk-forward 2025, ~1 micro † ‡ | -$2 | 13% / same | 6 / 22 | -$366 | -$1,844 | 0.0% | 0.0% / 0.2% | 104 | 1.1% | $48 | -$101 to -$41 | $48 |
| walk-forward 2026, full size (5 / 3) ‡ | -$24 | 33% / same | 12 / 20 | -$836 | -$9,563 | 17% | 4.8% / 5.4% | 16 | 0.1% | $74 | -$75 to -$15 | $64 |
| walk-forward 2026, ~1 micro † ‡ | -$8 | 20% / same | 12 / 24 | -$279 | -$3,188 | 0.0% | 0.0% / 0.0% | 105 | 0.0% | $13 | -$136 to -$76 | $13 |
| canonical strategy, 1 micro, 2020-2024 | $25 | 22% / 36% | 8 / 11 | -$1,902 | -$6,105 | 5.2% | 0.7% / 7.0% | 45 | 3.5% | $367 | $218-278 | $318 |

How to read the table:
- The mean, hit-rate, streak and drawdown columns describe the funded fleet's actual year.
- Streaks count eligible days. For fleets that is every session; for the canonical strategy it
  is its traded days.
- † These rows cut a 3-6 micro fleet to one micro in total, i.e. about 0.2-0.3 micro per
  sleeve. That size cannot actually be traded, so these rows are an upper bound and not a
  plan.
- ‡ These rows were already reported in `RESULTS_2020plus.md`. They describe what a buyer would
  have experienced, and nothing is selected from them.

**This table is not a case for buying.** In 2023-2024 the average evaluation returned a few
hundred dollars over a year. That average was driven by a minority of paths: at full size only
11-12% paid within 42 sessions, and funded survival was 0.3-4%. Among evaluations that paid at
all, the first payout came after a median of 17-18 sessions at full size and 100+ at about 1
micro. In 2025-2026 every evaluation lost money net of the fee. A breach caps the loss at the
fee while lucky paths still get paid, which is why even negative-mean years return some money.
The stricter 40% consistency rule lowers full-size returns by another 10-15%.

**The canonical noise-area momentum strategy alone**, 2020-2024: $25 a session per micro,
Sharpe 1.2. At 1 micro it trades 61% of days and is up $100+ on 36% of its eligible (traded)
days, which is 22% of all sessions. Its worst
day was -$1,902 at 1 micro (March 2020). Its 12-month funded survival is 5-9% at 1-8 micros,
with the $1,000 buffer.

## 3. Why noise-area momentum deteriorated in 2025-2026 (explanatory, no selection)
Per-session market structure, 09:30-16:00 ET (`lx_diag`):

| | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|---|
| trend days (abs(close - open) ≥ 0.6 × range) | 35% | 43% | 45% | 40% | 37% | 34% | 32% |
| post-10:00 move / day range | 0.415 | 0.433 | 0.451 | 0.447 | 0.400 | 0.392 | 0.378 |
| high or low set after 14:00 | 66% | 58% | 68% | 61% | 54% | 57% | 46% |
| overnight share of the day's move | 0.446 | 0.415 | 0.388 | 0.412 | 0.447 | 0.449 | 0.481 |
| opening-range follow-through (median, OR widths) | 0.02 | 0.13 | 0.18 | 0.15 | 0.09 | 0.13 | 0.06 |
| gap filled (abs gap > 0.25 ATR) | 37% | 46% | 41% | 44% | 36% | 38% | 28% |
| variance ratio, 30-minute | 0.939 | 0.991 | 1.044 | 1.000 | 1.052 | 0.969 | 0.959 |
| RTH range (% of price) | 2.14 | 1.35 | 2.39 | 1.41 | 1.27 | 1.47 | 1.41 |

**Momentum on trend days and on other days.** Median over all noise-area variants, 1 micro:

| | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|---|
| $ per trend day | 141 | 73 | 198 | 93 | 126 | 105 | 82 |
| $ per other day | -73 | -38 | -79 | -43 | -42 | -47 | -39 |
| trend share | 35% | 43% | 45% | 40% | 37% | 34% | 32% |
| break-even trend share | 34% | 34% | 29% | 31% | 25% | 31% | 32% |
| $ per session | 1.0 | 9.7 | 43.6 | 11.5 | 18.0 | 4.7 | -1.5 |

**What changed, split three ways.** Median $ per session is written as share × trend-day $ +
(1 - share) × other-day $. Each figure below averages the two decomposition orders
(`diagnostics.noise_change_split`).

| change | total $/session | fewer trend days | lower trend-day profit | other days |
|---|---|---|---|---|
| 2025 vs 2020-2024 average | -12.7 | -9.4 | -8.1 | +4.8 |
| 2026 vs 2020-2024 average | -17.5 | -11.8 | -16.1 | +10.3 |
| 2025 vs 2024 | -15.4 | -4.3 | -7.6 | -3.4 |
| 2026 vs 2024 | -20.2 | -7.0 | -15.3 | +2.1 |

Fewer trend days and lower profit per trend day contributed about equally. Against 2024, the
last year the edge worked, lower trend-day profit is the larger factor. The two orders differ
by up to about $5 for each factor.

The structure table points the same way. In 2026 more of each day's move happens overnight,
before a 09:30 strategy can trade, and less of it continues after 10:00. Late-day extremes fell
from 54-68% to 46%, which fits less trend continuation into the close. Gaps fill less often.

**Other families.** The same split for 09:30 opening-range breakouts (median variant, 1 micro):

| | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|---|
| $ per trend day | 30 | 26 | 55 | 24 | 33 | 30 | 28 |
| $ per other day | -21 | -18 | -40 | -21 | -11 | -17 | -21 |
| break-even trend share | 41% | 42% | 42% | 47% | 24% | 37% | 42% |
| $ per session | -1.7 | 1.1 | 5.5 | -2.6 | 6.1 | -1.2 | -5.6 |

ORB was marginal in every year: it broke even only when about 40% of days trended, and was
already negative in 2020 and 2023. Gap fades were about zero throughout. The 2025-2026
walk-forward fleets were mostly drives, ORB and Asia/London breakouts. This report does not
decompose the drives or the Asia/London breakouts, so their decline is unexplained here.

**What does not explain it.** Monthly trend-day share has almost no correlation with VIX
(0.03), VXN (0.00), VVIX (0.07) or the 9-day/30-day term structure (0.12): Spearman over 82
months. Over 2020-2024, the unconditional lag-1 autocorrelation of 30-minute returns is +0.004
(15,204 pairs, 09:30-16:00 grid). Any trend that momentum captures is therefore conditional,
showing up only on some days or after band breaks, rather than a general drift. The earlier
finding that variance ratios were about 0.8 (mean reversion) was an estimator bias, now fixed.
The corrected ratios are 0.93-1.09. Explanations such as 0DTE options hedging or crowding of the
published method fit the timing, but this data cannot test them.

## 4. New predictive information (2020-2024 design, chronological)
**Scans with no hits (Holm-corrected).** Two scans looked for features that predict a day's
outcome:
- Whether the rest of the day is a trend day.
- Whether the canonical strategy profits on a day it trades.

The 18 features were all known at 10:00 ET:
- Volume vs its 20-day average.
- Overnight range and opening-range width in ATR.
- Gap size.
- The 09:30-10:00 move in ATR, and ATR(14).
- 30-minute efficiency.
- Volatility ratio.
- Trailing trend frequency and trailing strategy P&L.
- Previous day's type.
- OPEX, month-end and day of week.
- VIX and its prior-day change.

Each feature's sign was learned on the years before each test year (2022, 2023, 2024). The
statistic is the mean of the three test-year AUCs, with a within-year permutation p-value.
- Best for "the rest of the day trends" (label: after 10:00, the 16:00 close is at least half
  the post-10:00 range from the 10:00 price; base rate 51%): a *lower* trailing 20-day strategy
  P&L. Mean AUC 0.541, p 0.024, Holm p 0.43.
- Best for profit on traded days: a prior-day VIX *fall*. Mean AUC 0.555, p 0.018, Holm p 0.32.
  It reverses in 2023 (AUC 0.46).

An earlier version of this scan seemed to find signals in opening-range width and 30-minute
efficiency. That was an artifact: those features predict *whether* the strategy trades, which
was confounded with whether it profits.

**Two simple filters on the canonical strategy (2021-2024) both hurt.**

| rule | mean $/session | Sharpe | traded days |
|---|---|---|---|
| R0 trade every day | 29.17 | 1.51 | 628 |
| R1 only if trailing 20-day P&L > 0 | 9.21 | 0.57 | 437 |
| R2 only if VIX rose the prior day | -0.15 | -0.01 | 292 |
| R1 and R2 | -4.61 | -0.41 | 208 |

R1 and R2 trade the opposite direction to the one the scan learned from earlier years. Their
failure therefore agrees with the scan and is not separate evidence. The learned direction
(trade after a losing month, or after VIX fell) did not survive Holm correction either, so no
filter was adopted.

**Pre-registered event-calendar and cross-asset tests** (`PREREGISTRATION.md`,
`lx_prereg.py`). Canonical strategy at 1 micro, 2020-2024. The permutation p-values shuffle the
day type within each year (20,000 draws). The Holm correction covers all four tests.
- **Calendar:** BLS, Fed and BEA release dates, cross-checked against 20 public compilations.
  Released events only: CPI and NFP at 08:30, FOMC statements at 14:00.
- **SPY:** consolidated-tape 1-minute bars, 2019-12 to 2026-09.

| test | day type | flagged / other sessions | effect, $/session | effect, $/traded day | p | Holm p | years with same sign | qualified |
|---|---|---|---|---|---|---|---|---|
| E1 | CPI or NFP day (one-sided) | 115 / 1,152 | +11.7 | +20.9 | 0.36 | 1.00 | 2 of 5 | no |
| E2 | FOMC statement day (two-sided) | 38 / 1,229 | +12.5 | +4.4 | 0.81 | 1.00 | 4 of 5 | no |
| E3 | rest of day trends, on any event day (one-sided) | 151 / 1,116 | -5.5 pp (46% vs 51%) | n/a | 0.91 | 1.00 | 3 of 5 | no |
| X1 | SPY's 09:30-10:00 sign agrees with NQ's (one-sided) | 957 / 279 | +21.7 | +30.6 | 0.19 | 0.76 | 5 of 5 | no |

To qualify, a test needed all three of:
- a Holm p below 0.05;
- the same sign in at least 4 of 5 years;
- at least $25 per traded day (or 5 points for E3).

Only X1 met the sign and size conditions, and it is far from significant. E1's yearly effects
were -92, -34, +45, -7 and +131: noise around zero. Event days were slightly *less* likely to
trend after 10:00, the opposite of E3.

On the account view, X1 changes nothing. At 1 micro with the $1,000 buffer, 12-month survival
is 8% for X1 and 6% for trading every day, and both pay about $102 a month. **Because nothing
qualified, the single 2025-2026 look was not run** (`results/goal70.json` → `prereg.single_look`).

### Round 2 of pre-registered tests (`PREREGISTRATION_round2.md`, `lx_prereg2.py`)
Round 2 tested three more day-level signals, each with its own rationale. They were committed
before running, at 8857be7 and a0b00d2. The canonical strategy was run at 1 micro, 2020-2024,
one-sided, with Holm correction both within the round and across all seven hypotheses of both
rounds.

| test | day type | flagged / other | effect, $/session | effect, $/traded day | p | Holm, round 2 | Holm, all 7 | years with same sign | qualified |
|---|---|---|---|---|---|---|---|---|---|
| N1 | prior-close VIX9D / VIX ≥ 1 (expected: better) | 311 / 956 | **-50.4** | -83.5 | 0.99 | 0.99 | 1.00 | 5 of 5 (all *negative*) | no |
| N2 | QQQ's beta-adjusted 09:30-10:00 lead agrees with NQ | 773 / 312 | +42.6 | +68.3 | 0.018 | 0.054 | 0.126 | 5 of 5 | no |
| N3 | NQ's 16:00 → 09:30 move agrees with its 09:30-10:00 move | 620 / 647 | +36.7 | +48.5 | 0.027 | 0.054 | 0.162 | 5 of 5 | no |

**Nothing qualified, so 2025-2026 was not touched for round 2 either.**

N2 and N3 just missed: p 0.018 and 0.027, with the same sign in all five years. Together with X1
(SPY agreement, +$22, 5 of 5 years) they suggest one pattern: the strategy does better when the
first-30-minute move is *confirmed* by other information.

N1 came out strongly in the *opposite* direction to the one registered. On days after
short-dated stress (VIX9D at or above VIX), the strategy lost $13 a session against +$37 on
other days, and that held in all five years. Because N1 was registered one-sided as "better",
this is not a finding. Flipping it now would be the same snooping the protocol exists to
prevent.

**An in-sample illustration, not evidence.** The rules below were chosen after seeing these
results, on the same 2020-2024 data, with the $1,000 buffer.

| rule | days traded | mean/day | Sharpe | hit ≥ $100, all days | worst day | 12-month survival | owner $/month |
|---|---|---|---|---|---|---|---|
| every day, 1 micro | 61% | $25 | 1.21 | 22% | -$1,902 | 6% | $104 |
| N3 and not N1, 1 micro | 25% | $18 | 1.47 | 9% | -$1,301 | 37% | $126 |
| N2 and N3 and not N1, 1 micro | 20% | $17 | 1.49 | 8% | -$1,301 | 44% | $115 |

Even with hindsight, the filters lift the Sharpe only from about 1.2 to 1.5. They mainly help
survival by trading fewer days. That is nowhere near the Sharpe of 6-10 the 70% goal needs.

## 5. Verified improvements vs preliminary discoveries
**Verified**: rule simulation, code checked against the fleet engine, or a chronological
test on 2020-2024 with multiple-testing control.
1. **What the goal costs.** Under LucidFlex rules, "+$100-150 on 70% of days" with sustainable
   survival needs an annualised Sharpe of about 6-9, with losing days capped near $100
   ($150 with the payout buffer) (section 1). `goal70.funded_sim` reproduces fleet_engine's `run_funded` exactly at buffer 0.
2. **Payout buffer (a rule-level simulation).** Requesting only what leaves the balance $1,000
   above the locked floor raises 12-month survival a lot for synthetic small-loss profiles:
   13% → 88% and 27% → 93%. Owner payouts also rise, and the first payout comes about 10-14
   sessions later. It barely helps strategies whose daily swings are large compared with
   $1,000, which includes every fleet found here. It is an improvement to keep for a future
   strategy, not one that rescues these.
3. **Sizing for survival.** On the blind walk-forward years 2023-2024, cutting fleets to about
   1 micro raises 12-month survival from 0.4-7.6% to 29-91%, with the $1,000 buffer. The
   owner's monthly amount goes from $56-155 at full size to $43-164 at about 1 micro. The 2024
   funded fleet is the weakest at either size. This is an upper bound, because it assumes size
   can be split below whole micros.
4. **No new predictor survives.** This covers the 18 features known at 10:00, VIX,
   CPI/NFP/FOMC days, SPY confirmation, VIX term structure, QQQ leadership and overnight
   agreement: seven pre-registered hypotheses in two rounds (section 4).
5. **Method fixes caught by review, all before the conclusions were drawn:**
   - variance-ratio bias;
   - a label confound (traded vs profitable);
   - zero-edge path marking;
   - exact synthetic hit rates;
   - a direction bug in the pre-registered single look, fixed before the first run.

**Preliminary**: descriptive, on data already examined, or not significant.
1. **Why noise-area momentum faded in 2025-2026.** Fewer trend days and lower profit per
   trend day contributed about equally, and smaller losses on other days partly offset them.
   Against 2024, lower trend-day profit is the larger factor. This is descriptive only: nothing
   predicts trend days in advance, so it explains the decline but cannot be traded. Drives and
   Asia/London breakouts were not decomposed.
2. 2026 structure: more of each day's move happens overnight (48% share), fewer highs or lows
   come after 14:00 (46%), and fewer gaps fill (28%). That is one partial year.
3. SPY confirmation (X1): +$22 a session with the same sign in all five design years, but not
   significant (p 0.19). At most a candidate filter for a forward test. It is not evidence.
4. The learned directions "trade after a losing month" and "trade after VIX fell" do not
   survive Holm correction.
5. Event days may trend slightly less after 10:00 (46% vs 51%). Not significant.
6. **Confirmation pattern.** The strategy did better when the first 30 minutes were confirmed by:
   - QQQ's beta-adjusted lead (N2): +$43 a session, p 0.018;
   - the overnight move (N3): +$37 a session, p 0.027;
   - SPY (X1): +$22 a session.

   All three held in 5 of 5 design years, but none survived Holm correction.
7. **Short-dated VIX stress hurts the strategy** (N1, the opposite of the registered direction):
   -$13 a session after VIX9D ≥ VIX, against +$37 otherwise, in 5 of 5 years.
8. **Profit locks create hit rate, not edge.** This is an in-sample illustration. A $125 lock
   gives the frozen funded fleet a 70% hit rate and turns +$125 a day into -$43 a day. With the
   same lock and $150-300 stops, a zero-edge version does about as well as the real fleet.

**Not tested:**
- order flow and bid/ask data, which `RESULTS_2020plus.md` named as the first lead;
- ES futures: the 1-minute data, 2020-01 to 2026-10-09, arrived after both rounds had been run, and has not been tested;
- options and 0DTE positioning data.

These are the only candidates worth a forward test. They are written down here, before any
forward data exists:
- trade the canonical strategy only when the overnight move agrees with the first 30 minutes;
- skip days after VIX9D ≥ VIX;
- optionally, also require QQQ's lead to agree.

Even in-sample, they cannot reach the 70% goal.

## 6. Recommendation and forward-test protocol
**Do not buy a LucidFlex evaluation for this goal.**
- No strategy tested comes close to "+$100-150 on 70% of days", even in-sample on 2020-2024.
- The best blind out-of-sample result at about 1 micro was $43-164 a month per account with
  a 14-22% hit rate. Even that is an upper bound, because it needs fractional sizing. That came from years when the edge still worked, and the edge has
  since faded.
- None of the new information tested restores it.

Two reference profiles show the gap:
- 3:1 reward:risk at 60% wins has a Sharpe of about 11.
- 70% of days at +$125 against -$100 has a Sharpe of about 9.

That is about 4-5 times the best single blind walk-forward year (2.3) and 6-9 times the
canonical strategy (1.2-1.5).

**The forward test is now frozen.** `PREREGISTRATION_forward.md` and `factory/forward.py` were
committed before any session after 2026-10-23 existed. They define two candidates:
- **C1:** overnight agreement, skipping VIX9D ≥ VIX days.
- **C2:** C1 plus agreement with QQQ's lead.

Each is compared with the canonical strategy (C0) at two milestones:
- **60 sessions:** the account-goal criteria below.
- **250 sessions:** a Holm-corrected Sharpe and survival comparison. Only a pass here would
  count as a verified economic improvement.

`python -m factory.forward` reports progress as new sessions are added to the data cache.

**What would count as convincing evidence.** This is a forward test, frozen before it starts,
for this or any future idea:
1. **Freeze.** Commit the code, parameters, size, daily stop and payout-buffer policy before the
   first forward session.
2. **Run.** Trade 60 or more sessions after 2026-10-23 on paper or a simulator, net of $2 per
   round trip plus real slippage. Log every fill, each day's P&L and its intraday low.
3. **Check execution.** Average slippage must be within 1 tick per fill of the model. A
   backtest replay of the same sessions must match the live daily P&L (correlation ≥ 0.9).
4. **Check the goal.** On the forward days, all of these must hold:
   - at least 70% of eligible days end at +$100 or more. Eligible days are the sessions the
     frozen rules allow trading, and the rule must allow at least 3 sessions a week;
   - the mean is at least $40 per session over all sessions;
   - the worst day is no worse than -$150;
   - a LucidFlex simulation (`goal70.funded_sim`, $1,000 buffer) never breaches.
5. **Check against zero edge.** The mean beats a sign-flipped zero-edge baseline at one-sided
   p < 0.05.

Why 60 sessions is enough here: an edge good enough for this goal (Sharpe 6-9) shows a
t-statistic of about 3-4.4 within 60 sessions. A Sharpe-1.2 strategy like the ones found here
would need about six years to reach t = 3, and a Sharpe-2.3 fleet about 1.7 years. No affordable test could separate it from luck before it hit the
$1,000 drawdown. Only after a candidate passes all five checks would buying one evaluation be
justified, sized for survival as in section 2 and using the payout buffer.

## 7. Test-integrity log
- In this goal70 work, strategy selection, every threshold, the scans and the filter rules used
  2020-2024 only. Two earlier choices sit outside that rule. The 2026 walk-forward fold, from
  the earlier process test in `RESULTS_2020plus.md`, used 2025 as its validation year. The
  range illustration in section 1 uses 2024-2026 daily ranges.
- 2025-2026 was used only in these ways:
  - Explanatory market-structure statistics (section 3). They select no strategy.
  - The per-evaluation economics of the walk-forward folds reported earlier (section 2). These
    are descriptive.
  - The single pre-registered looks (section 4, rounds 1 and 2). Each runs only if a hypothesis
    qualifies on 2020-2024. None did, so neither was run. The hypotheses and criteria
  (`PREREGISTRATION.md`, 8fb22c1) and the test code (`lx_prereg.py`, first at 4c7d4b7) were
  committed before any event-calendar or SPY result was computed. The VIX-level scans and the
  R1/R2 filters had already been run, and `PREREGISTRATION.md` lists them as examined. Three changes were made before the first run, after
  review, and each is in its own commit:
  - c0c237c: count only released CPI/NFP at 08:30 and FOMC statements at 14:00. This drops the
    two emergency FOMC actions of March 2020.
  - e1bae35: derive SPY's 09:30-10:00 return.
  - 05d468c: two fixes and one tightening.
    - Fix: score the single-look direction check on the oriented flag.
    - Fix: restrict X1 to sessions with SPY data in every view.
    - Tightening: require the traded-day effect to share the per-session effect's sign.
- Round 2 was pre-registered at 8857be7 and its code frozen at a0b00d2, both before it was run.
  Its motivation for N1 cites a monthly correlation of 0.12 between VIX9D/VIX and trend-day
  share. That correlation is positive, in N1's registered direction, and was computed on months
  that include 2025-2026. Motivating statistics should have used 2020-2024 only. N1 failed
  anyway.
  One pre-run amendment redefined N2 as beta-adjusted leadership. It was based on a
  flag-frequency check only, with no P&L seen, and is documented in the round-2 file.
- The calendar file marks 28 releases as rescheduled after the 2025 and 2026 government
  shutdowns. Those dates were not known in advance. All 28 fall in 2025-2026, which no test
  used, so the design-period event flags are unaffected.
- 2025-2026 had already been examined in `RESULTS_2020plus.md`, so no result on it counts as
  fully independent. That is why the recommendation requires a forward test.

## 8. Reproduce
```
cd research
PYTHONPATH=. python3 -m factory.goal70_report          # all sections -> results/goal70.json
PYTHONPATH=. python3 -m pytest -q tests
```
Files:
- `factory/goal70.py`: daily profile, funded simulator with payout buffer, frontiers.
- `factory/lx_diag.py`: market structure.
- `factory/lx_newinfo.py`: 10:00 ET features and scans.
- `factory/lx_prereg.py`, `factory/lx_prereg2.py`: pre-registered tests, rounds 1 and 2.
- `factory/forward.py`: the frozen forward test (`PREREGISTRATION_forward.md`).
- `factory/goal70_report.py`: report driver.
