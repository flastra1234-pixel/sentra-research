# Signed-flow data access audit

Date: 2026-10-25 America/New_York. Research only; no credentials, paid endpoints, purchases, live feeds or orders used. No reserved price-performance dates inspected.

## Finding

**No sufficiently long, authorized, publicly accessible signed CME ES/NQ trade-and-quote history was established in this audit.** This is a current evidence/data constraint, not a claim that such data never exist or that the hypothesis is false. Existing data can support price/volume ablations, but not the signed-flow confirmation, absorption or actual inventory claims.

## Existing files: direct schema inspection

Both HFD MES and MNQ ten-second parquet schemas contain `ts` (UTC), open/high/low/close, volume, trade_count. MES has1,677,810rows; MNQ1,696,803. Neither has exchange aggressor side, bid/ask prices/sizes, depth events, per-trade identifiers, or contract IDs. Only schema and file metadata were inspected, not strategy outcomes. `trade_count` is a count, not signed volume. Candle color, close location and volume cannot restore missing exchange trade side or participant inventory.

Older contributed minute bars likewise do not supply those fields. Cross-contract continuous price series are not a substitute for contract-identified quote/trade records when studying overnight information and rollover.

Machine inventory: `data/signed_flow_data_inventory.json`.

## What a suitable schema actually supplies

Official Databento GLBX.MDP3 `TradeMsg` documents source aggressor side: B=buy aggressor, A=sell aggressor, N=not specified. Preserve N as unknown; do not default it to buy/sell. Records include instrument ID and nanosecond event/receive timestamps. Definitions/symbology are needed to map IDs to actual contracts.

**MBO side is event-dependent:** Add/Modify side denotes the passive order, whereas Trade side denotes aggressor. Summing every A/B event as signed traded volume is wrong. Order-flow imbalance from changes at bid/ask requires quote or book events; it is different from signed executed-volume imbalance. Absorption requires trades plus passive liquidity/price response and an explicit operational definition, not a candle label.

Sources: [official record schema](https://github.com/databento/dbn/blob/main/rust/dbn/src/record.rs), [official side/action enums](https://github.com/databento/dbn/blob/main/rust/dbn/src/enums.rs), [official CME dataset catalog](https://databento.com/catalog/cme/GLBX.MDP3/futures/ES).

## Public sources checked

1. **Official Databento SDK fixtures.** Public GLBX.MDP3 trades/TBBO files were downloaded from the provider repository (217/256compressed bytes). Hashes and exact URLs are saved. These tiny decoder-test fixtures are suitable only for pipeline/schema tests. They do not cover overnight plus cash-open sessions or independent inference periods. Do not treat fixtures as a representative market sample or synthetic test records as actual profits.
2. **Databento ES catalog preview.** Displays a few source-schema rows, including early overnight MBO snapshots/updates. It is not an adequately long downloadable historical experiment. The official historical API example requires an API key; no calls to paid or authenticated data endpoints were made. [Official example](https://github.com/databento/databento-python/blob/main/examples/historical_timeseries_to_file.py).
3. **CME DataMine.** Official documentation says file/list APIs require an entitled API ID and authentication for purchased/access-permitted historical data. We did not create credentials, request entitlements, or treat sample request URLs as authorization. [DataMine API](https://www.cmegroup.com/datamine/datamine-api.html), [list API](https://www.cmegroup.com/datamine/datamine-list-api.html).
4. **HFD.** Public free samples are ten-second bars. Tick-level archives are a separately offered commercial product. No private/paid paths were probed or purchases made. Even a tick label would require field-level confirmation of source trade side and contract mapping. [Provider browse](https://historicalfuturesdata.com/browse), [pricing](https://www.historicalfuturesdata.com/pricing).
5. **Other commercial providers' public pages.** TickData, PortaraCQG and Tickdatamarket advertise trade/quote or aggressor data and small samples, but this audit did not establish a permission-free multi-period ES/NQ signed-flow history. We do not assume generic time-and-sales or an unlabeled sample contains genuine exchange aggressor flags.

## Minimum research prerequisites

- Contract-identified ES/NQ trades with source trade side or explicitly measured classification error, event timestamps, sizes, correction/bust and sequence handling; no OHLC trade-sign manufacture.
- Synchronized bid/ask prices and sizes for spread/cost controls and quote OFI; MBO or depth updates if absorption/replenishment is central.
- Overnight through cash-open coverage, explicit timezone/DST, holiday and rollover mapping, and enough distinct sessions/events across multiple volatility/news regimes.
- Definitions/symbology files and exchange status/session messages to distinguish resets, snapshots, halts, spreads and outright contracts.
- Point-in-time licensed macro release schedule if conditioning on announcements.
- Predetermined train/walk-forward/untouched periods and retention rules before outcomes. A few fixture rows or one free sample day can test parsing but not establish a repeatable edge or70%daily target.
- Realistic executable spread/market/stop costs, contract multiplier validation and exact account lifecycles. Signed flow predicts price only conditionally; incremental predictive information does not establish net profitability.

## Concrete next action within current authorization

Build and test the ingestion/validation contract offline using clearly labeled fixtures and synthetic unit tests, then run only a preregistered **price-only necessary-condition ablation** on already-consumed permissible bars if scientifically useful. Explicitly label overnight returns as a positioning proxy rather than measured inventory, and never claim that ablation tested signed-flow confirmation.

The full hypothesis remains DATA-BLOCKED until a sufficiently long authorized trade/quote dataset is located or the owner supplies an already-entitled export. Do not purchase data or ask for payment as an implied next step. Continue the authorized queue with an independently justified mechanism that uses information actually observed.

## Verified fixture decoding

Decoded both provider fixtures offline with the official Databento Python SDK, without instantiating an API client. Each contains exactly **four ESH1 trades** for instrument5482 on December28,2020, from00:00:00.2468 to00:00:00.7216UTC by receive time (less than half a second). Three records have B aggressor side and one A. TBBO includes bid/ask prices and sizes. The samples are therefore useful for checking A/B mappings and native timestamps, but emphatically do not contain a full overnight or cash-open observation. Decode results are saved in `data/fixture_decode_audit.json` and the `.decoded.csv` files.
