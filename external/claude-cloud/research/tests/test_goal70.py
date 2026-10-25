"""Account-goal tools (goal70) and the pre-registered test helpers (lx_prereg)."""
from dataclasses import replace

import numpy as np

from factory import goal70 as G
from factory import lx_prereg as P
from factory.lucid import run_funded


def _paths(seed=0, paths=500, T=126):
    rng = np.random.default_rng(seed)
    pnl = rng.normal(40, 220, (paths, T))
    low = np.minimum(pnl, 0) - np.abs(rng.normal(0, 60, (paths, T)))
    return pnl, low


def test_funded_sim_buffer0_matches_fleet_engine():
    pnl, low = _paths()
    rules = replace(G.RULES, funded_sessions=pnl.shape[1])
    owner_ref, _, pays_ref = run_funded(pnl, rules, low=low)
    owner, alive, pays, first = G.funded_sim(pnl, low, rules=rules, buffer=0.0)
    assert np.allclose(owner, owner_ref)
    assert (pays == pays_ref).all()
    assert (alive == G._alive(pnl, low, rules)).all()
    assert ((first >= 0) == (pays > 0)).all()


def test_buffer_keeps_balance_above_locked_floor_plus_buffer():
    pnl = np.full((1, 60), 300.0)                   # steady winner: every day qualifies
    low = np.zeros_like(pnl)
    owner, alive, pays, first = G.funded_sim(pnl, low, buffer=1000.0)
    assert alive.all() and pays[0] > 0
    # the first payout cannot happen before profit covers lock offset + buffer + $500 minimum
    assert first[0] + 1 >= int(np.ceil((G.RULES.lock_offset + 1000.0 + 500.0) / 300.0))


def test_day_profile_counts():
    dp = np.array([150, -50, 120, 0, -200, 99, 100], float)
    pr = G.day_profile(dp)
    assert pr["hit_rate_all"] == 3 / 7
    assert pr["losing_streak_max"] == 1
    assert pr["miss_streak_max"] == 3
    assert pr["worst_day"] == -200
    el = np.array([1, 1, 1, 0, 0, 0, 1], bool)
    assert G.day_profile(dp, el)["hit_rate_eligible"] == 3 / 4


def test_holm_matches_definition():
    ps = np.array([0.01, 0.04, 0.03, 0.5])
    adj = P._holm(ps)
    assert np.allclose(adj, [0.04, 0.09, 0.09, 0.5])


def test_perm_test_detects_planted_effect_and_not_noise():
    rng = np.random.default_rng(1)
    n = 1250
    years = np.repeat(np.arange(2020, 2025), n // 5)
    flag = rng.random(n) < 0.1
    valid = np.ones(n, bool)
    noise = rng.normal(0, 100, n)
    P.N_PERM, keep = 2000, P.N_PERM
    try:
        obs, p, per = P._perm_test(noise + 60 * flag, flag, years, valid, False, rng)
        assert p < 0.01 and obs > 30 and len(per) == 5
        obs, p, _ = P._perm_test(noise, flag, years, valid, True, rng)
        assert p > 0.01
    finally:
        P.N_PERM = keep


def test_single_look_refuses_without_qualified_hypothesis():
    out = P.single_look({"qualified": [], "hypotheses": []})
    assert out["run"] is False


def test_two_point_has_exact_hit_rate():
    for p in (0.6, 0.7, 0.8):
        dp, dl = G.two_point(p, 125.0, 150.0)
        assert np.mean(dp > 0) == p
        assert (dl[dp > 0] == 0).all() and (dl[dp < 0] == -150.0).all()


def test_best_mark_path_only_changes_marks():
    from tests.test_lx import _frame, _market
    from factory import lx_engine as LE
    from factory import lx_features as LF
    from factory import lx_newinfo as N
    _, mkt = _market(_frame(days=60, seed=4))
    mask = mkt[4][:, LF.VALID] > 0
    w = LE.run("noise", mkt, N.CANON_NOISE, mask, want_path=True)
    b = LE.run("noise", mkt, N.CANON_NOISE, mask, want_path=True, mark="best")
    assert np.array_equal(w["pnl"], b["pnl"]) and np.array_equal(w["low"], b["low"])
    assert np.array_equal(w["ntr"], b["ntr"])
    assert (b["path"] >= w["path"] - 1e-9).all()
    assert w["ntr"].sum() > 0 and (b["path"] > w["path"] + 1e-9).any()


def test_look_stats_oriented_flag_negative_design_effect():
    """E2-style case: design effect negative, so the rule trades NON-flag days (flag flipped).
    A look period that keeps the design direction must pass the same-direction check."""
    rng = np.random.default_rng(3)
    n = 450
    fomc = rng.random(n) < 0.04
    pnl = rng.normal(40, 120, n) - 600 * fomc                 # FOMC days much worse, as in design
    low = np.minimum(pnl, 0) - 20
    ntr = np.ones(n, int)
    keep = P.N_PERM
    P.N_PERM = 2000
    try:
        res = P.look_stats(pnl, low, ntr, ~fomc)               # oriented flag = non-FOMC days
    finally:
        P.N_PERM = keep
    assert res["effect_per_session"] > 0
    assert res["p_boot_one_sided"] < 0.05 and res["mean_per_traded_day"] > 0


def test_round2_prior_close_is_strictly_before_session():
    import pandas as pd
    from factory import lx_prereg2 as P2
    s = pd.Series([1.0, 2.0, 3.0], index=pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-05"]))
    d = np.array(["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-08"], dtype="datetime64[ns]")
    out = P2._prior_close(s, d)
    assert np.isnan(out[0]) and out[1] == 1.0 and out[2] == 2.0 and out[3] == 3.0


def test_forward_criteria_on_synthetic_days():
    from factory import forward as FW
    keep = FW.N_DRAWS
    FW.N_DRAWS = 2000
    try:
        good = np.where(np.arange(60) % 10 < 8, 150.0, -100.0)        # 80% at +150, worst -100
        r = FW.e_goal(good, np.minimum(good, 0), np.ones(60, bool), weeks=12)
        assert r["pass"] and r["p_zero_edge"] < 0.05 and r["funded_sim_alive"]
        bad = good.copy()
        bad[5] = -400.0                                                 # one day worse than -150
        assert not FW.e_goal(bad, np.minimum(bad, 0), np.ones(60, bool), weeks=12)["pass"]
        rng = np.random.default_rng(0)
        x = rng.normal(20, 300, 250)
        imp = FW.e_improve(x * 1.0, np.minimum(x, 0), x, np.minimum(x, 0))
        assert imp["p_boot"] > 0.4                                       # identical series: no improvement
    finally:
        FW.N_DRAWS = keep


def test_forward_run_reports_no_sessions_yet():
    from factory import forward as FW
    out = FW.run()
    assert out["forward_sessions"] == 0 and out["status"] == "no forward sessions yet"
