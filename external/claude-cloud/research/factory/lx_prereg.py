"""Pre-registered tests (research/PREREGISTRATION.md): event-calendar and cross-asset hypotheses on
the canonical noise-area momentum strategy, 1 MNQ.

design_tests() uses 2020-2024 sessions only. single_look() is the one 2025-2026 evaluation; it
refuses to run unless design_tests() qualified at least one hypothesis, and it runs only the
qualified ones. Both are committed before they are run, and neither is to be edited afterwards.
Fixed choices not spelled out in the pre-registration document:
  * permutation tests shuffle the day-type label among valid sessions within each year, 20,000
    draws, one-sided for E1/E3/X1 and two-sided for E2;
  * the "4 of 5 design years" sign check counts years whose effect has the pooled sign;
  * the single-look bootstrap is a stationary block bootstrap (mean block 5 sessions), 20,000
    draws, of d_t = rule P&L - every-day P&L;
  * "account metrics better" = owner $/month strictly higher and 12-month survival not lower,
    goal70.funded_life_policy with a $1,000 buffer, at both 1 and 3 MNQ;
  * added before any run, stricter than the document: in 2025-2026 the day-type effect itself must
    keep its design sign (mean P&L on flagged days vs other days), because "the rule beats trading
    every day" alone would also pass if the strategy simply lost money on all days.
"""
from pathlib import Path

import numpy as np
import pandas as pd

from . import goal70 as G
from . import lx_engine as LE
from . import lx_features as X
from . import lx_newinfo as N
from . import lx_run as R

EXT = Path("/home/user/sentra-data/raw/ext")
N_PERM = 20000
DESIGN_YEARS = (2020, 2021, 2022, 2023, 2024)
LOOK = (np.datetime64("2025-01-01"), np.datetime64("2026-10-23"))


def _events(dates):
    # released events at their scheduled time only: CPI/NFP 08:30 ET, FOMC statements 14:00 ET
    # (the two unscheduled March 2020 FOMC actions at other times are not "statement days")
    ev = pd.read_csv(EXT / "calendar" / "events.csv")
    ev["date"] = pd.to_datetime(ev["date"]).dt.normalize()
    if "status" in ev:
        ev = ev[ev["status"].str.lower() == "released"]
    when = {"FOMC": "14:00", "CPI": "08:30", "NFP": "08:30"}
    d = pd.DatetimeIndex(dates).normalize()
    out = {}
    for name in ("FOMC", "CPI", "NFP"):
        sel = ev["event"].str.upper() == name
        if "time_et" in ev:
            sel &= ev["time_et"].astype(str).str.startswith(when[name])
        days = set(ev.loc[sel, "date"])
        out[name] = np.array([x in days for x in d])
    return out


def build_spy_first30():
    """Derive SPY's 09:30-10:00 ET return per NYSE date from the consolidated-tape 1-minute file
    (open of the 09:30 bar to close of the 09:59 bar, the same span as NQ's o[930] -> c[959]).
    Days missing either bar are left out. Uses only the main SIP file, not the IEX supplement."""
    s = pd.read_parquet(EXT / "etf1m" / "spy_1m.parquet", columns=["ts_utc", "open", "close"])
    t = s["ts_utc"].dt.tz_convert("America/New_York")
    s = s.assign(date=t.dt.tz_localize(None).dt.normalize(), hm=t.dt.strftime("%H:%M"))
    o = s[s["hm"] == "09:30"].set_index("date")["open"]
    c = s[s["hm"] == "09:59"].set_index("date")["close"]
    out = pd.concat([o, c], axis=1, keys=["o", "c"]).dropna()
    out["ret_0930_1000"] = out["c"] / out["o"] - 1
    out.index.name = "date"
    out[["ret_0930_1000"]].to_csv(EXT / "etf1m" / "spy_first30.csv")
    return out


def _spy_first30_sign(dates):
    """Sign of SPY's 09:30-10:00 ET return per session date, or None if the data is missing."""
    p = EXT / "etf1m" / "spy_first30.csv"
    if not p.exists():
        return None
    s = pd.read_csv(p, parse_dates=["date"]).set_index("date")["ret_0930_1000"]
    s.index = s.index.normalize()
    return pd.Series(np.sign(s)).reindex(pd.DatetimeIndex(dates).normalize()).to_numpy()


def _base(mkt, F, dates):
    canon = LE.run("noise", mkt, N.CANON_NOISE, F[:, X.VALID] > 0)
    lab = N.labels(mkt, F)
    c = mkt[3]
    nq_first30 = np.sign(c[:, N.T0 - 1] / mkt[0][:, 930] - 1)
    return canon, lab, nq_first30


def _perm_test(y, flag, years, valid, two_sided, rng):
    """Mean(y | flag) - mean(y | not flag), labels permuted within year among valid sessions."""
    v = valid
    yv, fv, yr = y[v], flag[v], years[v]
    def stat(f):
        return yv[f].mean() - yv[~f].mean()
    obs = stat(fv)
    groups = [np.where(yr == k)[0] for k in np.unique(yr)]
    null = np.empty(N_PERM)
    for i in range(N_PERM):
        f = fv.copy()
        for g in groups:
            f[g] = fv[g][rng.permutation(len(g))]
        null[i] = stat(f)
    if two_sided:
        p = (np.sum(np.abs(null) >= abs(obs)) + 1) / (N_PERM + 1)
    else:
        p = (np.sum(null >= obs) + 1) / (N_PERM + 1)
    per_year = {int(k): float(yv[(yr == k) & fv].mean() - yv[(yr == k) & ~fv].mean())
                if ((yr == k) & fv).any() and ((yr == k) & ~fv).any() else None for k in np.unique(yr)}
    return float(obs), float(p), per_year


def _holm(ps):
    order = np.argsort(ps)
    m = len(ps)
    adj = np.empty(m)
    run = 0.0
    for r, i in enumerate(order):
        run = max(run, min(1.0, (m - r) * ps[i]))
        adj[i] = run
    return adj


def hypotheses(mkt, F, dates):
    """Day-type flags per hypothesis (all known before 10:00 ET on the session)."""
    ev = _events(dates)
    out = {"E1": ("pnl", ev["CPI"] | ev["NFP"], False),
           "E2": ("pnl", ev["FOMC"], True),
           "E3": ("trend", ev["CPI"] | ev["NFP"] | ev["FOMC"], False)}
    spy = _spy_first30_sign(dates)
    if spy is not None:
        _, _, nq = _base(mkt, F, dates)
        agree = (spy == nq) & (nq != 0)
        out["X1"] = ("pnl", agree, False, ~np.isnan(spy))
    return out


def design_tests(seed=11):
    mkt, dates, F = R.market("nq20")
    years = pd.DatetimeIndex(dates).year.to_numpy()
    canon, lab, _ = _base(mkt, F, dates)
    valid0 = (F[:, X.VALID] > 0) & np.isin(years, DESIGN_YEARS)
    pnl = canon["pnl"]
    traded = canon["ntr"] > 0
    trend = lab["trend_rest"].to_numpy().astype(float)
    rng = np.random.default_rng(seed)
    rows = []
    for name, spec in hypotheses(mkt, F, dates).items():
        kind, flag, two = spec[:3]
        valid = valid0 & (spec[3] if len(spec) > 3 else True)
        y = pnl if kind == "pnl" else trend
        obs, p, per_year = _perm_test(y, flag, years, valid, two, rng)
        sgn = np.sign(obs)
        same = sum(1 for v in per_year.values() if v is not None and np.sign(v) == sgn)
        on, off = valid & flag, valid & ~flag
        if kind == "pnl":
            eff_traded = float(pnl[on & traded].mean() - pnl[off & traded].mean())
            # the traded-day effect must point the same way as the per-session effect, which
            # decides the direction of the rule that would be traded
            size_ok = abs(eff_traded) >= 25.0 and np.sign(eff_traded) == np.sign(obs) and (two or obs > 0)
        else:
            eff_traded = None
            size_ok = obs >= 0.05
        rows.append({"hypothesis": name, "two_sided": two, "n_flag": int(on.sum()), "n_other": int(off.sum()),
                     "effect_per_session": obs, "effect_per_traded_day": eff_traded, "p_perm": p,
                     "per_year": per_year, "years_same_sign": same, "size_ok": bool(size_ok),
                     "mean_flag": float(y[on].mean()), "mean_other": float(y[off].mean())})
    adj = _holm(np.array([r["p_perm"] for r in rows]))
    for r, a in zip(rows, adj):
        r["p_holm"] = float(a)
        r["qualified"] = bool(a < 0.05 and r["years_same_sign"] >= 4 and r["size_ok"]
                              and (r["two_sided"] or r["effect_per_session"] > 0))
    # descriptive account view of each day-type rule on the design years (not a criterion)
    for r in rows:
        if r["hypothesis"] == "E3":
            continue
        spec = hypotheses(mkt, F, dates)[r["hypothesis"]]
        flag = spec[1] if r["effect_per_session"] > 0 else ~spec[1]
        m = valid0 & (spec[3] if len(spec) > 3 else True)
        dp_rule = np.where(flag, pnl, 0.0)[m]
        dl_rule = np.where(flag, canon["low"], 0.0)[m]
        r["design_account_1mnq"] = {
            "rule": G.day_profile(dp_rule, flag[m]),
            "every_day": G.day_profile(pnl[m], traded[m]),
            "rule_life": G.funded_life_policy(dp_rule, dl_rule, paths=4000, buffer=1000.0),
            "every_day_life": G.funded_life_policy(pnl[m], canon["low"][m], paths=4000, buffer=1000.0)}
    return {"design_years": list(DESIGN_YEARS), "hypotheses": rows,
            "qualified": [r["hypothesis"] for r in rows if r["qualified"]]}


def look_stats(pnl, low, ntr, flag, seed=13):
    """Single-look criteria on one period. `flag` is already oriented so that the design effect
    is positive (rule = trade the canonical strategy only on flagged days)."""
    rule = np.where(flag, pnl, 0.0)
    d = rule - pnl
    idx = G.boot_idx(len(d), N_PERM, len(d), seed)
    bm = d[idx].mean(axis=1)
    p = float((np.sum(bm <= 0) + 1) / (N_PERM + 1))
    t = flag & (ntr > 0)
    res = {"sessions": int(len(pnl)), "flagged": int(flag.sum()), "mean_rule": float(rule.mean()),
           "mean_every_day": float(pnl.mean()), "p_boot_one_sided": p,
           "mean_per_traded_day": float(rule[t].mean()) if t.any() else None}
    acct, better = {}, True
    for k in (1, 3):
        a = G.funded_life_policy(rule * k, np.where(flag, low, 0.0) * k, paths=4000, buffer=1000.0)
        b = G.funded_life_policy(pnl * k, low * k, paths=4000, buffer=1000.0)
        acct[k] = {"rule": a, "every_day": b}
        better &= a["owner_per_month"] > b["owner_per_month"] and a["p_survive"] >= b["p_survive"]
    res["account"] = acct
    # effect on the oriented flag: must stay positive, i.e. keep the design direction
    res["effect_per_session"] = (float(pnl[flag].mean() - pnl[~flag].mean())
                                 if flag.any() and (~flag).any() else None)
    res["success"] = bool(p < 0.05 and (res["mean_per_traded_day"] or 0) > 0 and better
                          and (res["effect_per_session"] or 0) > 0)
    return res


def single_look(design, seed=13):
    """The one 2025-2026 evaluation, only for qualified hypotheses."""
    qual = design["qualified"]
    if not qual:
        return {"run": False, "reason": "no hypothesis qualified on 2020-2024; 2025-2026 not touched"}
    mkt, dates, F = R.market("nq20")
    canon, lab, _ = _base(mkt, F, dates)
    m0 = (F[:, X.VALID] > 0) & (dates >= LOOK[0]) & (dates <= LOOK[1])
    hyp = hypotheses(mkt, F, dates)
    out = {"run": True, "results": {}}
    for name in qual:
        row = next(r for r in design["hypotheses"] if r["hypothesis"] == name)
        spec = hyp[name]
        m = m0 & (spec[3] if len(spec) > 3 else True)          # X1: sessions with SPY data only
        if m.sum() < 20:
            out["results"][name] = {"evaluable": False, "sessions": int(m.sum())}
            continue
        flag = spec[1] if row["effect_per_session"] > 0 else ~spec[1]
        out["results"][name] = {"evaluable": True,
                                **look_stats(canon["pnl"][m], canon["low"][m], canon["ntr"][m], flag[m], seed)}
    return out
