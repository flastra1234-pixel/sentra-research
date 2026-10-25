"""Decision-time features. Every daily value is known at the 09:30 open of the session it
belongs to (it uses only prior sessions plus the overnight range and the opening print).
Intraday arrays (VWAP, noise-area sigma) use only bars up to the minute they describe,
or prior sessions."""
import numpy as np

from .data import Sessions

# column order of the daily feature matrix F
OPEN, PREV_CLOSE, PREV_HIGH, PREV_LOW, ON_HIGH, ON_LOW, ATR14, ATR5, ATR50, VOLR, SMA20, \
    TREND, DOW, GAP, GAP_ATR, NR7, INSIDE, PREV_RET, VALID = range(19)
N_FEAT = 19
NOISE_LOOKBACKS = (10, 14, 20)


def _trailing_mean(x, n):
    """mean of x[i-n .. i-1] (excludes i). nan for the first n."""
    out = np.full(len(x), np.nan)
    cs = np.r_[0.0, np.cumsum(x)]
    for i in range(n, len(x)):
        out[i] = (cs[i] - cs[i - n]) / n
    return out


def daily_features(s: Sessions) -> np.ndarray:
    n = len(s)
    F = np.full((n, N_FEAT), np.nan)
    o0 = s.o[:, 0]
    close = s.c[:, -1]
    hi = s.h.max(axis=1)
    lo = s.l.min(axis=1)
    prev_close = np.r_[np.nan, close[:-1]]
    tr = (np.maximum(hi, np.nan_to_num(prev_close, nan=hi[0])) -
          np.minimum(lo, np.nan_to_num(prev_close, nan=lo[0])))
    tr_pct = tr / np.where(np.isnan(prev_close), close, prev_close)
    rng = (hi - lo) / close
    F[:, OPEN] = o0
    F[:, PREV_CLOSE] = prev_close
    F[:, PREV_HIGH] = np.r_[np.nan, hi[:-1]]
    F[:, PREV_LOW] = np.r_[np.nan, lo[:-1]]
    F[:, ON_HIGH] = s.on_high
    F[:, ON_LOW] = s.on_low
    F[:, ATR14] = _trailing_mean(tr_pct, 14)
    F[:, ATR5] = _trailing_mean(tr_pct, 5)
    F[:, ATR50] = _trailing_mean(tr_pct, 50)
    F[:, VOLR] = F[:, ATR5] / F[:, ATR50]
    F[:, SMA20] = _trailing_mean(close, 20)
    F[:, TREND] = np.sign(prev_close - F[:, SMA20])
    F[:, DOW] = (s.dates.astype("datetime64[D]").view("int64") - 4) % 7   # 0 = Monday
    F[:, GAP] = o0 / prev_close - 1.0
    F[:, GAP_ATR] = F[:, GAP] / F[:, ATR14]
    nr7 = np.zeros(n)
    inside = np.zeros(n)
    for i in range(8, n):
        nr7[i] = float(rng[i - 1] <= rng[i - 7:i].min())
        inside[i] = float(hi[i - 1] <= hi[i - 2] and lo[i - 1] >= lo[i - 2])
    F[:, NR7] = nr7
    F[:, INSIDE] = inside
    F[:, PREV_RET] = np.r_[np.nan, close[:-1]] / np.r_[np.nan, np.nan, close[:-2]] - 1.0
    F[:, VALID] = (~np.isnan(F[:, ATR14]) & ~np.isnan(F[:, SMA20]) & ~np.isnan(prev_close)).astype(float)
    return F


def vwap(s: Sessions) -> np.ndarray:
    tp = (s.h + s.l + s.c) / 3.0
    w = s.v.copy()
    no_vol = w.sum(axis=1) <= 0
    w[no_vol] = 1.0
    w = np.maximum(w, 1e-9)
    return np.cumsum(tp * w, axis=1) / np.cumsum(w, axis=1)


def noise_sigma(s: Sessions, lookback: int) -> np.ndarray:
    """sigma[i, t] = mean over the previous `lookback` sessions of |close_t / open - 1|."""
    a = np.abs(s.c / s.o[:, :1] - 1.0)
    cs = np.vstack([np.zeros((1, a.shape[1])), np.cumsum(a, axis=0)])
    out = np.full(a.shape, np.nan)
    out[lookback:] = (cs[lookback:-1] - cs[:-lookback - 1]) / lookback
    return out


def build(s: Sessions):
    F = daily_features(s)
    sig = np.stack([noise_sigma(s, L) for L in NOISE_LOOKBACKS])
    return F, vwap(s), sig
