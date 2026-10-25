"""Market data for the strategy factory.

Two sources, both 1-minute OHLCV, both turned into the same per-session layout:

  nas100  Oanda NAS100_USD CFD, 2005-01 .. 2020-05, timestamps UTC
          (public: github.com/FutureSharks/financial-data). Tracks the Nasdaq-100 cash
          index, so percent moves match NQ/MNQ; absolute levels do not (no futures basis).
  nq2026  Yahoo NQ=F front-month futures, 2026-07-02 .. 2026-10-23, timestamps ET
          (public: github.com/Chief-rich/nasdaq100-data). Real futures, sealed holdout.

Layout: one row per regular session (09:30-15:59 ET, 390 one-minute bars, minute 0 is the
09:30 bar). Missing minutes are forward-filled flat from the prior close; sessions with
fewer than MIN_BARS real bars (half days, feed gaps) are dropped. Each session also carries
the overnight range (18:00 ET the evening before through 09:29) for decision-time features.
"""
import os
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

RTH_BARS = 390
MIN_BARS = 380
MIN_BARS_BY = {"wti": 350}       # crude CFD has more tick-less minutes in the cash session
WORKSPACE = Path(__file__).resolve().parents[3]          # folder that holds the sentra checkout
DATA_DIR = Path(os.environ.get("FACTORY_DATA_DIR", WORKSPACE / "sentra-data"))
OANDA_DIR = Path(os.environ.get(
    "OANDA_DIR", WORKSPACE / "futuresharks/financial-data/pyfinancialdata/data/currencies/oanda"))
NAS100_SRC = Path(os.environ.get("NAS100_SRC", OANDA_DIR / "NAS100_USD"))
OANDA_SETS = {"us2000": "US2000_USD", "xau": "XAU_USD", "wti": "WTICO_USD"}
# SPX500_USD is left out: 20-30% of its 2012-17 cash-session minutes have no bar.
NQ2026_SRC = Path(os.environ.get(
    "NQ2026_SRC", WORKSPACE / "chief-rich/nasdaq100-data/data/nq_1m/history.csv"))


@dataclass
class Sessions:
    dates: np.ndarray        # datetime64[D], ascending
    o: np.ndarray            # sessions x 390
    h: np.ndarray
    l: np.ndarray
    c: np.ndarray
    v: np.ndarray
    on_high: np.ndarray      # overnight high/low before the open (nan if none)
    on_low: np.ndarray
    source: str

    def __len__(self):
        return len(self.dates)

    def slice(self, mask):
        return Sessions(self.dates[mask], self.o[mask], self.h[mask], self.l[mask],
                        self.c[mask], self.v[mask], self.on_high[mask], self.on_low[mask],
                        self.source)


def _read_nas100(src: Path) -> pd.DataFrame:
    """Any Oanda instrument folder (year/month csv, UTC); named for the first one used."""
    files = sorted(src.glob("*/*.csv"))
    if not files:
        raise FileNotFoundError(f"no Oanda csv files under {src}")
    df = pd.concat(pd.read_csv(f, parse_dates=["time"]) for f in files)
    df = df.drop_duplicates("time").sort_values("time")
    idx = pd.DatetimeIndex(df["time"]).tz_localize("UTC").tz_convert("America/New_York")
    return pd.DataFrame({k: df[k].to_numpy(float) for k in ("open", "high", "low", "close", "volume")},
                        index=idx)


def _read_nq2026(src: Path) -> pd.DataFrame:
    df = pd.read_csv(src)
    idx = pd.DatetimeIndex(pd.to_datetime(df["Datetime"], utc=True)).tz_convert("America/New_York")
    out = pd.DataFrame({"open": df["Open"].to_numpy(float), "high": df["High"].to_numpy(float),
                        "low": df["Low"].to_numpy(float), "close": df["Close"].to_numpy(float),
                        "volume": df["Volume"].to_numpy(float)}, index=idx)
    out = out[~out.index.duplicated(keep="last")].sort_index()
    return out[(out[["open", "high", "low", "close"]] > 0).all(axis=1)]


def _to_sessions(df: pd.DataFrame, source: str, min_bars: int = MIN_BARS) -> Sessions:
    minute = df.index.hour * 60 + df.index.minute
    rth = (minute >= 570) & (minute < 960)
    day = df.index.normalize().tz_localize(None)
    r = df[rth]
    r_day = day[rth]
    r_min = (minute[rth] - 570).to_numpy()
    days, inv = np.unique(r_day.to_numpy().astype("datetime64[D]"), return_inverse=True)
    n = len(days)
    grid = {k: np.full((n, RTH_BARS), np.nan) for k in ("open", "high", "low", "close", "volume")}
    for k in grid:
        grid[k][inv, r_min] = r[k].to_numpy()
    present = ~np.isnan(grid["close"])
    keep = present.sum(axis=1) >= min_bars
    keep &= present[:, 0]                       # need the real 09:30 bar
    o, h, l, c, v = (grid[k][keep] for k in ("open", "high", "low", "close", "volume"))
    days = days[keep]
    # forward-fill flat bars for missing minutes
    for i in range(len(days)):
        miss = np.isnan(c[i])
        if miss.any():
            last = c[i, 0]
            for t in range(RTH_BARS):
                if np.isnan(c[i, t]):
                    o[i, t] = h[i, t] = l[i, t] = c[i, t] = last
                    v[i, t] = 0.0
                else:
                    last = c[i, t]
    # overnight: everything after the previous kept session's 16:00 close, up to 09:29
    on_hi = np.full(len(days), np.nan)
    on_lo = np.full(len(days), np.nan)
    ts = df.index.tz_localize(None).to_numpy()
    hi, lo = df["high"].to_numpy(), df["low"].to_numpy()
    day_ns = days.astype("datetime64[ns]")
    prev_close_ts = np.r_[day_ns[:1] - np.timedelta64(6, "h"), day_ns[:-1] + np.timedelta64(16, "h")]
    starts = np.searchsorted(ts, prev_close_ts)
    ends = np.searchsorted(ts, day_ns + np.timedelta64(570, "m"))
    for i in range(len(days)):
        a, b = starts[i], ends[i]
        if b > a:
            on_hi[i] = hi[a:b].max()
            on_lo[i] = lo[a:b].min()
    return Sessions(days, o, h, l, c, np.nan_to_num(v), on_hi, on_lo, source)


def load(name: str, rebuild: bool = False) -> Sessions:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    cache = DATA_DIR / f"sessions_{name}.npz"
    if cache.exists() and not rebuild:
        z = np.load(cache, allow_pickle=False)
        return Sessions(z["dates"].astype("datetime64[D]"), z["o"], z["h"], z["l"], z["c"],
                        z["v"], z["on_high"], z["on_low"], str(z["source"]))
    if name == "nas100":
        s = _to_sessions(_read_nas100(NAS100_SRC), "oanda NAS100_USD 1m (CFD)")
    elif name in OANDA_SETS:
        s = _to_sessions(_read_nas100(OANDA_DIR / OANDA_SETS[name]), f"oanda {OANDA_SETS[name]} 1m (CFD)",
                         MIN_BARS_BY.get(name, MIN_BARS))
    elif name == "nq2026":
        s = _to_sessions(_read_nq2026(NQ2026_SRC), "yahoo NQ=F 1m (futures)")
    else:
        raise ValueError(name)
    np.savez_compressed(cache, dates=s.dates.astype("datetime64[D]").astype(str), o=s.o, h=s.h,
                        l=s.l, c=s.c, v=s.v, on_high=s.on_high, on_low=s.on_low,
                        source=np.array(s.source))
    return s


if __name__ == "__main__":
    import sys
    for nm in (sys.argv[1:] or ["nas100", "nq2026"]):
        s = load(nm, rebuild=True)
        yrs = pd.Series(s.dates.astype("datetime64[Y]").astype(int) + 1970).value_counts().sort_index()
        print(nm, len(s), s.dates[0], s.dates[-1], dict(yrs))
