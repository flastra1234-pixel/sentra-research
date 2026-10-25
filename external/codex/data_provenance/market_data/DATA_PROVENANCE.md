# Data acquired for LucidFlex strategy research

Acquired 2026-10-25, before strategy-performance analysis. No synthetic data created.

## Primary study data

Repository: https://github.com/kfccolonel1/BARS
Observed HEAD: b8f2d8ab36e44c289036ce093bf7c9f04073a7d9

- NQ_1min_continuous.csv.gz: 814,993 1-minute bars, 2024-06-21 00:00 through 2026-10-08 23:58 America/New_York. SHA256 77641a522d8aed138505b947e9d7d1d5020bd99ee08688e963a0894812514e66.
- ES_1min_stitched.csv: 464,160 1-minute bars, 2025-06-20 00:00 through 2026-10-09 16:59 America/New_York. SHA256 36baf1581b5a7ea2533812c101b7057cc6166162e14e089cb699650fd5c7635d.
- Exact original download URLs are in download_urls.json. Original files preserved unchanged.
- Source README and catalog snapshots: BARS_README.md, BARS_catalog.json.

Schema: datetime,open,high,low,close,volume,source,trading_date,session. Timestamp carries UTC offset including DST. Session RTH is 09:30–15:59 ET. Trading date rolls at 18:00 ET; do not substitute trading_date blindly for intraday calendar date.

Repository describes data as unadjusted front-month CME futures with genuine bars and no gap filling. Most data is marked alfordlabs; 41,955 older NQ bars are TradingView and lack volume, 258 are Yahoo. Detailed mapping in source catalog. These are publicly contributed data, not a direct exchange delivery verified by us.

Bar-start labeling is inferred from 09:30–15:59 RTH convention and 16:59 premaintenance last bar; source does not explicitly define start vs end. Use completed bars and subsequent-bar fills. Source choice and roll dates can still affect signals and requires reproduction on broker data.

## Independent overlap audit

Repository: https://github.com/axb0306/cme-futures-ohlc
README identifies TopstepX/ProjectX Gateway as original data source. Code snapshot: topstep_update_data.py. Dates Jan20–Apr15 2026, UTC timestamps. Code reads API bar timestamp t; includePartialBar=false; current contract IDs use June2026 M26. Existing file history can contain earlier contract bars and no per-row contract IDs.

Files NQ_topstep_1min.csv, ES_topstep_1min.csv; separate micro files MNQ_topstep_1min.csv and MES_topstep_1min.csv also downloaded if available.

~83,918 NQ and83,924 ES overlapping minute bars. Exact OHLC match fractions 91.57% NQ/92.15% ES; close match92.27%/92.56%. Most mismatches occur March15–20 2026 roll week; main source was on expiring contract while comparison source had switched. Excluding those dates, closes match99.24% NQ (77,018 overlap bars),99.55% ES (77,024). This corroborates general market provenance but is not proof of every bar or executable fills.

## Quality findings

Audit script audit_data.py and full output quality_report.json. Main files have zero duplicate or non-increasing timestamps, OHLC inconsistencies, prices off0.25 tick grid, or negative volume. All timestamps precede current date. NQ593 RTH dates:571 with390 bars,22 holiday-short210/225 bars. ES338 RTH dates:326 full390,12 holiday-short. Do not forward-fill or trade incomplete sessions by accident.

## Material limitations

- Unadjusted quarterly rolls cause price discontinuities and different providers roll at different times. Intraday session-reset features avoid most jumps; cross-day indicators, previous-day levels and overnight holds need contract-aware handling or roll exclusions.
- NQ futures prices used to evaluate MNQ risk are a proxy; micro liquidity, spread and fills differ. Stress costs and verify on micro data before execution.
- Minute OHLC does not resolve event order within a minute or model bid/ask, queue priority, gap-through stops and latency. Favor conservative stop-first handling and market/next-bar fills; no executable edge can be certified from this data alone.
- About2.3 years NQ data is suitable for an exploratory split, not an assertion of all-regime robustness or7-year replication of creator claims.
