"""New predictive information for the 2020+ NQ Lucid sessions: can a 10:00 ET forecast tell
trend days (where intraday momentum earns) from range days (where it bleeds)?

Everything here is decided at 10:00 ET from information known then; labels use only bars after
10:00, so no feature window overlaps a label window. Design data = 2020-2024; the protocol for
the single 2025-2026 evaluation is fixed in research/PREREGISTRATION.md before it is run.

The momentum sleeve being filtered is the canonical noise-area spec from the published method
(14-day sigma, band x1.0, gap-adjusted anchors, checks every 30 min from 10:00, trailing exit at
the tighter of band / VWAP, flat 16:00), not one of the factory's selected variants.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import lx_engine as LE
from . import lx_features as X

T0 = 960                      # decision bar: 10:00 ET (features use bars < 960)
CANON_NOISE = [1, 1.0, 30, 30, 2, 0, 1, 1, 0, 0.0, 1319]
EXT = Path("/home/user/sentra-data/raw/ext")


def _trail(x, n):
    """Mean of the previous n values (excludes the current one)."""
    s = pd.Series(x, dtype=float)
    return s.shift(1).rolling(n, min_periods=n).mean().to_numpy()


def labels(mkt, F):
    o, h, l, c = mkt[:4]
    hi, lo = h[:, T0:1320].max(axis=1), l[:, T0:1320].min(axis=1)
    rest = c[:, 1319] - c[:, T0 - 1]
    trend_rest = np.abs(rest) >= 0.5 * (hi - lo)
    canon = LE.run("noise", mkt, CANON_NOISE, F[:, X.VALID] > 0)
    return pd.DataFrame({"trend_rest": trend_rest, "rest_up": rest > 0,
                         "canon_pnl": canon["pnl"], "canon_traded": canon["ntr"] > 0})


def nq_features(mkt, F, dates, canon_pnl, trend_rest):
    o, h, l, c, _, _, _, pr = mkt
    v = None
    from .lx_run import sessions
    s = sessions("nq20")
    assert len(s.dates) == len(dates) and (s.dates == dates).all()
    v = s.v
    atr = F[:, X.ATR14]
    o930 = o[:, 930]
    vol30 = v[:, 930:T0].sum(axis=1)
    on_vol = v[:, :930].sum(axis=1)
    r1 = np.abs(np.diff(c[:, 930:T0], axis=1)).sum(axis=1)
    first30 = c[:, T0 - 1] / o930 - 1
    or_hi, or_lo = h[:, 930:T0].max(axis=1), l[:, 930:T0].min(axis=1)
    d = pd.DatetimeIndex(dates)
    third_fri = (d.dayofweek == 4) & (d.day >= 15) & (d.day <= 21)
    month_end = d.is_month_end | ((d + pd.offsets.BDay(1)).month != d.month)
    feats = pd.DataFrame({
        "rvol30": vol30 / _trail(vol30, 20),
        "on_rvol": on_vol / _trail(on_vol, 20),
        "or30_atr": (or_hi - or_lo) / o930 / atr,
        "on_range_atr": F[:, X.ON_RANGE_ATR],
        "abs_gap_atr": np.abs(F[:, X.GAP_ATR]),
        "eff30": np.abs(c[:, T0 - 1] - o930) / np.where(r1 > 0, r1, np.nan),
        "abs_first30_atr": np.abs(first30) / atr,
        "volr": F[:, X.VOLR],
        "atr14": atr,
        "trend_freq20": _trail(trend_rest.astype(float), 20),
        "canon_pnl20": _trail(canon_pnl, 20),
        "prev_trend": pd.Series(trend_rest.astype(float)).shift(1).to_numpy(),
        "opex": third_fri.astype(float),
        "month_end": np.asarray(month_end, float),
        "dow_mon": (d.dayofweek == 0).astype(float),
        "dow_fri": (d.dayofweek == 4).astype(float),
    })
    return feats


def ext_features(dates):
    """Calendar events and VIX, if the acquired datasets exist (ex-ante: event schedules are
    public in advance; VIX uses the PRIOR session's close)."""
    out = pd.DataFrame(index=range(len(dates)))
    d = pd.DatetimeIndex(dates)
    cal = EXT / "calendar" / "events.csv"
    if cal.exists():
        ev = pd.read_csv(cal)
        ev["date"] = pd.to_datetime(ev["date"])
        for name in ("FOMC", "CPI", "NFP"):
            days = set(ev.loc[ev["event"].str.upper() == name, "date"].dt.normalize())
            out[f"ev_{name.lower()}"] = np.array([x in days for x in d.normalize()], float)
    vix = EXT / "vix" / "vix_daily.csv"
    if vix.exists():
        vx = pd.read_csv(vix, parse_dates=["date"]).set_index("date").sort_index()
        col = [x for x in vx.columns if x.lower() in ("vix", "vix_close", "close")]
        if col:
            s = vx[col[0]].astype(float)
            prev = s.shift(1)
            # the value known at 10:00 ET on session date D is the close of the last day < D
            idx = np.searchsorted(s.index.values, d.normalize().values, side="left") - 1
            ok = idx >= 0
            out["vix_prev"] = np.where(ok, s.values[np.clip(idx, 0, None)], np.nan)
            ch = (s / prev - 1).values
            out["vix_chg_prev"] = np.where(ok, ch[np.clip(idx, 0, None)], np.nan)
    return out


def build(mkt, F, dates):
    lab = labels(mkt, F)
    feats = nq_features(mkt, F, dates, lab["canon_pnl"].to_numpy(), lab["trend_rest"].to_numpy())
    ext = ext_features(dates)
    return pd.concat([feats, ext], axis=1), lab


# ---------------------------------------------------------------- chronological evaluation
def auc(y, s):
    y = np.asarray(y, bool); s = np.asarray(s, float)
    ok = ~np.isnan(s)
    y, s = y[ok], s[ok]
    n1, n0 = y.sum(), (~y).sum()
    if n1 == 0 or n0 == 0:
        return np.nan
    r = pd.Series(s).rank().to_numpy()
    return float((r[y].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def feature_scan(feats, y, years, test_years=(2022, 2023, 2024), n_perm=2000, seed=0):
    """Per feature: sign learned on train years (< test year) via AUC, applied to the test year.
    Statistic = mean of the per-test-year AUCs (year-stratified, so differences in feature level
    or base rate between years cannot pose as signal); permutation p-value with labels shuffled
    within year. The pooled AUC is reported for reference only."""
    rng = np.random.default_rng(seed)
    rows = []
    for col in feats.columns:
        x = feats[col].to_numpy(float)
        oos_s, oos_y, per, signs = [], [], {}, []
        for ty in test_years:
            tr, te = years < ty, years == ty
            a_tr = auc(y[tr], x[tr])
            sign = 1.0 if (np.isnan(a_tr) or a_tr >= 0.5) else -1.0
            signs.append(int(sign))
            oos_s.append(sign * x[te]); oos_y.append(y[te])
            per[ty] = auc(y[te], sign * x[te])
        s_all, y_all = np.concatenate(oos_s), np.concatenate(oos_y)
        def stat(ys):
            return float(np.nanmean([auc(q, s) for q, s in zip(ys, oos_s)]))
        a = stat(oos_y)
        # permutation null: shuffle labels within each test year
        null = np.array([stat([rng.permutation(q) for q in oos_y]) for _ in range(n_perm)])
        p = float((np.sum(null >= a) + 1) / (n_perm + 1))
        rows.append({"feature": col, "oos_auc_mean": a, "oos_auc_pooled": auc(y_all, s_all), "p_perm": p,
                     "learned_sign": signs, **{f"auc_{k}": v for k, v in per.items()},
                     "consistent": all((v > 0.5) for v in per.values() if not np.isnan(v))})
    df = pd.DataFrame(rows).sort_values("p_perm")
    # Holm-Bonferroni over all features scanned for this label
    m = len(df)
    holm = np.minimum(1.0, np.maximum.accumulate((m - np.arange(m)) * df["p_perm"].to_numpy()))
    df["p_holm"] = holm
    return df
