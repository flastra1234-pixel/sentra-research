# Sentra: overnight inventory, failed auctions and order-flow evidence

Research date: October 25, 2026, America/New_York. This is a primary-source review and hypothesis specification, not a profitability result. No trading experiment or reserved-data performance was examined for this review.

## What the literature supports

### 1. Boyarchenko, Larsen and Whelan — The Overnight Drift

[Federal Reserve Bank of New York Staff Report 917](https://www.newyorkfed.org/research/staff_reports/sr917); [published RFS paper](https://academic.oup.com/rfs/article-abstract/36/9/3502/7076616).

The authors document positive equity-index-futures returns near European market openings and a relationship with preceding US-close order imbalances, consistent with inventory-risk compensation. Reversals following selloffs are stronger than those following rallies. This supports investigating observable residual demand pressure and the arrival of new liquidity, not assuming every overnight move represents trapped directional inventory. Dealer positions themselves are not directly observed by our existing bars.

**Scope:** an overseas-opening phenomenon and its historical sample. It does not establish a profitable 9:30 a.m. US failed-auction rule or Lucid-compatible withdrawals.

### 2. Critical original-author qualifications and updated evidence

[NYFed 2021 explanation](https://libertystreeteconomics.newyorkfed.org/2021/05/the-overnight-drift-in-us-equity-returns/): US-opening reversal was not simply reversal of the overnight drift. Their relationship was weakly positive, and significant negative opening returns were concentrated on Thursdays and Fridays in that sample. The post describes prior-close signed-volume imbalance, not candle direction, as relevant evidence.

[NYFed July 1, 2026 update](https://libertystreeteconomics.newyorkfed.org/2026/07/the-disappearing-overnight-drift/): the authors report the 2–3 a.m. ET premium averaged close to zero in January 2021–December 2025, including similar flattening in NQ/YM. They investigate closing-imbalance dispersion, volatility and liquidity-provider risk-bearing capacity; a decline in the first is central to their explanation. The update is a research commentary by the original authors, not a new claim of a tradable solution. The documented post-publication decline is a strong reason to measure conditional information and structural change rather than recycle an unconditional clock-time trade.

### 3. Cont, Kukanov and Stoikov — The Price Impact of Order Book Events

[Author manuscript](https://arxiv.org/abs/1011.6402); Journal of Financial Econometrics 12(1), 2014.

Using NYSE trades and quotes for 50 stocks, the authors relate short-interval price changes to net supply/demand changes at best bid/ask. Their order-flow imbalance includes limit-order additions, cancellations and market-order effects. Its price relation is more robust than raw traded-volume relations, with impact depending on depth.

**Implication:** trade delta, queue imbalance and quote-event OFI are different quantities. OHLCV lacks the best-quote sizes and event sequence required to reconstruct their OFI. Largely contemporaneous impact is not proof of future after-cost profit. Stock evidence must be revalidated for ES/MES and NQ/MNQ and the proposed horizon.

### 4. Lee and Ready — Inferring Trade Direction from Intraday Data

[Journal of Finance, 1991](https://doi.org/10.1111/j.1540-6261.1991.tb02683.x).

The paper evaluates individual trade classification using trades and quotes. Quote/trade sequencing and transactions inside the spread create classification errors. Its historical five-second quote lag concerns old reporting technology and must not be copied mechanically into modern exchange-sequenced futures data. A tick test uses individual transactions, not the sign of a candle body; it remains an inference, not observed aggressor truth.

**Implication:** prefer documented exchange/provider aggressor flags. If inference is needed, validate against genuine labels on a separate sample and retain unknown classifications. Never label candle volume as actual signed trade flow.

### 5. Gould and Bonart — Queue Imbalance as a One-Tick-Ahead Price Predictor

[Author manuscript](https://arxiv.org/abs/1512.03492).

The authors fit logistic relationships between displayed bid/ask queue imbalance and the next mid-price move for ten liquid Nasdaq stocks. Predictive improvements are stronger for large-tick than small-tick stocks.

**Implication:** quote sizes may add information beyond candles, but a one-tick mid-price prediction is not the same as a fillable trade, a 30-minute reversal or a $100 daily profit. Spread, queue priority, latency and adverse selection can consume that information. This result cannot justify retail high-frequency or prohibited microscalping practices.

### 6. Biais, Hillion and Spatt — Preopening Price Discovery

[Original publisher](https://www.journals.uchicago.edu/doi/10.1086/250095); [author institution summary](https://www.insead.edu/faculty-research/publications/journal-articles/price-discovery-and-learning-during-pre-opening).

The Paris Bourse preopening study investigates whether revisable preopening orders and indicative prices convey learning rather than noise. Its setting motivates observing actual auction information. It does not prove a futures candle excursion/reentry identifies a failed auction; US cash auctions and continuously traded index futures have different mechanisms.

## Required distinctions

- **Inventory:** actual intermediary holdings require participant-level data. Overnight return or closing flow can be a proxy only; neither identifies who holds what.
- **Signed trade imbalance:** buyer-initiated executed quantity minus seller-initiated quantity, requiring genuine flags or validated transaction-level classification.
- **Queue imbalance:** displayed size difference or ratio at a quote snapshot; cancellations and hidden liquidity matter.
- **Order-flow imbalance:** signed best-quote changes across events; requires ordered quote/event records, not just executions.
- **Absorption:** aggressive trades accompanied by limited price movement and replenishing passive liquidity. This needs trades plus quote/depth updates. A long candle wick does not establish absorption.
- **Failed auction:** an economic interpretation. A precisely defined price excursion and return inside a prior range is merely an observable candidate event unless auction/flow information corroborates it.

## Falsifiable next experiment, subject to preregistration and data readiness

Hypothesis: after a predefined US-open excursion beyond the prior overnight range that returns inside it, opposing signed aggressive flow or adverse quote OFI adds incremental forecast information about the following 15–30-minute move, beyond the same price/volatility conditions alone.

1. Freeze overnight window, excursion/reentry deadlines, forecast horizon and event direction before results. One possible initial specification is 18:00–09:29 NY overnight range, excursion during 09:30–09:35 and reentry by 09:40. These are proposed definitions, not optimized or tested values.
2. First measure event coverage. If the event occurs on fewer than 70% of all eligible days, it cannot alone deliver a 70% daily-$100 hit rate, even under perfect conditional prediction. It may only be a fleet sleeve.
3. Compare a price/volatility-only model against nested additions of observed signed trade imbalance, quote OFI/depth and their preregistered interactions. Evaluate incremental chronological forecast accuracy/calibration as well as equal-risk net P&L. Do not compare a fully optimized flow model with an intentionally weak price baseline.
4. Use contract-identified trades and contemporaneous BBO/depth, source sequence/receive times, explicit aggressor semantics, corrections and gaps. Obtain correct roll mappings, exchange calendars and a causally available scheduled-news calendar. Reject timestamp/data defects before performance work.
5. Keep quote/trade classification calibration separate from economic-model validation. Unknown aggressor values remain unknown; do not silently fill missing sides.
6. Freeze model, costs, liquidity assumptions and risk limits before an independent period. Already examined 2026 observations remain consumed. The earlier 2024 check is backward robustness, not prospective confirmation.
7. Continue through complete Lucid evaluation/funded/payout paths and count every eligible day, including no-event days. Positive event returns or statistical classification gains alone do not meet the Sentra mission.

## Evidence status and next exact action

**NO VERIFIED IMPROVEMENT.** The compound mechanism is scientifically plausible but not established by the cited papers. The original overnight drift has documented decay, and its US-opening relationship contradicts a simplistic reversal story. Next: audit availability and semantics of lawful historical ES/MES or NQ/MNQ trade/BBO data. If unavailable, mark full signed-flow experiment blocked. A separately labeled price-only necessary-condition study may assess event prevalence and return structure, but cannot validate inventory, signed flow or absorption.
