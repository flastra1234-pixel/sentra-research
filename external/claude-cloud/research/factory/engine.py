"""Numba backtester. One function per strategy family, all with the same contract:

    fam(o, h, l, c, F, vw, sig, mask, P, pnl, low, ntr, path)

o/h/l/c/vw: sessions x 390 (minute 0 = 09:30 ET). F: daily features (features.py).
sig: noise-area sigma, lookbacks x sessions x 390. mask: sessions the strategy may trade.
P: float parameter vector (layout per family in strategies.py).
Outputs per session, for ONE micro (MNQ, $2/pt) at today's price level REF_PRICE:
    pnl  net $ after commission and slippage
    low  worst intraday mark in $ (realized + open P&L at the bar extreme), <= 0
    ntr  trades taken
path (sessions x 390, or shape (0, 0) to skip): running worst mark per minute, used for an
exact intraday low when several strategies are combined.

Fill conventions (conservative):
  * signal on a bar close fills at the NEXT bar's open;
  * stop-entry fills at max(open, level) for longs (min for shorts);
  * if the entry bar also trades through the protective stop, the trade is stopped there;
  * a bar that touches both stop and target counts as a stop;
  * every fill pays SLIP_TICKS ticks, stop exits pay STOP_EXTRA_TICKS more.
Prices are scaled by REF_PRICE / entry price, so a 2010 move is charged at today's size.
"""
from dataclasses import dataclass

import numpy as np
from numba import njit

from . import features as X

REF_PRICE = 29_000.0          # NQ level at the end of the 2026 holdout (2026-10-23 close 29,118)
USD_PER_PT = 2.0              # MNQ
TICK = 0.25
COMMISSION_RT = 2.00          # $ per micro round trip, incl. exchange/NFA fees (conservative)
SLIP_TICKS = 1.0              # per fill
STOP_EXTRA_TICKS = 1.0        # extra on stop exits
ENTRY_COST = COMMISSION_RT / 2 + SLIP_TICKS * TICK * USD_PER_PT
EXIT_COST = COMMISSION_RT / 2 + SLIP_TICKS * TICK * USD_PER_PT
STOP_COST = STOP_EXTRA_TICKS * TICK * USD_PER_PT


@dataclass(frozen=True)
class Instrument:
    """One CME micro. ref: price level every trade is scaled to (today's, roughly)."""
    symbol: str
    dataset: str
    ref: float
    usd_per_pt: float
    tick: float
    commission_rt: float = COMMISSION_RT

    def costs(self) -> np.ndarray:
        """K = [notional per micro, entry cost, exit cost, extra stop cost] in $."""
        fill = self.commission_rt / 2 + SLIP_TICKS * self.tick * self.usd_per_pt
        return np.array([self.ref * self.usd_per_pt, fill, fill,
                         STOP_EXTRA_TICKS * self.tick * self.usd_per_pt])


# ref levels other than NQ are assumptions for late 2026 (no 2026 data for them here):
# a 10% error in ref is a 10% error in that sleeve's $ P&L per micro. Re-run with live prices.
INSTRUMENTS = {
    "nq": Instrument("MNQ", "nas100", REF_PRICE, 2.0, 0.25),
    "rty": Instrument("M2K", "us2000", 2_700.0, 5.0, 0.10),
    "gc": Instrument("MGC", "xau", 4_200.0, 10.0, 0.10),
    "cl": Instrument("MCL", "wti", 65.0, 100.0, 0.01),
}

NB = 390
LAST = NB - 1
UNSET = 1e18                  # path sentinel: no mark written yet

EXIT_TIME, EXIT_STOP, EXIT_TARGET, EXIT_SIGNAL = 0, 1, 2, 3


@njit(cache=True)
def _manage(o, h, l, c, i, t0, d, pe, stop, target, tx, be_r, scale, real, path, worst, K):
    """Hold a position opened at price pe during bar t0. The entry bar is checked against the
    stop only (its high/low may predate the fill). `real` is the day's realized P&L so far;
    marks are real + open P&L at the bar's adverse extreme - entry cost.
    Returns (exit_price, exit_minute, exit_type, running worst mark)."""
    risk = abs(pe - stop) if stop == stop else 0.0
    moved = False
    for t in range(t0, tx + 1):
        if d > 0:
            adverse = (l[i, t] - pe) * scale
        else:
            adverse = (pe - h[i, t]) * scale
        m = real + adverse - K[1]
        if m < worst:
            worst = m
        if path.shape[0] > 0 and m < path[i, t]:
            path[i, t] = m
        if stop == stop:
            hit = (l[i, t] <= stop) if d > 0 else (h[i, t] >= stop)
            if hit:
                if t == t0:
                    px = stop
                else:
                    px = min(o[i, t], stop) if d > 0 else max(o[i, t], stop)
                return px, t, EXIT_STOP, worst
        if t > t0 and target == target:
            hitt = (h[i, t] >= target) if d > 0 else (l[i, t] <= target)
            if hitt:
                px = max(o[i, t], target) if d > 0 else min(o[i, t], target)
                return px, t, EXIT_TARGET, worst
        if be_r > 0 and not moved and risk > 0:
            gain = (c[i, t] - pe) * d
            if gain >= be_r * risk:
                stop = pe
                moved = True
    return c[i, tx], tx, EXIT_TIME, worst


@njit(cache=True)
def _book(pe, px, d, kind, scale, K):
    gross = (px - pe) * d * scale
    cost = K[1] + K[2] + (K[3] if kind == EXIT_STOP else 0.0)
    return gross - cost


@njit(cache=True)
def _fill_path(path, i, t_from, t_to, real):
    if path.shape[0] > 0:
        for t in range(t_from, t_to + 1):
            if real < path[i, t]:
                path[i, t] = real


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


# ---------------------------------------------------------------- family 0: ORB
# P: or_len, cutoff, dir_mode, stop_mode(0 OR-opposite,1 OR-frac,2 ATR), stop_val,
#    target_r(0 none), tx, be_r(0 off), max_trades, tf
@njit(cache=True)
def fam_orb(o, h, l, c, F, vw, sig, mask, P, pnl, low, ntr, path, K):
    orl = int(P[0]); cut = int(P[1]); dm = int(P[2]); sm = int(P[3]); sv = P[4]
    tr_ = P[5]; tx = int(P[6]); be = P[7]; mt = int(P[8]); tf = int(P[9])
    for i in range(o.shape[0]):
        if not mask[i]:
            continue
        atr = F[i, X.ATR14]
        orh = h[i, :orl].max()
        orw = orh - l[i, :orl].min()
        orlw = orh - orw
        real = 0.0
        worst = 0.0
        n = 0
        t = orl
        while t <= min(cut, tx - 1) and n < mt:
            d = 0
            if h[i, t] > orh:
                d = 1
            elif l[i, t] < orlw:
                d = -1
            if d == 0 or not _dir_ok(d, dm) or not _trend_ok(d, F[i, X.TREND], tf):
                t += 1
                continue
            lvl = orh if d > 0 else orlw
            pe = max(o[i, t], lvl) if d > 0 else min(o[i, t], lvl)
            if sm == 0:
                stop = orlw if d > 0 else orh
            elif sm == 1:
                stop = pe - d * sv * orw
            else:
                stop = pe - d * sv * atr * pe
            if (stop - pe) * d >= 0:
                t += 1
                continue
            target = pe + d * tr_ * abs(pe - stop) if tr_ > 0 else np.nan
            scale = K[0] / pe
            px, te, kind, worst = _manage(o, h, l, c, i, t, d, pe, stop, target, tx, be, scale,
                                          real, path, worst, K)
            real += _book(pe, px, d, kind, scale, K)
            n += 1
            if real < worst:
                worst = real
            _fill_path(path, i, te, LAST, real)
            t = te + 1
            # after a long stop-out only the short side can trigger again (and vice versa)
            if d > 0:
                orh = 1e18
            else:
                orlw = -1e18
        pnl[i] = real
        low[i] = min(worst, 0.0)
        ntr[i] = n


# ---------------------------------------------------------------- family 1: noise-area momentum
# P: lb_idx, mult, freq, first_t, stop_mode(0 band,1 vwap,2 tighter of both), check_every_bar,
#    reentry, gap_adj, tf, hard_stop_atr(0 off)
@njit(cache=True)
def fam_noise(o, h, l, c, F, vw, sig, mask, P, pnl, low, ntr, path, K):
    li = int(P[0]); m = P[1]; fq = int(P[2]); ft = int(P[3]); sm = int(P[4])
    every = int(P[5]); reent = int(P[6]); ga = int(P[7]); tf = int(P[8]); hs = P[9]
    for i in range(o.shape[0]):
        if not mask[i]:
            continue
        o0 = o[i, 0]
        pc = F[i, X.PREV_CLOSE]
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
        entered_once = False
        t = ft
        while t < LAST:
            s_t = sig[li, i, t]
            ub = up_a * (1.0 + m * s_t)
            lb = dn_a * (1.0 - m * s_t)
            check = (t - ft) % fq == 0
            if pos != 0:
                # mark
                adverse = ((l[i, t] - pe) if pos > 0 else (pe - h[i, t])) * scale
                mk = real + adverse - K[1]
                if mk < worst:
                    worst = mk
                if path.shape[0] > 0 and mk < path[i, t]:
                    path[i, t] = mk
                if hs > 0:
                    if (pos > 0 and l[i, t] <= hard) or (pos < 0 and h[i, t] >= hard):
                        px = min(o[i, t], hard) if pos > 0 else max(o[i, t], hard)
                        real += _book(pe, px, pos, EXIT_STOP, scale, K)
                        pos = 0
                        if real < worst:
                            worst = real
                        _fill_path(path, i, t, LAST, real)
                        t += 1
                        continue
                if check or every == 1:
                    if sm == 0:
                        lvl = ub if pos > 0 else lb
                    elif sm == 1:
                        lvl = vw[i, t]
                    else:
                        lvl = max(ub, vw[i, t]) if pos > 0 else min(lb, vw[i, t])
                    if (pos > 0 and c[i, t] < lvl) or (pos < 0 and c[i, t] > lvl):
                        px = o[i, t + 1]
                        real += _book(pe, px, pos, EXIT_SIGNAL, scale, K)
                        pos = 0
                        if real < worst:
                            worst = real
                        _fill_path(path, i, t + 1, LAST, real)
            if pos == 0 and check and (reent == 1 or not entered_once) and t < LAST - 1:
                d = 0
                if c[i, t] > ub:
                    d = 1
                elif c[i, t] < lb:
                    d = -1
                if d != 0 and _trend_ok(d, F[i, X.TREND], tf):
                    pos = d
                    pe = o[i, t + 1]
                    scale = K[0] / pe
                    hard = pe - d * hs * atr * pe
                    n += 1
                    entered_once = True
                    t += 1          # position live from bar t+1 (filled at its open)
                    continue
            t += 1
        if pos != 0:
            adverse = ((l[i, LAST] - pe) if pos > 0 else (pe - h[i, LAST])) * scale
            mk = real + adverse - K[1]
            if mk < worst:
                worst = mk
            real += _book(pe, c[i, LAST], pos, EXIT_TIME, scale, K)
            if path.shape[0] > 0:
                path[i, LAST] = min(path[i, LAST], mk, real)
        pnl[i] = real
        low[i] = min(worst, real, 0.0)
        ntr[i] = n


# ---------------------------------------------------------------- family 2: intraday momentum
# P: sig_mode(0 first30 from open, 1 first30 from prev close, 2 open->entry), te, k_atr,
#    follow(1)/fade(0), stop_atr(0 off), tf
@njit(cache=True)
def fam_imom(o, h, l, c, F, vw, sig, mask, P, pnl, low, ntr, path, K):
    sm = int(P[0]); te = int(P[1]); k = P[2]; fol = int(P[3]); sa = P[4]; tf = int(P[5])
    for i in range(o.shape[0]):
        if not mask[i]:
            continue
        atr = F[i, X.ATR14]
        if sm == 0:
            r = c[i, 29] / o[i, 0] - 1.0
        elif sm == 1:
            r = c[i, 29] / F[i, X.PREV_CLOSE] - 1.0
        else:
            r = c[i, te - 1] / o[i, 0] - 1.0
        if abs(r) < k * atr or r == 0:
            continue
        d = 1 if r > 0 else -1
        if fol == 0:
            d = -d
        if not _trend_ok(d, F[i, X.TREND], tf):
            continue
        pe = o[i, te]
        scale = K[0] / pe
        stop = pe - d * sa * atr * pe if sa > 0 else np.nan
        px, tq, kind, worst = _manage(o, h, l, c, i, te, d, pe, stop, np.nan, LAST, 0.0, scale,
                                      0.0, path, 0.0, K)
        real = _book(pe, px, d, kind, scale, K)
        _fill_path(path, i, tq, LAST, real)
        pnl[i] = real
        low[i] = min(worst, real, 0.0)
        ntr[i] = 1


# ---------------------------------------------------------------- family 3: opening gap
# P: gmin_atr, gmax_atr, mode(0 fade,1 go), delay, stop_atr, tgt(fade: fill frac; go: R),
#    tx, tf
@njit(cache=True)
def fam_gap(o, h, l, c, F, vw, sig, mask, P, pnl, low, ntr, path, K):
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
        pe = o[i, dl]
        pc = F[i, X.PREV_CLOSE]
        stop = pe - d * sa * atr * pe
        if mode == 0:
            target = o[i, 0] - tg * (o[i, 0] - pc)
            if (target - pe) * d <= 0:
                continue
        else:
            target = pe + d * tg * abs(pe - stop)
        scale = K[0] / pe
        px, tq, kind, worst = _manage(o, h, l, c, i, dl, d, pe, stop, target, tx, 0.0, scale,
                                      0.0, path, 0.0, K)
        real = _book(pe, px, d, kind, scale, K)
        _fill_path(path, i, tq, LAST, real)
        pnl[i] = real
        low[i] = min(worst, real, 0.0)
        ntr[i] = 1


# ---------------------------------------------------------------- family 4: VWAP reversion
# P: k_atr, t_start, t_end, stop_atr, tgt_mode(0 vwap at entry, 1 live vwap cross), max_trades, tf
@njit(cache=True)
def fam_vwap(o, h, l, c, F, vw, sig, mask, P, pnl, low, ntr, path, K):
    k = P[0]; ts = int(P[1]); tend = int(P[2]); sa = P[3]; tm = int(P[4]); mt = int(P[5])
    tf = int(P[6])
    for i in range(o.shape[0]):
        if not mask[i]:
            continue
        atr = F[i, X.ATR14]
        o0 = o[i, 0]
        real = 0.0
        worst = 0.0
        n = 0
        t = ts
        while t <= tend and n < mt:
            dev = (c[i, t] - vw[i, t]) / (atr * o0)
            d = 0
            if dev > k:
                d = -1
            elif dev < -k:
                d = 1
            if d == 0 or not _trend_ok(d, F[i, X.TREND], tf):
                t += 1
                continue
            pe = o[i, t + 1]
            scale = K[0] / pe
            stop = pe - d * sa * atr * pe
            if tm == 0:
                target = vw[i, t]
                px, te, kind, worst = _manage(o, h, l, c, i, t + 1, d, pe, stop, target, LAST, 0.0,
                                              scale, real, path, worst, K)
            else:
                px = c[i, LAST]
                te = LAST
                kind = EXIT_TIME
                for u in range(t + 1, LAST + 1):
                    adverse = ((l[i, u] - pe) if d > 0 else (pe - h[i, u])) * scale
                    mk = real + adverse - K[1]
                    if mk < worst:
                        worst = mk
                    if path.shape[0] > 0 and mk < path[i, u]:
                        path[i, u] = mk
                    if (d > 0 and l[i, u] <= stop) or (d < 0 and h[i, u] >= stop):
                        px = stop if u == t + 1 else (min(o[i, u], stop) if d > 0 else max(o[i, u], stop))
                        te = u
                        kind = EXIT_STOP
                        break
                    if u < LAST and ((d > 0 and c[i, u] >= vw[i, u]) or (d < 0 and c[i, u] <= vw[i, u])):
                        px = o[i, u + 1]
                        te = u + 1
                        kind = EXIT_SIGNAL
                        break
            real += _book(pe, px, d, kind, scale, K)
            n += 1
            if real < worst:
                worst = real
            _fill_path(path, i, te, LAST, real)
            t = te + 1
        pnl[i] = real
        low[i] = min(worst, 0.0)
        ntr[i] = n


# ---------------------------------------------------------------- family 5: prior-day / overnight levels
# P: level(0 prior RTH H/L, 1 overnight H/L), mode(0 breakout, 1 fade at level), dir_mode,
#    stop_atr, target_r(0 none), tx, cutoff, tf
@njit(cache=True)
def fam_level(o, h, l, c, F, vw, sig, mask, P, pnl, low, ntr, path, K):
    lv = int(P[0]); mode = int(P[1]); dm = int(P[2]); sa = P[3]; tr_ = P[4]; tx = int(P[5])
    cut = int(P[6]); tf = int(P[7])
    for i in range(o.shape[0]):
        if not mask[i]:
            continue
        hi_l = F[i, X.PREV_HIGH] if lv == 0 else F[i, X.ON_HIGH]
        lo_l = F[i, X.PREV_LOW] if lv == 0 else F[i, X.ON_LOW]
        if not (hi_l == hi_l and lo_l == lo_l):
            continue
        o0 = o[i, 0]
        if not (o0 < hi_l and o0 > lo_l):
            continue
        atr = F[i, X.ATR14]
        for t in range(0, min(cut, tx - 1) + 1):
            up = h[i, t] >= hi_l
            dn = l[i, t] <= lo_l
            if not (up or dn):
                continue
            if up and dn:
                break
            if mode == 0:
                d = 1 if up else -1
                pe = max(o[i, t], hi_l) if up else min(o[i, t], lo_l)
            else:
                d = -1 if up else 1
                pe = hi_l if up else lo_l
            if not _dir_ok(d, dm) or not _trend_ok(d, F[i, X.TREND], tf):
                break
            scale = K[0] / pe
            stop = pe - d * sa * atr * pe
            target = pe + d * tr_ * abs(pe - stop) if tr_ > 0 else np.nan
            px, tq, kind, worst = _manage(o, h, l, c, i, t, d, pe, stop, target, tx, 0.0, scale,
                                          0.0, path, 0.0, K)
            real = _book(pe, px, d, kind, scale, K)
            _fill_path(path, i, tq, LAST, real)
            pnl[i] = real
            low[i] = min(worst, real, 0.0)
            ntr[i] = 1
            break


# ---------------------------------------------------------------- family 6: time-of-day drift
# P: te, hold(0 = to close), dir(+1/-1), stop_atr(0 off), tf
@njit(cache=True)
def fam_tod(o, h, l, c, F, vw, sig, mask, P, pnl, low, ntr, path, K):
    te = int(P[0]); hold = int(P[1]); d = int(P[2]); sa = P[3]; tf = int(P[4])
    tx = LAST if hold == 0 else min(te + hold - 1, LAST)
    for i in range(o.shape[0]):
        if not mask[i] or not _trend_ok(d, F[i, X.TREND], tf):
            continue
        atr = F[i, X.ATR14]
        pe = o[i, te]
        scale = K[0] / pe
        stop = pe - d * sa * atr * pe if sa > 0 else np.nan
        px, tq, kind, worst = _manage(o, h, l, c, i, te, d, pe, stop, np.nan, tx, 0.0, scale,
                                      0.0, path, 0.0, K)
        real = _book(pe, px, d, kind, scale, K)
        _fill_path(path, i, tq, LAST, real)
        pnl[i] = real
        low[i] = min(worst, real, 0.0)
        ntr[i] = 1


# ---------------------------------------------------------------- family 7: opening-drive continuation / fade
# P: t1, k_atr, follow(1)/fade(0), stop_atr, target_r(0 none), tx, tf
@njit(cache=True)
def fam_drive(o, h, l, c, F, vw, sig, mask, P, pnl, low, ntr, path, K):
    t1 = int(P[0]); k = P[1]; fol = int(P[2]); sa = P[3]; tr_ = P[4]; tx = int(P[5]); tf = int(P[6])
    for i in range(o.shape[0]):
        if not mask[i]:
            continue
        atr = F[i, X.ATR14]
        r = c[i, t1] / o[i, 0] - 1.0
        if abs(r) < k * atr or r == 0:
            continue
        d = 1 if r > 0 else -1
        if fol == 0:
            d = -d
        if not _trend_ok(d, F[i, X.TREND], tf):
            continue
        pe = o[i, t1 + 1]
        scale = K[0] / pe
        stop = pe - d * sa * atr * pe
        target = pe + d * tr_ * abs(pe - stop) if tr_ > 0 else np.nan
        px, tq, kind, worst = _manage(o, h, l, c, i, t1 + 1, d, pe, stop, target, tx, 0.0, scale,
                                      0.0, path, 0.0, K)
        real = _book(pe, px, d, kind, scale, K)
        _fill_path(path, i, tq, LAST, real)
        pnl[i] = real
        low[i] = min(worst, real, 0.0)
        ntr[i] = 1


# ---------------------------------------------------------------- family 8: 5-minute RSI(2) reversion
# P: lo(entry threshold, short at 100-lo), exit_level, max_bars(5m), stop_atr, max_trades, tf
@njit(cache=True)
def fam_rsi(o, h, l, c, F, vw, sig, mask, P, pnl, low, ntr, path, K):
    lo_ = P[0]; ex = P[1]; mb = int(P[2]); sa = P[3]; mt = int(P[4]); tf = int(P[5])
    for i in range(o.shape[0]):
        if not mask[i]:
            continue
        atr = F[i, X.ATR14]
        real = 0.0
        worst = 0.0
        n = 0
        ag = 0.0
        al = 0.0
        prev = c[i, 4]
        pos = 0
        pe = 0.0
        scale = 1.0
        stop = 0.0
        bars = 0
        k5 = 1
        t = 9
        while t <= LAST:
            ch = c[i, t] - prev
            prev = c[i, t]
            g = ch if ch > 0 else 0.0
            ls = -ch if ch < 0 else 0.0
            if k5 <= 2:
                ag = (ag * (k5 - 1) + g) / k5
                al = (al * (k5 - 1) + ls) / k5
            else:
                ag = (ag + g) / 2.0
                al = (al + ls) / 2.0
            k5 += 1
            rsi = 100.0 if al == 0 else 100.0 - 100.0 / (1.0 + ag / al)
            if pos != 0:
                bars += 1
                done = False
                if (pos > 0 and rsi >= ex) or (pos < 0 and rsi <= 100.0 - ex) or bars >= mb:
                    done = True
                if done or t + 1 > LAST:
                    px = o[i, t + 1] if t + 1 <= LAST else c[i, LAST]
                    real += _book(pe, px, pos, EXIT_SIGNAL, scale, K)
                    pos = 0
                    if real < worst:
                        worst = real
                    _fill_path(path, i, min(t + 1, LAST), LAST, real)
            if pos == 0 and k5 > 3 and t >= 29 and t <= 359 and n < mt:
                d = 0
                if rsi < lo_:
                    d = 1
                elif rsi > 100.0 - lo_:
                    d = -1
                if d != 0 and _trend_ok(d, F[i, X.TREND], tf):
                    pe = o[i, t + 1]
                    scale = K[0] / pe
                    stop = pe - d * sa * atr * pe
                    pos = d
                    bars = 0
                    n += 1
                    # walk the next 5 one-minute bars for stop / marks
            if pos != 0:
                t_end = min(t + 5, LAST)
                for u in range(t + 1, t_end + 1):
                    adverse = ((l[i, u] - pe) if pos > 0 else (pe - h[i, u])) * scale
                    mk = real + adverse - K[1]
                    if mk < worst:
                        worst = mk
                    if path.shape[0] > 0 and mk < path[i, u]:
                        path[i, u] = mk
                    if (pos > 0 and l[i, u] <= stop) or (pos < 0 and h[i, u] >= stop):
                        px = stop if u == t + 1 else (min(o[i, u], stop) if pos > 0 else max(o[i, u], stop))
                        real += _book(pe, px, pos, EXIT_STOP, scale, K)
                        pos = 0
                        if real < worst:
                            worst = real
                        _fill_path(path, i, u, LAST, real)
                        break
            t += 5
        if pos != 0:
            real += _book(pe, c[i, LAST], pos, EXIT_TIME, scale, K)
            if path.shape[0] > 0:
                path[i, LAST] = min(path[i, LAST], real)
        pnl[i] = real
        low[i] = min(worst, real, 0.0)
        ntr[i] = n


FAMILIES = {
    "orb": fam_orb, "noise": fam_noise, "imom": fam_imom, "gap": fam_gap, "vwap": fam_vwap,
    "level": fam_level, "tod": fam_tod, "drive": fam_drive, "rsi": fam_rsi,
}
FAMILY_ID = {k: i for i, k in enumerate(FAMILIES)}


def run(family, market, params, mask, want_path=False, inst="nq"):
    o, h, l, c, F, vw, sig = market
    K = INSTRUMENTS[inst].costs()
    n = o.shape[0]
    pnl = np.zeros(n)
    low = np.zeros(n)
    ntr = np.zeros(n, np.int32)
    path = np.full((n, NB), UNSET) if want_path else np.zeros((0, 0))
    FAMILIES[family](o, h, l, c, F, vw, sig, mask, np.asarray(params, np.float64), pnl, low, ntr, path, K)
    if want_path:
        path[path >= UNSET / 2] = 0.0       # minutes before the first fill of the day
    return pnl, low, ntr, (path if want_path else None)
