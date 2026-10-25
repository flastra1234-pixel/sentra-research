"""Lucid-session layout: one row per Lucid trading day, 18:00 ET (previous evening) through
16:44 ET, 1,365 one-minute bars. Lucid allows trading Sunday-Friday 18:00-16:45 ET and no
position may be held through 16:45, so every strategy here is flat by the close of the 16:44
bar. Index 0 = 18:00, 540 = 03:00 (London), 870 = 08:30 (US data), 930 = 09:30 (cash open),
1320 = 16:00 (cash close), 1364 = 16:44.

Input: any 1-minute OHLCV DataFrame with a tz-aware index. A weekday session is kept when it
has >= ALL_MIN real bars and >= RTH_MIN real cash-session bars, so halt days (e.g. the 2020
limit-down sessions) and holiday half days stay in: dropping them on completeness would use
information from after every entry and remove exactly the tail days. Missing minutes are
filled flat from the last print (no trading during a halt or after an early close); minutes
before the session's first print take that print's OPEN (the first tradable price).
"""
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

NB = 1365
T = {"asia": 0, "tokyo": 120, "midnight": 360, "london": 540, "data": 870, "open": 930,
     "open30": 960, "noon": 1080, "fomc": 1200, "c60": 1260, "c30": 1290, "close": 1320,
     "last": NB - 1}
RTH = slice(930, 1320)
RTH_MIN = 60
ALL_MIN = 300


@dataclass
class LxSessions:
    dates: np.ndarray        # session date (the day it ends), datetime64[D]
    o: np.ndarray            # sessions x 1365
    h: np.ndarray
    l: np.ndarray
    c: np.ndarray
    v: np.ndarray
    present: np.ndarray      # bars with a real print, per session
    source: str

    def __len__(self):
        return len(self.dates)

    def slice(self, mask):
        return LxSessions(self.dates[mask], self.o[mask], self.h[mask], self.l[mask], self.c[mask],
                          self.v[mask], self.present[mask], self.source)


def build(df: pd.DataFrame, source: str, rth_min=RTH_MIN, all_min=ALL_MIN) -> LxSessions:
    if df.index.tz is None:
        raise ValueError("index must be tz-aware")
    et = df.index.tz_convert("America/New_York")
    shifted = et + pd.Timedelta(hours=6)            # 18:00 -> 00:00 of the session date
    minute = (shifted.hour * 60 + shifted.minute).to_numpy()
    keep = minute < NB                               # drops 16:45-17:59
    sday = shifted.normalize().tz_localize(None).to_numpy().astype("datetime64[D]")
    days, inv = np.unique(sday[keep], return_inverse=True)
    n = len(days)
    g = {k: np.full((n, NB), np.nan) for k in ("open", "high", "low", "close", "volume")}
    for k in g:
        g[k][inv, minute[keep]] = df[k].to_numpy(float)[keep]
    present = ~np.isnan(g["close"])
    weekday = (days.view("int64") - 4) % 7 < 5
    ok = weekday & (present[:, RTH].sum(axis=1) >= rth_min) & (present.sum(axis=1) >= all_min)
    o, h, l, c, v = (g[k][ok] for k in ("open", "high", "low", "close", "volume"))
    present = present[ok]
    days = days[ok]
    for i in range(len(days)):
        row = c[i]
        miss = np.isnan(row)
        if not miss.any():
            continue
        first = np.argmax(~miss)
        last = o[i, first]
        for t in range(NB):
            if np.isnan(c[i, t]):
                o[i, t] = h[i, t] = l[i, t] = c[i, t] = last
                v[i, t] = 0.0
            else:
                last = c[i, t]
    return LxSessions(days, o, h, l, c, np.nan_to_num(v), present, source)


def save(s: LxSessions, path: Path):
    np.savez_compressed(path, dates=s.dates.astype(str), o=s.o.astype(np.float32),
                        h=s.h.astype(np.float32), l=s.l.astype(np.float32), c=s.c.astype(np.float32),
                        v=s.v.astype(np.float32), present=s.present, source=np.array(s.source))


def load(path: Path) -> LxSessions:
    z = np.load(path, allow_pickle=False)
    f = lambda k: z[k].astype(np.float64)
    return LxSessions(z["dates"].astype("datetime64[D]"), f("o"), f("h"), f("l"), f("c"), f("v"),
                      z["present"], str(z["source"]))
