"""Decision-time features for Lucid sessions. Each column has an availability index (the bar
from which a strategy may use it): prior-session values are known at 18:00 (index 0); the
overnight range and the 09:30 gap only from the 09:30 bar (index 930). Filters inherit the
availability of the features they read, so a 03:00 strategy can never filter on the gap."""
import numpy as np

from .lx_data import LxSessions, NB

(OPEN, RTH_PREV_CLOSE, SESS_PREV_CLOSE, PREV_HIGH, PREV_LOW, ON_HIGH, ON_LOW, ATR14, ATR5,
 ATR50, VOLR, SMA20, TREND, DOW, GAP, GAP_ATR, ON_RANGE_ATR, NR7, INSIDE, VALID,
 PREV_SHIGH, PREV_SLOW) = range(22)
N_FEAT = 22
AVAILABLE_AT = {OPEN: 930, GAP: 930, GAP_ATR: 930, ON_HIGH: 930, ON_LOW: 930, ON_RANGE_ATR: 930}
NOISE_LOOKBACKS = (10, 14, 20)


def _trailing_mean(x, n):
    out = np.full(len(x), np.nan)
    cs = np.r_[0.0, np.cumsum(x)]
    for i in range(n, len(x)):
        out[i] = (cs[i] - cs[i - n]) / n
    return out


def daily(s: LxSessions) -> np.ndarray:
    n = len(s)
    F = np.full((n, N_FEAT), np.nan)
    rth_close = s.c[:, 1319]
    sess_close = s.c[:, NB - 1]
    shi, slo = s.h.max(axis=1), s.l.min(axis=1)
    rhi, rlo = s.h[:, 930:1320].max(axis=1), s.l[:, 930:1320].min(axis=1)
    prev_sc = np.r_[np.nan, sess_close[:-1]]
    first = s.o[:, 0]
    pc = np.where(np.isnan(prev_sc), first, prev_sc)
    tr = (np.maximum(shi, pc) - np.minimum(slo, pc)) / pc
    F[:, OPEN] = s.o[:, 930]
    F[:, RTH_PREV_CLOSE] = np.r_[np.nan, rth_close[:-1]]
    F[:, SESS_PREV_CLOSE] = prev_sc
    F[:, PREV_HIGH] = np.r_[np.nan, rhi[:-1]]
    F[:, PREV_LOW] = np.r_[np.nan, rlo[:-1]]
    F[:, PREV_SHIGH] = np.r_[np.nan, shi[:-1]]
    F[:, PREV_SLOW] = np.r_[np.nan, slo[:-1]]
    F[:, ON_HIGH] = s.h[:, :930].max(axis=1)
    F[:, ON_LOW] = s.l[:, :930].min(axis=1)
    F[:, ATR14] = _trailing_mean(tr, 14)
    F[:, ATR5] = _trailing_mean(tr, 5)
    F[:, ATR50] = _trailing_mean(tr, 50)
    F[:, VOLR] = F[:, ATR5] / F[:, ATR50]
    F[:, SMA20] = _trailing_mean(sess_close, 20)
    F[:, TREND] = np.sign(prev_sc - F[:, SMA20])
    F[:, DOW] = (s.dates.astype("datetime64[D]").view("int64") - 4) % 7
    F[:, GAP] = s.o[:, 930] / F[:, RTH_PREV_CLOSE] - 1.0
    F[:, GAP_ATR] = F[:, GAP] / F[:, ATR14]
    F[:, ON_RANGE_ATR] = (F[:, ON_HIGH] - F[:, ON_LOW]) / s.o[:, 930] / F[:, ATR14]
    rng = (shi - slo) / sess_close
    for i in range(8, n):
        F[i, NR7] = float(rng[i - 1] <= rng[i - 7:i].min())
        F[i, INSIDE] = float(shi[i - 1] <= shi[i - 2] and slo[i - 1] >= slo[i - 2])
    F[:, VALID] = (~np.isnan(F[:, ATR14]) & ~np.isnan(F[:, SMA20]) & ~np.isnan(prev_sc)).astype(float)
    return F


def rth_vwap(s: LxSessions) -> np.ndarray:
    """VWAP from 09:30, sessions x 390 (column 0 = the 09:30 bar)."""
    h, l, c, v = (a[:, 930:1320] for a in (s.h, s.l, s.c, s.v))
    w = v.copy()
    w[w.sum(axis=1) <= 0] = 1.0
    w = np.maximum(w, 1e-9)
    return np.cumsum((h + l + c) / 3 * w, axis=1) / np.cumsum(w, axis=1)


def noise_sigma(s: LxSessions, lookback: int) -> np.ndarray:
    """sessions x 390: mean over the previous sessions of |close_t / open_0930 - 1|."""
    a = np.abs(s.c[:, 930:1320] / s.o[:, 930:931] - 1.0)
    cs = np.vstack([np.zeros((1, a.shape[1])), np.cumsum(a, axis=0)])
    out = np.full(a.shape, np.nan)
    out[lookback:] = (cs[lookback:-1] - cs[:-lookback - 1]) / lookback
    return out


def build(s: LxSessions):
    F = daily(s)
    return F, rth_vwap(s), np.stack([noise_sigma(s, L) for L in NOISE_LOOKBACKS])
