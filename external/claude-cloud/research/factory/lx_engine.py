"""Numba families on the Lucid session (18:00-16:44 ET, 1,365 bars; see lx_data.T for key
indices). Same fill and cost conventions as engine.py; every position is closed by the
16:44 bar at the latest. Times in parameters are absolute session indices.

Contract: fam(o, h, l, c, F, vw, sig, pr, mask, P, pnl, low, ntr, nwin, gw, gl, path, K)
  vw, sig: cash-session arrays (390 columns, column 0 = 09:30), see lx_features.
  pr: True where the bar is a real print; orders only fill on real prints (no fills during
      halts, after an early close or before the session's first print).
  pnl/low/ntr as in engine.py; nwin = winning trades, gw / gl = gross $ won / lost.
  path: per-minute mark of the sleeve (realised + open P&L at the bar's adverse extreme).
"""
import numpy as np
from numba import njit

from . import lx_features as X
from .engine import EXIT_SIGNAL, EXIT_STOP, EXIT_TARGET, EXIT_TIME, INSTRUMENTS

OPEN_T = 930


@njit(cache=True)
def _manage(o, h, l, c, i, t0, d, pe, stop, target, tx, be_r, scale, real, path, worst, K):
    risk = abs(pe - stop) if stop == stop else 0.0
    moved = False
    best = K.shape[0] > 4 and K[4] > 0
    for t in range(t0, tx + 1):
        adverse = ((l[i, t] - pe) if d > 0 else (pe - h[i, t])) * scale
        m = real + adverse - K[1]
        if m < worst:
            worst = m
        if path.shape[0] > 0:
            path[i, t] = (real + ((h[i, t] - pe) if d > 0 else (pe - l[i, t])) * scale - K[1]) if best else m
        if stop == stop:
            if (l[i, t] <= stop) if d > 0 else (h[i, t] >= stop):
                if t == t0:
                    px = stop
                else:
                    px = min(o[i, t], stop) if d > 0 else max(o[i, t], stop)
                return px, t, EXIT_STOP, worst
        if t > t0 and target == target:
            if (h[i, t] >= target) if d > 0 else (l[i, t] <= target):
                px = max(o[i, t], target) if d > 0 else min(o[i, t], target)
                return px, t, EXIT_TARGET, worst
        if be_r > 0 and not moved and risk > 0 and (c[i, t] - pe) * d >= be_r * risk:
            stop = pe
            moved = True
    return c[i, tx], tx, EXIT_TIME, worst


@njit(cache=True)
def _book(pe, px, d, kind, scale, K):
    return (px - pe) * d * scale - K[1] - K[2] - (K[3] if kind == EXIT_STOP else 0.0)


@njit(cache=True)
def _after(path, i, t_from, real, v, nwin, gw, gl, best=False):
    if v > 0:
        nwin[i] += 1
        gw[i] += v
    else:
        gl[i] -= v
    if path.shape[0] > 0:
        if (real > path[i, t_from]) if best else (real < path[i, t_from]):
            path[i, t_from] = real
        for t in range(t_from + 1, path.shape[1]):
            path[i, t] = real


@njit(cache=True)
def _first_real(pr, i, t, tmax):
    for u in range(t, tmax + 1):
        if pr[i, u]:
            return u
    return -1


@njit(cache=True)
def _trend_ok(d, trend, tf):
    if tf == 1:
        return d * trend > 0
    if tf == 2:
        return d * trend < 0
    return True


@njit(cache=True)
def _dir_ok(d, dm):
    return dm == 0 or (dm == 1 and d > 0) or (dm == 2 and d < 0)


# ---------------------------------------------------------------- window breakout
# P: ra, rb, cut, dir_mode, stop_mode(0 opposite side, 1 range frac, 2 ATR), stop_val,
#    target_r(0 none), tx, be_r, tf, max_trades
@njit(cache=True)
def fam_brk(o, h, l, c, F, vw, sig, pr, mask, P, pnl, low, ntr, nwin, gw, gl, path, K):
    ra = int(P[0]); rb = int(P[1]); cut = int(P[2]); dm = int(P[3]); sm = int(P[4]); sv = P[5]
    tr_ = P[6]; tx = int(P[7]); be = P[8]; tf = int(P[9]); mt = int(P[10])
    for i in range(o.shape[0]):
        if not mask[i]:
            continue
        atr = F[i, X.ATR14]
        hi = h[i, ra:rb].max()
        lo = l[i, ra:rb].min()
        w = hi - lo
        if w <= 0:
            continue
        real = 0.0
        worst = 0.0
        n = 0
        t = rb
        while t <= min(cut, tx - 1) and n < mt:
            d = 1 if h[i, t] > hi else (-1 if l[i, t] < lo else 0)
            if d == 0 or not pr[i, t] or not _dir_ok(d, dm) or not _trend_ok(d, F[i, X.TREND], tf):
                t += 1
                continue
            pe = max(o[i, t], hi) if d > 0 else min(o[i, t], lo)
            if sm == 0:
                stop = lo if d > 0 else hi
            elif sm == 1:
                stop = pe - d * sv * w
            else:
                stop = pe - d * sv * atr * pe
            if (stop - pe) * d >= 0:
                t += 1
                continue
            target = pe + d * tr_ * abs(pe - stop) if tr_ > 0 else np.nan
            scale = K[0] / pe
            px, te, kind, worst = _manage(o, h, l, c, i, t, d, pe, stop, target, tx, be, scale,
                                          real, path, worst, K)
            # a stop ENTRY triggers on a print beyond the level: charge the stop-order slip too
            v = _book(pe, px, d, kind, scale, K) - K[3]
            real += v
            n += 1
            worst = min(worst, real)
            _after(path, i, te, real, v, nwin, gw, gl, K.shape[0] > 4 and K[4] > 0)
            t = te + 1
            if d > 0:
                hi = 1e18
            else:
                lo = -1e18
        pnl[i] = real
        low[i] = min(worst, 0.0)
        ntr[i] = n


# ---------------------------------------------------------------- window fade (first touch)
# P: ra, rb, cut, dir_mode, stop_atr, target(0 = range mid, >0 = R), tx, tf
@njit(cache=True)
def fam_fade(o, h, l, c, F, vw, sig, pr, mask, P, pnl, low, ntr, nwin, gw, gl, path, K):
    ra = int(P[0]); rb = int(P[1]); cut = int(P[2]); dm = int(P[3]); sa = P[4]; tg = P[5]
    tx = int(P[6]); tf = int(P[7])
    for i in range(o.shape[0]):
        if not mask[i]:
            continue
        hi = h[i, ra:rb].max()
        lo = l[i, ra:rb].min()
        if not (o[i, rb] < hi and o[i, rb] > lo):
            continue
        atr = F[i, X.ATR14]
        for t in range(rb, min(cut, tx - 1) + 1):
            up = h[i, t] > hi          # a resting limit fills only when price trades through it
            dn = l[i, t] < lo
            if not (up or dn) or not pr[i, t]:
                continue
            if up and dn:
                break
            d = -1 if up else 1
            if not _dir_ok(d, dm) or not _trend_ok(d, F[i, X.TREND], tf):
                break
            pe = hi if up else lo
            scale = K[0] / pe
            stop = pe - d * sa * atr * pe
            target = (hi + lo) / 2 if tg == 0 else pe + d * tg * abs(pe - stop)
            px, te, kind, worst = _manage(o, h, l, c, i, t, d, pe, stop, target, tx, 0.0, scale,
                                          0.0, path, 0.0, K)
            v = _book(pe, px, d, kind, scale, K)
            _after(path, i, te, v, v, nwin, gw, gl, K.shape[0] > 4 and K[4] > 0)
            pnl[i] = v
            low[i] = min(worst, v, 0.0)
            ntr[i] = 1
            break


# ---------------------------------------------------------------- noise-area momentum from 09:30
# P: lb_idx, mult, freq, first_t(min after 09:30), stop_mode(0 band,1 vwap,2 tighter), every_bar,
#    reentry, gap_adj, tf, hard_stop_atr, t_end(absolute)
@njit(cache=True)
def fam_noise(o, h, l, c, F, vw, sig, pr, mask, P, pnl, low, ntr, nwin, gw, gl, path, K):
    li = int(P[0]); m = P[1]; fq = int(P[2]); ft = int(P[3]); sm = int(P[4])
    every = int(P[5]); reent = int(P[6]); ga = int(P[7]); tf = int(P[8]); hs = P[9]
    tend = int(P[10])
    last_rel = min(tend, OPEN_T + 389) - OPEN_T
    for i in range(o.shape[0]):
        if not mask[i]:
            continue
        o0 = o[i, OPEN_T]
        pc = F[i, X.RTH_PREV_CLOSE]
        up_a = max(o0, pc) if ga == 1 else o0
        dn_a = min(o0, pc) if ga == 1 else o0
        atr = F[i, X.ATR14]
        real = 0.0
        worst = 0.0
        n = 0
        pos = 0
        pe = 0.0
        scale = 1.0
        hard = 0.0
        once = False
        r = ft
        while r < last_rel:
            t = OPEN_T + r
            s_t = sig[li, i, r]
            ub = up_a * (1.0 + m * s_t)
            lb = dn_a * (1.0 - m * s_t)
            check = (r - ft) % fq == 0
            if pos != 0:
                mk = real + ((l[i, t] - pe) if pos > 0 else (pe - h[i, t])) * scale - K[1]
                worst = min(worst, mk)
                if path.shape[0] > 0:
                    path[i, t] = (real + ((h[i, t] - pe) if pos > 0 else (pe - l[i, t])) * scale - K[1]
                                  if K.shape[0] > 4 and K[4] > 0 else mk)
                if hs > 0 and ((pos > 0 and l[i, t] <= hard) or (pos < 0 and h[i, t] >= hard)):
                    px = min(o[i, t], hard) if pos > 0 else max(o[i, t], hard)
                    v = _book(pe, px, pos, EXIT_STOP, scale, K)
                    real += v
                    pos = 0
                    worst = min(worst, real)
                    _after(path, i, t, real, v, nwin, gw, gl, K.shape[0] > 4 and K[4] > 0)
                    r += 1
                    continue
                if check or every == 1:
                    if sm == 0:
                        lvl = ub if pos > 0 else lb
                    elif sm == 1:
                        lvl = vw[i, r]
                    else:
                        lvl = max(ub, vw[i, r]) if pos > 0 else min(lb, vw[i, r])
                    if (pos > 0 and c[i, t] < lvl) or (pos < 0 and c[i, t] > lvl):
                        v = _book(pe, o[i, t + 1], pos, EXIT_SIGNAL, scale, K)
                        real += v
                        pos = 0
                        worst = min(worst, real)
                        _after(path, i, t + 1, real, v, nwin, gw, gl, K.shape[0] > 4 and K[4] > 0)
            if pos == 0 and check and (reent == 1 or not once) and r < last_rel - 1 and pr[i, t + 1]:
                d = 1 if c[i, t] > ub else (-1 if c[i, t] < lb else 0)
                if d != 0 and _trend_ok(d, F[i, X.TREND], tf):
                    pos = d
                    pe = o[i, t + 1]
                    scale = K[0] / pe
                    hard = pe - d * hs * atr * pe
                    n += 1
                    once = True
                    r += 1
                    continue
            r += 1
        if pos != 0:
            te = OPEN_T + last_rel
            mk = real + ((l[i, te] - pe) if pos > 0 else (pe - h[i, te])) * scale - K[1]
            worst = min(worst, mk)
            if path.shape[0] > 0:
                path[i, te] = (real + ((h[i, te] - pe) if pos > 0 else (pe - l[i, te])) * scale - K[1]
                               if K.shape[0] > 4 and K[4] > 0 else mk)
            v = _book(pe, c[i, te], pos, EXIT_TIME, scale, K)
            real += v
            _after(path, i, te, real, v, nwin, gw, gl, K.shape[0] > 4 and K[4] > 0)
        pnl[i] = real
        low[i] = min(worst, real, 0.0)
        ntr[i] = n


# ---------------------------------------------------------------- end-of-day momentum
# P: sig_mode(0 09:30->10:00, 1 prior cash close->10:00, 2 09:30->entry, 3 prior session close->entry),
#    te, k_atr, follow, stop_atr, tf, tx
@njit(cache=True)
def fam_imom(o, h, l, c, F, vw, sig, pr, mask, P, pnl, low, ntr, nwin, gw, gl, path, K):
    sm = int(P[0]); te = int(P[1]); k = P[2]; fol = int(P[3]); sa = P[4]; tf = int(P[5])
    tx = int(P[6])
    for i in range(o.shape[0]):
        if not mask[i]:
            continue
        atr = F[i, X.ATR14]
        if sm == 0:
            r = c[i, 959] / o[i, OPEN_T] - 1.0
        elif sm == 1:
            r = c[i, 959] / F[i, X.RTH_PREV_CLOSE] - 1.0
        elif sm == 2:
            r = c[i, te - 1] / o[i, OPEN_T] - 1.0
        else:
            r = c[i, te - 1] / F[i, X.SESS_PREV_CLOSE] - 1.0
        if abs(r) < k * atr or r == 0:
            continue
        d = 1 if r > 0 else -1
        if fol == 0:
            d = -d
        if not _trend_ok(d, F[i, X.TREND], tf):
            continue
        te_ = _first_real(pr, i, te, tx - 1)
        if te_ < 0:
            continue
        pe = o[i, te_]
        scale = K[0] / pe
        stop = pe - d * sa * atr * pe if sa > 0 else np.nan
        px, tq, kind, worst = _manage(o, h, l, c, i, te_, d, pe, stop, np.nan, tx, 0.0, scale,
                                      0.0, path, 0.0, K)
        v = _book(pe, px, d, kind, scale, K)
        _after(path, i, tq, v, v, nwin, gw, gl, K.shape[0] > 4 and K[4] > 0)
        pnl[i] = v
        low[i] = min(worst, v, 0.0)
        ntr[i] = 1


# ---------------------------------------------------------------- timed hold (session drift)
# P: te, tx, dir, stop_atr(0 off), tf
@njit(cache=True)
def fam_hold(o, h, l, c, F, vw, sig, pr, mask, P, pnl, low, ntr, nwin, gw, gl, path, K):
    te = int(P[0]); tx = int(P[1]); d = int(P[2]); sa = P[3]; tf = int(P[4])
    for i in range(o.shape[0]):
        if not mask[i] or not _trend_ok(d, F[i, X.TREND], tf):
            continue
        te_ = _first_real(pr, i, te, tx - 1)
        if te_ < 0:
            continue
        atr = F[i, X.ATR14]
        pe = o[i, te_]
        scale = K[0] / pe
        stop = pe - d * sa * atr * pe if sa > 0 else np.nan
        px, tq, kind, worst = _manage(o, h, l, c, i, te_, d, pe, stop, np.nan, tx, 0.0, scale,
                                      0.0, path, 0.0, K)
        v = _book(pe, px, d, kind, scale, K)
        _after(path, i, tq, v, v, nwin, gw, gl, K.shape[0] > 4 and K[4] > 0)
        pnl[i] = v
        low[i] = min(worst, v, 0.0)
        ntr[i] = 1


# ---------------------------------------------------------------- drive after an anchor
# P: anchor, t1(minutes measured), k_atr, follow, stop_atr, target_r(0 none), tx, tf
@njit(cache=True)
def fam_drive(o, h, l, c, F, vw, sig, pr, mask, P, pnl, low, ntr, nwin, gw, gl, path, K):
    ta = int(P[0]); t1 = int(P[1]); k = P[2]; fol = int(P[3]); sa = P[4]; tr_ = P[5]
    tx = int(P[6]); tf = int(P[7])
    for i in range(o.shape[0]):
        if not mask[i]:
            continue
        atr = F[i, X.ATR14]
        r = c[i, ta + t1 - 1] / o[i, ta] - 1.0
        if abs(r) < k * atr or r == 0:
            continue
        d = 1 if r > 0 else -1
        if fol == 0:
            d = -d
        if not _trend_ok(d, F[i, X.TREND], tf):
            continue
        te = _first_real(pr, i, ta + t1, tx - 1)
        if te < 0:
            continue
        pe = o[i, te]
        scale = K[0] / pe
        stop = pe - d * sa * atr * pe
        target = pe + d * tr_ * abs(pe - stop) if tr_ > 0 else np.nan
        px, tq, kind, worst = _manage(o, h, l, c, i, te, d, pe, stop, target, tx, 0.0, scale,
                                      0.0, path, 0.0, K)
        v = _book(pe, px, d, kind, scale, K)
        _after(path, i, tq, v, v, nwin, gw, gl, K.shape[0] > 4 and K[4] > 0)
        pnl[i] = v
        low[i] = min(worst, v, 0.0)
        ntr[i] = 1


# ---------------------------------------------------------------- 09:30 gap (overnight move) fade / go
# P: gmin_atr, gmax_atr, mode(0 fade, 1 go), delay, stop_atr, tgt(fade: fill frac; go: R), tx, tf
@njit(cache=True)
def fam_gap(o, h, l, c, F, vw, sig, pr, mask, P, pnl, low, ntr, nwin, gw, gl, path, K):
    g0 = P[0]; g1 = P[1]; mode = int(P[2]); dl = int(P[3]); sa = P[4]; tg = P[5]
    tx = int(P[6]); tf = int(P[7])
    for i in range(o.shape[0]):
        if not mask[i]:
            continue
        ga = F[i, X.GAP_ATR]
        if not (abs(ga) >= g0 and abs(ga) < g1):
            continue
        d = -1 if ga > 0 else 1
        if mode == 1:
            d = -d
        if not _trend_ok(d, F[i, X.TREND], tf):
            continue
        atr = F[i, X.ATR14]
        te = _first_real(pr, i, OPEN_T + dl, tx - 1)
        if te < 0:
            continue
        pe = o[i, te]
        pc = F[i, X.RTH_PREV_CLOSE]
        stop = pe - d * sa * atr * pe
        if mode == 0:
            target = o[i, OPEN_T] - tg * (o[i, OPEN_T] - pc)
            if (target - pe) * d <= 0:
                continue
        else:
            target = pe + d * tg * abs(pe - stop)
        scale = K[0] / pe
        px, tq, kind, worst = _manage(o, h, l, c, i, te, d, pe, stop, target, tx, 0.0, scale,
                                      0.0, path, 0.0, K)
        v = _book(pe, px, d, kind, scale, K)
        _after(path, i, tq, v, v, nwin, gw, gl, K.shape[0] > 4 and K[4] > 0)
        pnl[i] = v
        low[i] = min(worst, v, 0.0)
        ntr[i] = 1


FAMILIES = {"brk": fam_brk, "fade": fam_fade, "noise": fam_noise, "imom": fam_imom,
            "hold": fam_hold, "drive": fam_drive, "gap": fam_gap}


def run(family, market, params, mask, want_path=False, inst="nq", mark="worst"):
    """mark="best" marks in-position minutes of the path at the bar's favourable extreme
    instead of the adverse one (used to flip a path for a zero-edge baseline: -best is the
    worst-mark path of the reversed trades). P&L, lows and trade tallies do not change."""
    o, h, l, c, F, vw, sig, pr = market
    n, nb = o.shape
    K = INSTRUMENTS[inst].costs()
    if mark == "best":
        K = np.append(K, 1.0)
    out = {k: np.zeros(n) for k in ("pnl", "low", "gw", "gl")}
    ntr = np.zeros(n, np.int32)
    nwin = np.zeros(n, np.int32)
    path = np.zeros((n, nb)) if want_path else np.zeros((0, 0))
    FAMILIES[family](o, h, l, c, F, vw, sig, pr, mask, np.asarray(params, np.float64), out["pnl"],
                     out["low"], ntr, nwin, out["gw"], out["gl"], path, K)
    out.update(ntr=ntr, nwin=nwin, path=path if want_path else None)
    return out
