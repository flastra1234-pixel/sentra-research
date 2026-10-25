"""Round-2 pre-registered tests (research/PREREGISTRATION_round2.md): N1 VIX term structure, N2
QQQ-vs-SPY leadership agreeing with NQ, N3 overnight move agreeing with the first 30 minutes.
Same machinery and criteria as round 1 (lx_prereg); Holm within round 2 and across all seven
hypotheses of both rounds. Committed before it is run; not to be edited afterwards."""
import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import lx_features as X
from . import lx_prereg as P1
from . import lx_run as R

EXT = P1.EXT
ROUND1 = Path(__file__).resolve().parents[1] / "results" / "goal70.json"


def _first30(sym):
    """09:30 open -> 09:59 close return per NYSE date from the consolidated-tape 1-minute file."""
    s = pd.read_parquet(EXT / "etf1m" / f"{sym}_1m.parquet", columns=["ts_utc", "open", "close"])
    t = s["ts_utc"].dt.tz_convert("America/New_York")
    s = s.assign(date=t.dt.tz_localize(None).dt.normalize(), hm=t.dt.strftime("%H:%M"))
    o = s[s["hm"] == "09:30"].set_index("date")["open"]
    c = s[s["hm"] == "09:59"].set_index("date")["close"]
    out = pd.concat([o, c], axis=1, keys=["o", "c"]).dropna()
    return out["c"] / out["o"] - 1


def _prior_close(series, dates):
    """Value of a daily series at the last date strictly before each session date."""
    s = series.dropna().sort_index()
    d = pd.DatetimeIndex(dates).normalize().values
    idx = np.searchsorted(s.index.values, d, side="left") - 1
    return np.where(idx >= 0, s.values[np.clip(idx, 0, None)], np.nan)


def hypotheses(mkt, F, dates):
    o, c = mkt[0], mkt[3]
    nq30 = np.sign(c[:, 959] / o[:, 930] - 1)
    vx = pd.read_csv(EXT / "vix" / "vix_daily.csv", parse_dates=["date"]).set_index("date")
    ratio = _prior_close(vx["VIX9D"] / vx["VIX"], dates)
    n1 = ratio >= 1.0
    dn = pd.DatetimeIndex(dates).normalize()
    q = _first30("qqq").reindex(dn).to_numpy()
    s = _first30("spy").reindex(dn).to_numpy()
    # leadership = QQQ's 09:30-10:00 return beyond what its beta to SPY explains; beta from the
    # previous 60 sessions with both returns (raw QQQ - SPY just restates direction x beta > 1)
    qs, ss = pd.Series(q), pd.Series(s)
    ok = qs.notna() & ss.notna()
    cov = (qs * ss).where(ok).shift(1).rolling(60, min_periods=40).mean()
    var = (ss ** 2).where(ok).shift(1).rolling(60, min_periods=40).mean()
    beta = (cov / var).to_numpy()
    rel = np.sign(q - beta * s)
    n2 = (rel == nq30) & (nq30 != 0) & (rel != 0)
    on = np.sign(o[:, 930] / F[:, X.RTH_PREV_CLOSE] - 1)
    n3 = (on == nq30) & (nq30 != 0)
    return {"N1": ("pnl", n1, False, ~np.isnan(ratio)),
            "N2": ("pnl", n2, False, ~np.isnan(q) & ~np.isnan(s) & ~np.isnan(beta)),
            "N3": ("pnl", n3, False)}


def design_tests(seed=17):
    mkt, dates, F = R.market("nq20")
    years = pd.DatetimeIndex(dates).year.to_numpy()
    canon, _, _ = P1._base(mkt, F, dates)
    valid0 = (F[:, X.VALID] > 0) & np.isin(years, P1.DESIGN_YEARS)
    pnl, traded = canon["pnl"], canon["ntr"] > 0
    rng = np.random.default_rng(seed)
    rows = []
    for name, spec in hypotheses(mkt, F, dates).items():
        _, flag, two = spec[:3]
        valid = valid0 & (spec[3] if len(spec) > 3 else True)
        obs, p, per_year = P1._perm_test(pnl, flag, years, valid, two, rng)
        same = sum(1 for v in per_year.values() if v is not None and np.sign(v) == np.sign(obs))
        on, off = valid & flag, valid & ~flag
        eff_traded = float(pnl[on & traded].mean() - pnl[off & traded].mean())
        size_ok = abs(eff_traded) >= 25.0 and np.sign(eff_traded) == np.sign(obs) and obs > 0
        rows.append({"hypothesis": name, "n_flag": int(on.sum()), "n_other": int(off.sum()),
                     "effect_per_session": obs, "effect_per_traded_day": eff_traded, "p_perm": p,
                     "per_year": per_year, "years_same_sign": same, "size_ok": bool(size_ok),
                     "mean_flag": float(pnl[on].mean()), "mean_other": float(pnl[off].mean())})
    p2 = np.array([r["p_perm"] for r in rows])
    within = P1._holm(p2)
    r1 = json.load(open(ROUND1))["prereg"]["hypotheses"]
    p_all = np.r_[[h["p_perm"] for h in r1], p2]
    across = P1._holm(p_all)[len(r1):]
    for r, a, b in zip(rows, within, across):
        r["p_holm_round2"] = float(a)
        r["p_holm_all7"] = float(b)
        r["qualified"] = bool(a < 0.05 and b < 0.05 and r["years_same_sign"] >= 4 and r["size_ok"])
    return {"design_years": list(P1.DESIGN_YEARS), "hypotheses": rows,
            "round1_p": [h["p_perm"] for h in r1],
            "qualified": [r["hypothesis"] for r in rows if r["qualified"]]}


def single_look(design, seed=19):
    qual = design["qualified"]
    if not qual:
        return {"run": False, "reason": "no round-2 hypothesis qualified on 2020-2024; 2025-2026 not touched"}
    mkt, dates, F = R.market("nq20")
    canon, _, _ = P1._base(mkt, F, dates)
    m0 = (F[:, X.VALID] > 0) & (dates >= P1.LOOK[0]) & (dates <= P1.LOOK[1])
    hyp = hypotheses(mkt, F, dates)
    out = {"run": True, "results": {}}
    for name in qual:
        spec = hyp[name]
        m = m0 & (spec[3] if len(spec) > 3 else True)
        if m.sum() < 20:
            out["results"][name] = {"evaluable": False, "sessions": int(m.sum())}
            continue
        out["results"][name] = {"evaluable": True, **P1.look_stats(canon["pnl"][m], canon["low"][m],
                                                                   canon["ntr"][m], spec[1][m], seed)}
    return out
