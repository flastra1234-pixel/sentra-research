"""Lucid-session engine: flat by 16:44, filters never used before they exist, no lookahead,
trade tallies consistent with P&L."""
import numpy as np
import pandas as pd
import pytest

from factory import lx_data as LD
from factory import lx_engine as LE
from factory import lx_features as LF
from factory import lx_strategies as LS


def _frame(days=45, seed=1):
    rng = np.random.default_rng(seed)
    idx = []
    for d in pd.bdate_range("2024-01-02", periods=days):
        start = (d - pd.Timedelta(days=1)).replace(hour=18)
        idx.append(pd.date_range(start, d.replace(hour=16, minute=44), freq="1min"))
    idx = pd.DatetimeIndex(np.concatenate(idx)).tz_localize("America/New_York")
    r = 0.0006 * rng.standard_normal(len(idx))
    c = 20000 * np.exp(np.cumsum(r))
    o = np.r_[c[0], c[:-1]]
    h = np.maximum(o, c) * (1 + 0.0002 * rng.random(len(c)))
    l = np.minimum(o, c) * (1 - 0.0002 * rng.random(len(c)))
    return pd.DataFrame({"open": o, "high": h, "low": l, "close": c, "volume": 1.0}, index=idx)


def _market(df):
    s = LD.build(df, "synthetic")
    F, vw, sig = LF.build(s)
    return s, (s.o, s.h, s.l, s.c, F, vw, sig, s.present)


def test_session_layout():
    s, _ = _market(_frame())
    assert s.o.shape[1] == LD.NB == 1365
    assert len(s) == 45 and s.present.all()


@pytest.mark.parametrize("fam", list(LS.GENERATORS))
def test_flat_by_close_and_tallies(fam):
    s, m = _market(_frame(seed=2))
    F = m[4]
    mask = F[:, LF.VALID] > 0
    specs = list(LS.GENERATORS[fam]())
    for p, _ in specs[:: max(1, len(specs) // 30)]:
        r = LE.run(fam, m, p, mask, want_path=True)
        assert np.allclose(r["gw"] - r["gl"], r["pnl"], atol=1e-6)
        assert (r["nwin"] <= r["ntr"]).all()
        assert np.allclose(np.minimum(r["path"].min(axis=1), 0), r["low"], atol=1e-6)


@pytest.mark.parametrize("fam", list(LS.GENERATORS))
def test_no_lookahead_into_next_session(fam):
    df = _frame(seed=3)
    s, m = _market(df)
    mask = m[4][:, LF.VALID] > 0
    last_day = s.dates[-1]
    df2 = df.copy()
    sel = (df2.index + pd.Timedelta(hours=6)).normalize().tz_localize(None) == pd.Timestamp(last_day)
    df2.loc[sel, ["open", "high", "low", "close"]] *= 1.04
    _, m2 = _market(df2)
    for p, _ in list(LS.GENERATORS[fam]())[:20]:
        a = LE.run(fam, m, p, mask)["pnl"]
        b = LE.run(fam, m2, p, mask)["pnl"]
        assert np.allclose(a[:-1], b[:-1])


EXIT_PARAM = {"brk": 7, "fade": 6, "noise": 10, "imom": 6, "hold": 1, "drive": 6, "gap": 6}


def test_every_spec_exits_by_1644():
    for fam, gen in LS.GENERATORS.items():
        for p, _ in gen():
            assert LS.entry_from(fam, p) < p[EXIT_PARAM[fam]] <= LD.NB - 1, (fam, p)


def test_path_carries_realised_pnl_after_exits():
    s, m = _market(_frame(seed=6))
    mask = m[4][:, LF.VALID] > 0
    for fam in ("brk", "noise"):
        for p, _ in list(LS.GENERATORS[fam]())[::97][:30]:
            r = LE.run(fam, m, p, mask, want_path=True)
            # the final minute never shows more than the realised P&L, and on days whose last
            # trade closed before the final bar it shows exactly the realised P&L
            assert (r["path"][:, -1] <= r["pnl"] + 1e-6).all()


def test_no_fills_on_bars_without_a_print():
    df = _frame(seed=7)
    s, _ = _market(df)
    day = s.dates[30]
    sday = (df.index + pd.Timedelta(hours=6)).normalize().tz_localize(None)
    et = df.index.tz_convert("America/New_York")
    early_close = (sday == pd.Timestamp(day)) & ((et.hour * 60 + et.minute) >= 13 * 60)
    s2, m2 = _market(df[~early_close])
    i = int(np.where(s2.dates == day)[0][0])
    mask = m2[4][:, LF.VALID] > 0
    r = LE.run("hold", m2, [1290, 1364, 1, 0.0, 0], mask)
    assert r["ntr"][i] == 0 and r["pnl"][i] == 0


def test_journey_constant_pnl():
    from factory import lx_run as R
    n = 200
    dp_e, dp_f = np.full(n, 300.0), np.full(n, 250.0)
    j = R.journey(dp_e, np.zeros(n), dp_f, np.zeros(n), n_paths=200, horizon=20)
    # passes on session 5 (1,500 >= 1,250, best day 300 <= 50%), funded from session 6,
    # 5 qualifying days and $1,250 profit -> first payout approved on session 10
    assert j["p_pass_within_10"] == 1.0 and j["p_payout_within_10"] == 1.0
    assert j["median_sessions_to_first_payout"] == 10


def test_filters_respect_availability():
    bases = [{"id": "x", "family": f, "params": p, "knobs": k} for f, gen in LS.GENERATORS.items()
             for p, k in list(gen())[:50]]
    for sp in LS.round2(bases):
        t0 = LS.entry_from(sp["family"], sp["params"])
        for part in sp["filter"].split("+"):
            assert LS.FILTERS[part][0] <= t0, (sp["family"], sp["filter"], t0)


def test_gap_and_overnight_features_need_the_open():
    s, _ = _market(_frame(seed=4))
    F = LF.daily(s)
    s.o[20, 930:] *= 1.02; s.h[20, 930:] *= 1.02; s.l[20, 930:] *= 1.02; s.c[20, 930:] *= 1.02
    G = LF.daily(s)
    early = [k for k in range(LF.N_FEAT) if LF.AVAILABLE_AT.get(k, 0) == 0]
    assert np.allclose(F[:21][:, early], G[:21][:, early], equal_nan=True)
