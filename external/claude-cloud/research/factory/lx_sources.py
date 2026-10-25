"""2020+ NQ 1-minute sources (public GitHub copies; see RESULTS for provenance) spliced into one
back-adjusted continuous series, UTC, bars stamped at the minute start:

  NQ.F continuous futures   2020-01-01 .. 2026-03-01   futures_NQ.F_1m.parquet
                            (okmantz/T58-QUANT-ALGO-BACKTESTER; cross-checked against
                            hindsight-finance/Silver-Bullet-AM-Session: 1m return corr 0.993)
  NQ continuous futures     2026-03-02 .. 2026-09-11   NQ_db_1m.json (chi2tseng/nq-replay-trainer)
  NQ=F front month          2026-09-12 .. 2026-10-23   chief-rich nq_1m/history.csv (ET offsets)
Sources overlap on the same contract at each splice (price ratio 1.0000), so no scaling is
needed there; MNQ / CFD loaders remain for cross-checks.

Front-month series jump at each quarterly roll. The NQ.F vendor switches at 00:00 UTC on the
Monday (sometimes Tuesday) of expiry week, i.e. inside a Lucid session; Yahoo switches intraday.
The switch shows up as an open-vs-previous-close gap between consecutive minutes (normally a
few hundredths of a percent; at a roll ~1%), so it is detected in the expiry-week window and
earlier bars are ratio-scaled by the measured gap. Low-rate rolls (2020-21, basis ~0.1%) leave
no detectable gap and are left alone. Splices are joined by price continuity. Percent moves
within a contract are untouched.
"""
import os
from pathlib import Path

import numpy as np
import pandas as pd

from . import data as D

RAW = Path(os.environ.get("FACTORY_RAW_DIR", D.DATA_DIR / "raw"))
COLS = ["open", "high", "low", "close", "volume"]
CLEANED = {}                      # source -> bars changed by clean_spikes in the last build()


def _third_friday(y, m):
    d = pd.Timestamp(y, m, 15)
    return d + pd.Timedelta(days=(4 - d.dayofweek) % 7)


def detect_rolls(df, min_gap=0.0015, ratio_to_p99=3.0):
    """[(utc time of the first new-contract bar, gap)] for each Mar/Jun/Sep/Dec expiry week: the
    largest open-vs-previous-close gap between contiguous minutes, if it is big, far above the
    window's normal gaps, and the bar itself is calm (a level shift, not a news print)."""
    o, h, l, c = (df[k].to_numpy() for k in ("open", "high", "low", "close"))
    gap = np.r_[0.0, o[1:] / c[:-1] - 1.0]
    step = np.diff(df.index.values).astype("timedelta64[s]").astype(np.int64)
    contiguous = np.r_[False, step <= 120]
    out = []
    years = range(df.index[0].year, df.index[-1].year + 1)
    for y in years:
        for m in (3, 6, 9, 12):
            f3 = _third_friday(y, m)
            a = pd.Timestamp(f3.year, f3.month, f3.day, tz="UTC") - pd.Timedelta(days=6)
            b = pd.Timestamp(f3.year, f3.month, f3.day, tz="UTC") - pd.Timedelta(days=1)
            w = np.where((df.index >= a) & (df.index < b) & contiguous)[0]
            if len(w) < 100:
                continue
            j = w[np.argmax(gap[w])]
            p99 = np.percentile(np.abs(gap[w]), 99)
            calm = (h[j] - l[j]) / c[j] < 0.5 * gap[j]       # a level shift, not a volatile print
            if gap[j] >= min_gap and gap[j] >= ratio_to_p99 * p99 and calm:
                out.append((df.index[j], float(gap[j])))
    return out


def _nqf():
    d = pd.read_parquet(RAW / "futures_NQ.F_1m.parquet")
    return d.set_index("ts")[COLS].sort_index()


def _mnq():
    d = pd.read_csv(RAW / "MNQ_1min_20260120_20260415.csv", parse_dates=["datetime"])
    d = d.set_index("datetime").sort_index()
    d.index = d.index.tz_localize("UTC")
    return d[COLS]


def _cfd():
    d = pd.read_parquet(RAW / "NAS100_USD_1m.parquet")
    return d.set_index("ts")[COLS].sort_index()


def _chi():
    import json
    d = pd.DataFrame(json.loads((RAW / "NQ_db_1m.json").read_text()))
    d.index = pd.to_datetime(d["time"], unit="s", utc=True)
    d = d[d.index.second == 0]                   # drop zero-volume sub-minute tick rows
    return d.sort_index()[COLS]


def clean_spikes(df, wick=0.005, calm=0.002):
    """Clamp isolated overnight bad prints (18:00-08:25 ET only, so news bars at 08:30,
    10:00 and 14:00 are never touched): a high/low more than `wick` beyond the 5-bar
    median close while the bar's body stays within `calm` of it, or an open that jumps
    away from both the previous close and its own close. Returns (df, bars changed)."""
    df = df.copy()
    et = df.index.tz_convert("America/New_York")
    mins = et.hour * 60 + et.minute
    night = (mins >= 18 * 60) | (mins < 8 * 60 + 25)
    o, h, l, c = (df[k].to_numpy().copy() for k in ("open", "high", "low", "close"))
    med = pd.Series(c, index=df.index).rolling(5, center=True, min_periods=3).median().to_numpy()
    body_hi, body_lo = np.maximum(o, c), np.minimum(o, c)
    prev_c = np.r_[c[0], c[:-1]]
    bad_open = night & (np.abs(o / prev_c - 1) > wick) & (np.abs(o / c - 1) > wick) & (np.abs(c / prev_c - 1) < calm)
    o = np.where(bad_open, prev_c, o)
    body_hi, body_lo = np.maximum(o, c), np.minimum(o, c)
    bad_hi = night & (h / med - 1 > wick) & (body_hi / med - 1 < calm)
    bad_lo = night & (1 - l / med > wick) & (1 - body_lo / med < calm)
    h = np.where(bad_hi | bad_open, np.maximum(body_hi, np.minimum(h, body_hi * (1 + calm))), h)
    l = np.where(bad_lo | bad_open, np.minimum(body_lo, np.maximum(l, body_lo * (1 - calm))), l)
    df["open"], df["high"], df["low"] = o, h, l
    return df, int((bad_open | bad_hi | bad_lo).sum())


def _nq26():
    d = D._read_nq2026(D.NQ2026_SRC)
    d.index = d.index.tz_convert("UTC")
    return d[COLS]


def _scale(df, k):
    df = df.copy()
    df[["open", "high", "low", "close"]] *= k
    return df


def _splice_scale(cur, nxt):
    """Price ratio at the join: from overlapping bars when the sources overlap (same
    contract, ~1.0), otherwise first next open / last current close."""
    ov = cur.index.intersection(nxt.index)
    if len(ov) >= 100:
        ov = ov[-1440:]
        return float(np.median(nxt.loc[ov, "close"].to_numpy() / cur.loc[ov, "close"].to_numpy()))
    return float(nxt["open"].iloc[0] / cur["close"].iloc[-1])


def build():
    """Returns (df, None, rolls): back-adjusted continuous NQ series (UTC) and detected rolls."""
    raw = []
    for loader in (_nqf, _chi, _nq26):
        seg, nbad = clean_spikes(loader())
        CLEANED[loader.__name__] = nbad
        raw.append(seg)
    segs = []
    for j, seg in enumerate(raw):
        start = segs[-1][1].index[-1] if segs else None
        scale_ref = raw[j - 1] if j else None
        part = seg if start is None else seg[seg.index > start]
        segs.append((scale_ref, part, seg))
    frames = [p for _, p, _ in segs]
    # scale earlier parts so each join is continuous (overlap ratio ~1.0 on the same contract)
    for j in range(len(frames) - 1, 0, -1):
        k = _splice_scale(raw[j - 1], raw[j])
        for q in range(j):
            frames[q] = _scale(frames[q], k)
    df = pd.concat(frames)
    df = df[~df.index.duplicated(keep="last")].sort_index()
    rolls = [r for fr in frames for r in detect_rolls(fr)]
    px = df[["open", "high", "low", "close"]].to_numpy()
    ts = df.index
    for t, g in rolls:
        px[ts < t] *= 1.0 + g
    df[["open", "high", "low", "close"]] = px
    return df, None, rolls
