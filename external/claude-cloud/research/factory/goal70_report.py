"""Reproduces every table of research/RESULTS_goal70.md and writes research/results/goal70.json.

    cd research && PYTHONPATH=. python3 -m factory.goal70_report [section ...]

Sections: feasibility, existing, overlays, walkforward, diagnostics, newinfo, canonical, scorecard,
prereg, prereg2.
Strategy selection and every tuned threshold use 2020-2024 only. 2025-2026 appears only in the
explanatory market-structure diagnostics, in the descriptive scorecard rows for the 2025 and 2026
walk-forward folds (already reported in RESULTS_2020plus.md; nothing is chosen from them) and, if
a hypothesis qualifies, in the single pre-registered looks (lx_prereg, lx_prereg2)."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from . import goal70 as G
from . import lx_diag as Dg
from . import lx_features as X
from . import lx_newinfo as N
from . import lx_run as R

OUT = Path(__file__).resolve().parents[1] / "results" / "goal70.json"
DATA = Path("/home/user/sentra-data")


def _records(df):
    return json.loads(df.to_json(orient="records"))


def feasibility():
    req = pd.DataFrame(G.required_table())
    rows = []
    for (p, w, l) in [(0.7, 125, 100), (0.7, 125, 150), (0.7, 125, 200), (0.7, 150, 150),
                      (0.7, 150, 200), (0.6, 150, 100), (0.8, 125, 200)]:
        dp, dl = G.two_point(p, w, l)
        for b in (0, 500, 1000, 1500, 2000, 3000):
            rows.append({"p_hit": p, "win": w, "loss": l, "mean": p * w - (1 - p) * l,
                         **G.funded_life_policy(dp, dl, buffer=b, paths=4000)})
    return {"required_profile": _records(req), "buffer_policy": rows}


def existing():
    from . import lx_walkforward as W
    meta, dates, arr = W._full("nq20_r1")
    design = dates < np.datetime64("2025-01-01")
    pnl = arr["pnl"].astype(np.float32)[:, design]
    traded = arr["ntr"][:, design] > 0
    nt = traded.sum(axis=1)
    rows, top = [], {}
    for m in (1, 2, 3, 4, 5, 6, 8, 10):
        P = pnl * m
        hit = ((P >= 100) & traded).sum(axis=1) / np.maximum(nt, 1)
        mean_all = P.mean(axis=1)
        ok = nt >= 150
        for thr in (0.5, 0.6, 0.7):
            sel = ok & (hit >= thr)
            rows.append({"micros": m, "hit_rate_ge": thr, "n_specs": int(sel.sum()),
                         "n_mean_ge_48": int((sel & (mean_all >= 48)).sum()),
                         "n_mean_gt_0": int((sel & (mean_all > 0)).sum()),
                         "best_mean_per_session": float(mean_all[sel].max()) if sel.any() else None})
        if m in (2, 4, 6):
            cand = np.where(ok & (mean_all > 0))[0]
            best = cand[np.argsort(-hit[cand])[:5]]
            top[m] = [{"hit": float(hit[i]), "traded": int(nt[i]), "share": float(nt[i] / design.sum()),
                       "mean_per_session": float(mean_all[i]), "family": meta[i]["family"],
                       "knobs": meta[i]["knobs"]} for i in best]
    # round-2 variants (round-1 specs x ex-ante day filters): open file = 2020-2024 sessions only
    o2 = R.load_open("nq20_r2")
    d2 = np.asarray(o2["dates"]).astype("datetime64[D]") < np.datetime64("2025-01-01")
    p2 = o2["pnl"][:, d2].astype(np.float32)
    t2 = o2["ntr"][:, d2] > 0
    n2 = t2.sum(axis=1)
    r2 = []
    for m in (2, 4, 6, 10):
        hit = ((p2 * m >= 100) & t2).sum(axis=1) / np.maximum(n2, 1)
        sel = (n2 >= 150) & (hit >= 0.7)
        r2.append({"micros": m, "n_specs_hit_ge_70_traded150": int(sel.sum()),
                   "max_hit_traded50": float(hit[n2 >= 50].max()),
                   "max_hit_all_sessions": float(((p2 * m >= 100)).mean(axis=1).max())})
    return {"n_specs": int(pnl.shape[0]), "design_sessions": int(design.sum()), "hit_vs_mean": rows,
            "top_hit_positive_mean": top, "round2_specs": int(p2.shape[0]), "round2_screen": r2}


def overlays():
    mkt, dates, F = R.market("nq20")
    fl = json.load(open(DATA / "lx_fleet2_nq20.json"))
    pm = R.period_masks("nq20")
    design = pm["discovery"] | pm["validation"]
    out = {}
    for ph in ("funded", "eval"):
        f = fl[ph]
        P, dpr, _, _ = R.fleet_paths(f["sleeves"], mkt, F, design)
        rows = G.lock_stop_frontier(P, dpr, f["micros"])
        # zero-edge: each day's trades reversed at random. A reversed day's worst-mark path is
        # minus the favourable-extreme path of the real trades (negating the worst-mark path
        # would hand the flipped days best marks and an optimistic lock / stop order)
        Pb = R.fleet_paths(f["sleeves"], mkt, F, design, mark="best")[0]
        rng = np.random.default_rng(5)
        flip = rng.random(len(dpr)) < 0.5
        Pz = np.where(flip[:, None], -Pb, P)
        zero = G.lock_stop_frontier(Pz, np.where(flip, -dpr, dpr), f["micros"], locks=(100.0, 125.0),
                                    stops=(150.0, 233.0, 300.0))
        out[ph] = {"micros": f["micros"], "frontier": rows, "zero_edge": zero}
    return out


def walkforward():
    mkt, dates, F = R.market("nq20")
    wf = json.load(open(DATA / "lx_walkforward_nq20.json"))
    buf, size = [], []
    for f in wf:
        y = f["year"]
        if y > 2024:
            continue                                       # design-period OOS years only
        test = ((dates >= np.datetime64(f"{y}-01-01")) & (dates <= np.datetime64(f"{y}-12-31"))
                & (F[:, X.VALID] > 0))
        for ph in ("funded", "eval"):
            fl = f["fleets"][ph]
            sleeves = [dict(s, id=str(i)) for i, s in enumerate(fl["sleeves"])]
            P, dpr, _, _ = R.fleet_paths(sleeves, mkt, F, test)
            micros = sum(s["micros"] for s in sleeves)
            if ph == "funded":
                dp, dl = R.overlay(P, dpr, None, fl["lock"], micros)
                prof = G.day_profile(dp)
                for b in (0, 500, 1000, 1500, 2000):
                    life = G.funded_life_policy(dp, dl, months=12, paths=6000, buffer=b)
                    buf.append({"oos_year": y, "buffer": b, "mean_day": prof["mean_day"],
                                "hit_rate": prof["hit_rate_all"], "losing_streak_max": prof["losing_streak_max"],
                                **life})
            dp0, dl0 = R.overlay(P, dpr, None, None, micros)
            for k in (0.1, 0.2, 0.3, 0.5, 0.75, 1.0):
                dp, dl = dp0 * k, dl0 * k
                prof = G.day_profile(dp)
                life = G.funded_life_policy(dp, dl, months=12, paths=6000, buffer=1000)
                size.append({"oos_year": y, "fleet": ph, "size_x": k, "approx_micros": round(micros * k, 1),
                             "mean_day": prof["mean_day"], "sd_day": float(dp.std()),
                             "hit_ge_100": prof["hit_rate_all"], "losing_streak_max": prof["losing_streak_max"],
                             "p_survive_12m": life["p_survive"], "owner_per_month": life["owner_per_month"],
                             "median_first_payout_session": life["median_first_payout_session"]})
    return {"buffer": buf, "size_frontier": size}


def diagnostics():
    from . import lx_walkforward as W
    mkt, dates, F = R.market("nq20")
    valid = F[:, X.VALID] > 0
    full = Dg.per_session(mkt, F)
    o, h, l, c = mkt[:4]
    hi_t = np.argmax(h[:, 930:1320], axis=1) + 930
    lo_t = np.argmin(l[:, 930:1320], axis=1) + 930
    full["late_extreme"] = np.maximum(hi_t, lo_t) >= 1200          # high or low set after 14:00
    prev = F[:, X.RTH_PREV_CLOSE]
    on, dy = np.abs(o[:, 930] / prev - 1), np.abs(c[:, 1319] / o[:, 930] - 1)
    full["overnight_share"] = on / (on + dy + 1e-12)
    rng = h[:, 930:1320].max(1) - l[:, 930:1320].min(1)
    full["post10_share"] = np.abs(c[:, 1319] - c[:, 959]) / rng
    df, d = full[valid], dates[valid]
    yearly = Dg.summarise(df.drop(columns=["late_extreme", "overnight_share", "post10_share"]), d, "Y")
    g = df.groupby(pd.DatetimeIndex(d).year)
    extra = pd.DataFrame({"late_extreme_%": g["late_extreme"].mean() * 100,
                          "overnight_share": g["overnight_share"].mean(),
                          "post10_move_over_range": g["post10_share"].mean()})
    extra.index = extra.index.astype(str)                          # summarise() keys periods as "2020"
    # family P&L on trend vs other days (median over all variants, 1 micro)
    meta, sdates, arr = W._full("nq20_r1")
    pos = np.searchsorted(dates, sdates)
    trend = full["trend_day"].to_numpy()[pos]
    years = pd.DatetimeIndex(sdates).year
    fam = np.array([m["family"] for m in meta])
    win = np.array([m["knobs"].get("window", "") for m in meta])
    pnl = arr["pnl"].astype(np.float64)
    decomp = {}
    for gname, msk in (("noise", fam == "noise"), ("cash_open_orb", (fam == "brk") & (win == "orb")),
                       ("gap", fam == "gap")):
        rows = {}
        for y in range(2020, 2027):
            cy = years == y
            P, t = pnl[msk][:, cy], trend[cy]
            tm, om = P[:, t].mean(axis=1), P[:, ~t].mean(axis=1)
            share = t.mean()
            rows[int(y)] = {"sessions": int(cy.sum()), "trend_share": float(share),
                            "median_per_trend_day": float(np.median(tm)), "median_per_other_day": float(np.median(om)),
                            "median_per_session": float(np.median(P.mean(axis=1))),
                            # trend share at which the median variant breaks even
                            "breakeven_trend_share": float(-np.median(om) / (np.median(tm) - np.median(om)))
                            if np.median(tm) > np.median(om) else None}
        decomp[gname] = rows
    def split(base, new):
        """P = s*T + (1-s)*O; share / trend-day / other-day effects of base -> new, both orders
        (base values first, new values first) and their average (Shapley for this form)."""
        s0, T0, O0 = base
        s1, T1, O1 = new
        total = (s1 * T1 + (1 - s1) * O1) - (s0 * T0 + (1 - s0) * O0)
        a = {"share": (s1 - s0) * (T0 - O0), "trend_day": s1 * (T1 - T0), "other_day": (1 - s1) * (O1 - O0)}
        b = {"share": (s1 - s0) * (T1 - O1), "trend_day": s0 * (T1 - T0), "other_day": (1 - s0) * (O1 - O0)}
        return {"total": total, **{k: {"base_first": a[k], "new_first": b[k], "avg": (a[k] + b[k]) / 2}
                                   for k in a}}
    nz = decomp["noise"]
    def triple(ys):
        return tuple(np.mean([nz[y][k] for y in ys]) for k in ("trend_share", "median_per_trend_day",
                                                                "median_per_other_day"))
    base_avg, base_24 = triple(range(2020, 2025)), triple([2024])
    decomp_split = {f"{y}_vs_{nm}": split(b0, triple([y])) for y in (2025, 2026)
                    for nm, b0 in (("2020_24_avg", base_avg), ("2024", base_24))}
    # vol regime vs trend frequency (monthly)
    vx = pd.read_csv(DATA / "raw/ext/vix/vix_daily.csv", parse_dates=["date"]).set_index("date")
    vx["term_9d_30d"] = vx["VIX9D"] / vx["VIX"]
    vx["term_30d_3m"] = vx["VIX"] / vx["VIX3M"]
    m = df.set_index(pd.DatetimeIndex(d)).resample("ME").agg({"trend_day": "mean", "eff": "mean", "vr30": "mean"})
    j = m.join(vx.resample("ME").mean(), how="inner").dropna()
    corr = j.corr(method="spearman").loc[["trend_day", "eff", "vr30"],
                                         ["VIX", "VXN", "VVIX", "term_9d_30d", "term_30d_3m"]]
    # 30-minute return autocorrelation, design period, direct (no variance-ratio estimator)
    px = np.c_[o[:, 930], c[:, 959:1320:30]]                        # 09:30 open, then 10:00 .. 16:00
    r30 = np.diff(np.log(px), axis=1)
    des = valid & (pd.DatetimeIndex(dates).year <= 2024)
    a, b = r30[des, :-1].ravel(), r30[des, 1:].ravel()
    rho30 = float(np.corrcoef(a, b)[0, 1])
    return {"yearly": json.loads(pd.concat([yearly, extra], axis=1).to_json(orient="index")),
            "trend_decomposition": decomp, "noise_change_split": decomp_split,
            "vix_vs_trend_spearman_monthly": json.loads(corr.to_json()), "months": int(len(j)),
            "rho_30min_consecutive_design": rho30, "rho_30min_n": int(len(a))}


def newinfo():
    mkt, dates, F = R.market("nq20")
    feats, lab = N.build(mkt, F, dates)
    years = pd.DatetimeIndex(dates).year.to_numpy()
    nq_cols = [c for c in feats.columns if not c.startswith("ev_")]   # event flags go to lx_prereg
    feats = feats[nq_cols]
    ok = (F[:, X.VALID] > 0) & feats.notna().all(axis=1).to_numpy() & (years <= 2024)
    fv, lv, yv = feats[ok].reset_index(drop=True), lab[ok].reset_index(drop=True), years[ok]
    s_trend = N.feature_scan(fv, lv["trend_rest"].to_numpy(), yv, n_perm=1000)
    t = lv["canon_traded"].to_numpy()
    s_prof = N.feature_scan(fv[t].reset_index(drop=True), (lv["canon_pnl"] > 0).to_numpy()[t], yv[t], n_perm=1000)
    # the two fixed filter rules, 2021-2024
    valid = F[:, X.VALID] > 0
    pnl = np.where(valid, lab["canon_pnl"].to_numpy(), 0.0)
    traded = lab["canon_traded"].to_numpy() & valid
    allf = N.build(mkt, F, dates)[0]
    mom = allf["canon_pnl20"].to_numpy() > 0
    vixup = allf["vix_chg_prev"].to_numpy() > 0
    rules = {"R0 every day": np.ones(len(pnl), bool), "R1 trailing20>0": mom, "R2 VIX rose prior day": vixup,
             "R1&R2": mom & vixup}
    rr = []
    for y in list(range(2021, 2025)) + ["2021-24"]:
        cy = (((years >= 2021) & (years <= 2024)) if y == "2021-24" else (years == y)) & valid
        for name, allow in rules.items():
            p = np.where(allow, pnl, 0.0)[cy]
            tt = (allow & traded)[cy]
            sd = p.std(ddof=1)
            rr.append({"year": str(y), "rule": name, "days_traded": int(tt.sum()), "mean_per_session": float(p.mean()),
                       "sharpe": float(p.mean() / sd * np.sqrt(252)) if sd > 0 else 0.0,
                       "mean_per_traded": float(p[tt].mean()) if tt.any() else None,
                       "win_pct_traded": float(np.mean(p[tt] > 0) * 100) if tt.any() else None})
    return {"design_sessions": int(ok.sum()), "base_trend_rest": float(lv["trend_rest"].mean()),
            "base_profit_given_traded": float((lv["canon_pnl"] > 0).to_numpy()[t].mean()),
            "scan_trend_rest": _records(s_trend), "scan_profit_given_traded": _records(s_prof), "rules": rr}


def canonical():
    """The published noise-area momentum spec on its own, 2020-2024, at several sizes."""
    from . import lx_engine as LE
    mkt, dates, F = R.market("nq20")
    years = pd.DatetimeIndex(dates).year
    m = (F[:, X.VALID] > 0) & (years <= 2024)
    r = LE.run("noise", mkt, N.CANON_NOISE, F[:, X.VALID] > 0)
    dp1, dl1, tr = r["pnl"][m], r["low"][m], r["ntr"][m] > 0
    rows = []
    for k in (1, 2, 3, 4, 6, 8):
        prof = G.day_profile(dp1 * k, tr)
        life = G.funded_life_policy(dp1 * k, dl1 * k, paths=6000, buffer=1000.0)
        rows.append({"micros": k, **{q: prof[q] for q in ("hit_rate_all", "hit_rate_eligible", "eligible_share",
                     "mean_day", "worst_day", "losing_streak_max", "max_drawdown", "sharpe_ann")}, **life})
    return {"sessions": int(m.sum()), "rows": rows}


def scorecard():
    """Complete account economics for the realistic candidates: walk-forward fleets traded blind
    in 2023-2026 (full size and cut to about 1 micro) and the canonical strategy (2020-2024,
    1 micro). Daily profile, then buy an evaluation, pass it, trade funded for up to 12 months
    (lx_run.journey: standard payout policy, a breach ends the account, no reset)."""
    from . import lx_engine as LE
    mkt, dates, F = R.market("nq20")
    wf = json.load(open(DATA / "lx_walkforward_nq20.json"))
    from dataclasses import replace as _replace
    rows = []
    c40 = _replace(G.RULES, consistency=0.40)
    def score(label, dpe, dle, dpf, dlf, elig=None):
        prof = G.day_profile(dpf, elig)
        j = R.journey(dpe, dle, dpf, dlf, n_paths=10000, horizon=252, seed=21)
        j40 = R.journey(dpe, dle, dpf, dlf, n_paths=10000, horizon=252, seed=21, rules=c40)
        life = G.funded_life_policy(dpf, dlf, months=12, paths=6000, buffer=0.0)
        rows.append({"candidate": label, "mean_day": prof["mean_day"], "hit_ge_100": prof["hit_rate_all"],
                     "hit_ge_100_eligible": prof["hit_rate_eligible"], "eligible_share": prof["eligible_share"],
                     "losing_streak_max_eligible": prof["losing_streak_max"],
                     "miss_streak_max_eligible": prof["miss_streak_max"],
                     "worst_day": prof["worst_day"], "max_drawdown": prof["max_drawdown"],
                     "p_pass_within_10": j["p_pass_within_10"], "p_payout_within_21": j["p_payout_within_21"],
                     "p_payout_within_42": j["p_payout_within_42"],
                     "median_sessions_to_first_payout_if_paid": j["median_sessions_to_first_payout"],
                     "funded_p_survive_12m": life["p_survive"], "funded_owner_per_month": life["owner_per_month"],
                     "owner_per_eval_12m": j["owner_mean_within_252"],
                     "net_per_eval_12m_fee_89_149": [j["owner_mean_within_252"] - 149.0, j["owner_mean_within_252"] - 89.0],
                     "consistency_40": {"p_pass_within_10": j40["p_pass_within_10"],
                                        "owner_per_eval_12m": j40["owner_mean_within_252"]}})
    for f in wf:
        # 2025-2026 folds were already reported in RESULTS_2020plus.md; they are scored here as
        # what a buyer would have experienced (descriptive), and nothing is selected from them
        y = f["year"]
        tag = "" if y <= 2024 else " [already examined, descriptive]"
        test = ((dates >= np.datetime64(f"{y}-01-01")) & (dates <= np.datetime64(f"{y}-12-31"))
                & (F[:, X.VALID] > 0))
        raw = {}
        for ph in ("eval", "funded"):
            fl = f["fleets"][ph]
            sleeves = [dict(s, id=str(i)) for i, s in enumerate(fl["sleeves"])]
            P, dpr, _, _ = R.fleet_paths(sleeves, mkt, F, test)
            raw[ph] = (P, dpr, sum(s["micros"] for s in sleeves), fl.get("stop"), fl.get("lock"))
        def at(ph, k):
            # each fleet with the daily stop / profit lock it was selected with (the eval fleets'
            # $600 lock keeps them inside the consistency rule), scaled with size
            P, dpr, mi, stop, lock = raw[ph]
            return R.overlay(P * k, dpr * k, stop * k if stop else None, lock * k if lock else None, mi * k)
        me, mf = raw["eval"][2], raw["funded"][2]
        score(f"walk-forward {y}, full size ({me} / {mf} micros){tag}", *at("eval", 1.0), *at("funded", 1.0))
        score(f"walk-forward {y}, cut to ~1 micro (fractional sizing){tag}", *at("eval", 1.0 / me),
              *at("funded", 1.0 / mf))
    years = pd.DatetimeIndex(dates).year
    m = (F[:, X.VALID] > 0) & (years <= 2024)
    r = LE.run("noise", mkt, N.CANON_NOISE, F[:, X.VALID] > 0)
    score("canonical noise-area momentum, 1 micro, 2020-2024", r["pnl"][m], r["low"][m], r["pnl"][m], r["low"][m],
          elig=r["ntr"][m] > 0)
    return {"rows": rows, "fee_assumption": [89, 149]}


def prereg():
    from . import lx_prereg as P
    design = P.design_tests()
    return {**design, "single_look": P.single_look(design)}


def prereg2():
    from . import lx_prereg2 as P2
    from . import lx_prereg as P1
    design = P2.design_tests()
    # post-hoc, in-sample illustration of the near-miss filters (chosen after seeing the
    # results, same 2020-2024 data): NOT evidence, only to show the scale against the goal
    mkt, dates, F = R.market("nq20")
    years = pd.DatetimeIndex(dates).year
    canon, _, _ = P1._base(mkt, F, dates)
    h = P2.hypotheses(mkt, F, dates)
    n1, n2, n3, okq = h["N1"][1], h["N2"][1], h["N3"][1], h["N2"][3]
    v = (F[:, X.VALID] > 0) & (years <= 2024)
    pnl, low, tr = canon["pnl"], canon["low"], canon["ntr"] > 0
    rows = []
    for name, allow, m in [("every day", np.ones(len(pnl), bool), v), ("N3 and not N1", n3 & ~n1, v),
                           ("every day (N2 sample)", np.ones(len(pnl), bool), v & okq),
                           ("N2 and N3 and not N1", n2 & n3 & ~n1, v & okq)]:
        for k in (1, 2, 3):
            dp, dl = np.where(allow, pnl, 0.0)[m] * k, np.where(allow, low, 0.0)[m] * k
            pr = G.day_profile(dp, (allow & tr)[m])
            life = G.funded_life_policy(dp, dl, paths=4000, buffer=1000.0)
            rows.append({"rule": name, "micros": k, "sessions": int(m.sum()),
                         "trade_share": float((allow & tr)[m].mean()), **{q: pr[q] for q in (
                             "mean_day", "hit_rate_eligible", "hit_rate_all", "sharpe_ann", "worst_day",
                             "losing_streak_max")}, **life})
    return {**design, "single_look": P2.single_look(design), "posthoc_insample_illustration": rows}


SECTIONS = {"feasibility": feasibility, "existing": existing, "overlays": overlays, "walkforward": walkforward,
            "diagnostics": diagnostics, "newinfo": newinfo, "canonical": canonical, "scorecard": scorecard,
            "prereg": prereg, "prereg2": prereg2}


def main(names):
    res = json.load(open(OUT)) if OUT.exists() else {}
    for n in names or list(SECTIONS):
        print("running", n, flush=True)
        res[n] = SECTIONS[n]()
        OUT.write_text(json.dumps(res, indent=1, default=float))
    print("wrote", OUT)


if __name__ == "__main__":
    main(sys.argv[1:])
