# Additional futures data for continued Lucid research

Acquired 2026-10-25 UTC. No strategy signals, trades or P&L were evaluated by this acquisition task. Existing `/workspace/market_data` files were preserved.

## Main new source: public latest-year ten-second samples

Provider: [Historical Futures Data](https://historicalfuturesdata.com/). Its [documentation](https://historicalfuturesdata.com/docs) explicitly permits latest-year ten-second sample downloads without an account. No registration, payment, credentials or access-control bypass was used.

Primary files:

| File | Rows | First UTC | Last UTC | SHA256 |
|---|---:|---|---|---|
| `MES_10sec_2026_hfd.parquet` | 1,677,810 | 2026-01-01 23:00 | 2026-10-18 23:41:40 | `19e9e0f9acaf0b35999c60cc60ce29e086aa129092cfb41d9de2c53cf4ece9fd` |
| `MNQ_10sec_2026_hfd.parquet` | 1,696,803 | 2026-01-01 23:00 | 2026-10-19 06:29:30 | `b7978677822c1c1cd302236a133153ede9753e27f822120c614bb4f19e65c497` |

Direct URL pattern: `https://historicalfuturesdata.com/MES/bars/10s/cme.mes.bars.10s.2026.parquet` (substitute asset and lowercase root for MNQ). Download URLs, byte counts and hashes are recorded in `hfd_download_manifest.json`. A saved provider inventory and HTML documentation snapshot are included. The catalog advertises coverage through October23, but the actual downloaded MES/MNQ samples stop earlier: trust the observed file timestamps.

Schema: `ts` is `timestamp[ns, UTC]`, documented as **bar open time**. OHLC are float64, `volume` and `trade_count` uint32. Buckets are epoch-aligned; empty buckets are omitted. Both inspected samples contain zero duplicate timestamps and zero OHLC inconsistencies.

The price series is **back-adjusted continuous futures**, rather than a single unadjusted traded contract. Intraday price differences are corroborated below, but absolute levels and cross-day features require roll-aware handling. Treat it as contributed vendor data, not an exchange-certified feed.

### Guarded access and fresh dates

`load_micro.py` exposes:

```python
from load_micro import load_micro_10sec, load_micro_1min

# Default: excludes all New York dates on/after2026-10-10.
d = load_micro_10sec('MES')
a = load_micro_1min('MES', before='2026-10-10')

# Only AFTER candidate selection is frozen:
fresh_allowed = load_micro_10sec('MES', allow_fresh=True)
```

Explicit later `before` dates are rejected unless `allow_fresh=True`. MES and MNQ alone are supported by this loader, because their units have been checked. Both have **five new complete RTH sessions: October12–16,2026**. These dates are sequestered from search/diagnosis. Acquisition inspected only file/schema/coverage and cross-provider price quality, not strategy performance.

One-minute derivatives `MES_1min_2026_hfd.parquet` and `MNQ_1min_2026_hfd.parquet` were produced by first/max/min/last OHLC and summed volume/trades from observed ten-second buckets. No missing prices were filled. Loader output also includes `source_bars`, the observed constituent count1–6. The saved derivatives omit that auxiliary count; raw files remain authoritative.

### Completion and non-RTH coverage

For each asset, 199 sessions have all390 RTH minutes; 198 have all2,340 ten-second RTH buckets. Both also have199 CME session dates with all990 non-RTH minutes, and199 with the entire1,380-minute23-hour CME day. This is useful for overnight studies, though missing ten-second buckets often reflect no trade and cannot be equated automatically to a feed outage.

MES has473,192 RTH and1,204,618 non-RTH ten-second bars; MNQ473,219 and1,223,584. Only6 MES and123 MNQ sessions contain every possible non-RTH ten-second bucket. Detailed counts are in `samples_schema_completeness.json` and per-session CSVs.

### Independent price overlap

Compared one-minute aggregates with the actual-micro TopstepX-contributed files already acquired. Each comparison has84,075 overlapping minutes. HFD differs by additive continuous-contract adjustments:

- MES: January daily median offset +184.25points. After subtracting each day's median offset, median absolute close difference0 and99th percentile0.5points.
- MNQ: January daily median offset +812.75points. Offset-adjusted median absolute close difference0 and99th percentile3.25points.

This independently corroborates general intraday price moves and timestamp alignment. It does not prove every OHLC extremum, volume or executable fill. Do not subtract an estimated daily offset using future data in a live strategy; it was only a data-audit diagnostic. Session-reset strategies can operate directly in adjusted price coordinates.

## Substantial earlier S&P history

`ES_3min_2024_2025.csv` was downloaded from the original BARS source at immutable revision `b8f2d8ab36e44c289036ce093bf7c9f04073a7d9`:

`https://raw.githubusercontent.com/kfccolonel1/BARS/b8f2d8ab36e44c289036ce093bf7c9f04073a7d9/ES/3min/ES_3min_2024-01-01_2025-12-19_tradingview.csv`

-232,740 three-minute bars, January2,2024 through December19,2025 (trading dates).
-490 full130-bar RTH sessions, including249 in2024 and **364 before the previous ES history began on June20,2025**.
-Columns datetime/OHLC/trading_date/session/source; **no volume**. Original ISO timestamps have explicit New York offsets. Bar-start convention is inferred from source convention.
-No duplicate timestamps. Close match94.85% across59,535 overlapping three-minute buckets against the previous ES minute source; median price difference0. Contract-roll differences remain.
-SHA256 `4f1ebcb0c7e6e2cf9eb89e13b6ab2ea81994d5465cffbbc126c257c23a3c8418`.

This previously unused earlier history can provide a backward-time challenge, clearly labeled as such. Use native three-minute fills or exact15-minute aggregation. **Never invent one-minute OHLC by upsampling it.** VWAP/volume filters cannot be evaluated on this file. The data have not been subjected to strategy-performance analysis by this task.

## Additional files acquired but not approved for primary research

Eight TopstepX-contributed GC/MGC,CL/MCL,RTY/M2K,YM/MYM minute files cover roughly January–April2026; hashes/URLs in `download_manifest.json`. They add instruments, not long histories.

Additional HFD sample downloads completed before the scope was narrowed to MES/MNQ: MGC,MCL,M2K,RTY,YM,GC. They are retained but not used in the recommended loader or primary study.

**Quarantine notes:** HFD MGC prices use an undocumented scale approximately1/10of standard gold quotation. Multiplying by10 and removing daily additive roll offsets reproduces Topstep changes closely (median absolute difference~0.0001point,99th percentile1.3points), but no normalization has been silently applied. HFD MCL has large missing months and only41full RTH sessions; it is unsuitable for broad backtesting without a separate audit. Extra M2K/RTY/YM/GC samples have not been quality-audited and should not be used merely because they downloaded successfully.

## Limits and reproducibility

All files are fact data from public third-party sources, not proof of a tradable edge. Ten-second OHLC improves order sequencing versus minute bars but still lacks bid/ask, queues, event order within each ten-second bucket and actual latency. Costs and stop-gap assumptions remain essential. Five fresh days are a sanity check, not a statistically persuasive holdout.

`samples_hashes.json` pins downloaded and derived files. `hfd_quality_report.json`, `es3min_quality.json` and the schema/completeness reports retain numeric audit results. No existing study output or strategy configuration was modified.
