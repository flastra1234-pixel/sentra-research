"""Stage 5: the frozen fleet (fleet.json) meets data it has never seen, once.

  sealed   NAS100 CFD 2019-01 .. 2020-05 (includes the 2020 crash)
  nq2026   real NQ futures 2026-07 .. 2026-10 (sessions with 20+ days of history)

Sleeves are re-run with minute paths so the fleet's intraday low is exact. Reported:
sleeve and fleet statistics, LucidFlex bootstrap scores per period, every-start-date
historical replays of the evaluation, and the fleet-engine verdict."""
import json

import numpy as np

from . import data as D
from . import engine as E
from . import features as X
from . import strategies as S
from . import sweep as W
from .fleet import EVAL_SESSIONS, FUNDED_SESSIONS, RULES, bootstrap_idx, lucid_scores
from .lucid import deflated_sharpe, run_eval

from dataclasses import replace


def fleet_days(fleet, market, F, period_mask):
    k_pnl, k_low = [], []
    tot_pnl = np.zeros(len(F))
    tot_path = np.zeros((len(F), E.NB))
    for s in fleet["sleeves"]:
        mask = S.day_mask(F, s["filter"]) & period_mask
        pnl, low, ntr, path = E.run(s["family"], market, s["params"], mask, want_path=True)
        k_pnl.append(pnl)
        k_low.append(low)
        tot_pnl += s["micros"] * pnl
        tot_path += s["micros"] * path
    low = np.minimum(tot_path.min(axis=1), 0.0)
    return tot_pnl[period_mask], low[period_mask], np.array(k_pnl)[:, period_mask]


def stats(p, low=None):
    p = np.asarray(p, float)
    n = len(p)
    sd = p.std(ddof=1)
    s = p.mean() / sd if sd > 0 else 0.0
    cum = np.cumsum(p)
    dd = float((cum - np.maximum.accumulate(np.maximum(cum, 0))).min())
    out = {"sessions": n, "mean_day": float(p.mean()), "sd_day": float(sd),
           "sharpe_ann": float(s * np.sqrt(252)), "t": float(s * np.sqrt(n)),
           "se_daily_sharpe": float(np.sqrt((1 + s * s / 2) / n)), "daily_sharpe": float(s),
           "total": float(p.sum()), "max_dd": dd, "pct_up_days": float(np.mean(p > 0)),
           "worst_day": float(p.min()), "best_day": float(p.max())}
    if low is not None:
        out["worst_intraday"] = float(np.min(low))
    return out


def replays(pnl, low, rules=RULES, horizon=EVAL_SESSIONS):
    """Start an evaluation on every session; count pass / breach / still open at the end of data."""
    n = len(pnl)
    res = {"passed": 0, "breached": 0, "open": 0, "days_to_pass": []}
    for d in range(n):
        seg_p, seg_l = pnl[d:d + horizon], low[d:d + horizon]
        bal, high, mx = rules.start, rules.start, 0.0
        outcome = "open"
        for t in range(len(seg_p)):
            floor = min(high - rules.max_loss, rules.start + rules.lock_offset)
            if bal + seg_l[t] <= floor or bal + seg_p[t] <= floor:
                outcome = "breached"
                break
            bal += seg_p[t]
            high = max(high, bal)
            mx = max(mx, seg_p[t])
            prof = bal - rules.start
            if prof >= rules.target and mx <= rules.consistency * prof:
                outcome = "passed"
                res["days_to_pass"].append(t + 1)
                break
        res[outcome] += 1
    decided = res["passed"] + res["breached"]
    res["pass_rate_decided"] = res["passed"] / decided if decided else None
    res["median_days_to_pass"] = float(np.median(res["days_to_pass"])) if res["days_to_pass"] else None
    del res["days_to_pass"]
    res["starts"] = n
    return res


def lucid_block(pnl, low, seed):
    n = len(pnl)
    ie = bootstrap_idx(n, 20000, EVAL_SESSIONS, seed)
    iff = bootstrap_idx(n, 20000, FUNDED_SESSIONS, seed + 1)
    return {"c50": lucid_scores(pnl, low, ie, iff),
            "c40": lucid_scores(pnl, low, ie, iff, replace(RULES, consistency=0.40))}


def verdict(s_oos, se_oos, s_in, beats_best):
    if s_oos - 2 * se_oos > 0 and beats_best:
        return "confirmed"
    if s_oos < s_in - 2 * se_oos:
        return "contradicted"
    return "consistent"


def main():
    fleet = json.loads((D.DATA_DIR / "fleet.json").read_text())
    mk = W.markets()
    pm = W.period_masks()
    mkt, dates, F = mk["nas100"]
    out = {"fleet": {"stop": fleet["stop"], "sleeves": [
        {k: s[k] for k in ("micros", "id", "family", "filter", "knobs")} for s in fleet["sleeves"]]}}
    periods = {
        "in_sample_2008_2018": (mkt, F, pm["discovery"] | pm["validation"], dates),
        "sealed_2019_2020": (mkt, F, pm["sealed"], dates),
    }
    qm, qd, qF = mk["nq2026"]
    periods["nq_futures_2026"] = (qm, qF, qF[:, X.VALID] > 0, qd)
    s_in = None
    for name, (m, FF, mask, dd) in periods.items():
        pnl, low, ks = fleet_days(fleet, m, FF, mask)
        st = stats(pnl, low)
        block = {"dates": [str(dd[mask][0]), str(dd[mask][-1])], "fleet": st,
                 "sleeves": [stats(k) for k in ks]}
        block["lucid_bootstrap"] = lucid_block(pnl, low, 777)
        block["lucid_replays_c50"] = replays(pnl, low)
        block["lucid_replays_c40"] = replays(pnl, low, replace(RULES, consistency=0.40))
        yrs = dd[mask].astype("datetime64[Y]")
        block["by_year"] = {str(y): stats(pnl[yrs == y])["total"] for y in np.unique(yrs)}
        if name.startswith("in_sample"):
            s_in = st["daily_sharpe"]
        else:
            best_single = max(x["daily_sharpe"] for x in block["sleeves"])
            block["verdict"] = verdict(st["daily_sharpe"], st["se_daily_sharpe"], s_in,
                                       st["daily_sharpe"] > best_single)
            block["p_value_sharpe_gt_0"] = float(1 - deflated_sharpe(pnl, 1, 0.0)) if len(pnl) > 3 else None
        out[name] = block
    (D.DATA_DIR / "unseal.json").write_text(json.dumps(out, default=float, indent=1))
    return out


def funded_replays(pnl, low, rules, horizon):
    """Start a fresh funded account on every session with a full horizon ahead."""
    from .lucid import run_funded
    n = len(pnl) - horizon + 1
    if n <= 0:
        return None
    w = np.stack([pnl[d:d + horizon] for d in range(n)])
    wl = np.stack([low[d:d + horizon] for d in range(n)])
    owner, qd, payouts = run_funded(w, rules, low=wl)
    return {"starts": n, "owner_mean": float(owner.mean()), "owner_median": float(np.median(owner)),
            "p_owner_ge_1k": float(np.mean(owner >= 1000)), "payouts_mean": float(payouts.mean())}


def main_phased():
    """v1.1: separate evaluation and funded fleets (fleet_phased.json), same periods."""
    from .fleet import EVAL_LONG, FUNDED_LONG, RULES_PHASE
    from .lucid import run_funded
    ph = json.loads((D.DATA_DIR / "fleet_phased.json").read_text())
    mk = W.markets()
    pm = W.period_masks()
    mkt, dates, F = mk["nas100"]
    qm, qd, qF = mk["nq2026"]
    periods = {"in_sample_2008_2018": (mkt, F, pm["discovery"] | pm["validation"], dates),
               "sealed_2019_2020": (mkt, F, pm["sealed"], dates),
               "nq_futures_2026": (qm, qF, qF[:, X.VALID] > 0, qd)}
    out = {"eval_fleet": ph["eval"], "funded_fleet": ph["funded"]}
    for name, (m, FF, mask, dd) in periods.items():
        block = {"dates": [str(dd[mask][0]), str(dd[mask][-1])]}
        ep, el, eks = fleet_days(ph["eval"], m, FF, mask)
        fp, fl, fks = fleet_days(ph["funded"], m, FF, mask)
        block["eval_fleet"] = stats(ep, el)
        block["funded_fleet"] = stats(fp, fl)
        n = len(ep)
        ie = bootstrap_idx(n, 20000, EVAL_LONG, 4242)
        iff = bootstrap_idx(n, 20000, FUNDED_LONG, 4343)
        block["eval_pass_120_bootstrap"] = {
            "c50": float(run_eval(ep[ie], RULES_PHASE, low=el[ie]).mean()),
            "c40": float(run_eval(ep[ie], replace(RULES_PHASE, consistency=0.40), low=el[ie]).mean())}
        owner, qdays, pays = run_funded(fp[iff], RULES_PHASE, low=fl[iff])
        block["funded_63_bootstrap"] = {"owner_mean": float(owner.mean()),
                                        "p_owner_ge_1k": float(np.mean(owner >= 1000)),
                                        "payouts_mean": float(pays.mean())}
        block["eval_replays_c50"] = replays(ep, el, RULES_PHASE, EVAL_LONG)
        block["eval_replays_c40"] = replays(ep, el, replace(RULES_PHASE, consistency=0.40), EVAL_LONG)
        block["funded_replays"] = funded_replays(fp, fl, RULES_PHASE, FUNDED_LONG)
        block["eval_sleeves"] = [stats(k)["sharpe_ann"] for k in eks]
        block["funded_sleeves"] = [stats(k)["sharpe_ann"] for k in fks]
        out[name] = block
    (D.DATA_DIR / "unseal_phased.json").write_text(json.dumps(out, default=float, indent=1))
    return out


if __name__ == "__main__":
    import sys
    if "--phased" in sys.argv:
        o = main_phased()
        for name in ("in_sample_2008_2018", "sealed_2019_2020", "nq_futures_2026"):
            b = o[name]
            print("\n==", name, b["dates"])
            for k in ("eval_fleet", "funded_fleet"):
                print(" ", k, {kk: round(v, 3) if isinstance(v, float) else v for kk, v in b[k].items()
                               if kk in ("sessions", "mean_day", "sd_day", "sharpe_ann", "t", "max_dd", "worst_day", "worst_intraday")})
            for k in ("eval_pass_120_bootstrap", "funded_63_bootstrap", "eval_replays_c50", "eval_replays_c40", "funded_replays"):
                print(" ", k, b[k])
            print("  eval sleeves sharpe", [round(x, 2) for x in b["eval_sleeves"]])
            print("  funded sleeves sharpe", [round(x, 2) for x in b["funded_sleeves"]])
        raise SystemExit
    o = main()
    for name in ("in_sample_2008_2018", "sealed_2019_2020", "nq_futures_2026"):
        b = o[name]
        print("\n==", name, b["dates"])
        print(" fleet", {k: round(v, 3) if isinstance(v, float) else v for k, v in b["fleet"].items()})
        print(" by year", {k: round(v) for k, v in b["by_year"].items()})
        print(" lucid bootstrap", b["lucid_bootstrap"])
        print(" replays c50", b["lucid_replays_c50"])
        print(" replays c40", b["lucid_replays_c40"])
        for s, st in zip(o["fleet"]["sleeves"], b["sleeves"]):
            print("   ", s["family"], s["filter"], "sharpe", round(st["sharpe_ann"], 2), "total", round(st["total"]))
        if "verdict" in b:
            print(" VERDICT", b["verdict"], "p(Sharpe<=0)", b["p_value_sharpe_gt_0"])
