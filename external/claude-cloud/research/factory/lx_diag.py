"""Explanatory market-structure diagnostics by period (no strategy selection happens here).

Each statistic is computed per session from the Lucid-session arrays (cash session 09:30-16:00
= indices 930..1319) and summarised per year / half-year, to explain why intraday momentum and
opening-range breakouts worked in 2020-2024 and not in 2025-2026."""
import numpy as np
import pandas as pd

from . import lx_features as X

O, C30, C60, C1500, C1530, CL = 930, 959, 989, 1259, 1289, 1319


def per_session(mkt, F):
    o, h, l, c = mkt[:4]
    n = o.shape[0]
    rth_o, rth_c = o[:, O], c[:, CL]
    rh, rl = h[:, O:CL + 1].max(axis=1), l[:, O:CL + 1].min(axis=1)
    r1 = np.diff(np.log(c[:, O:CL + 1]), axis=1)                    # 1-minute log returns
    var1 = (r1 ** 2).mean(axis=1)
    def vr(k):
        # raw second moments (no per-session demeaning: subtracting each day's own mean would
        # strip out exactly the trend and bias the ratio toward "mean reversion"); numerator and
        # denominator over the same first m returns (the dropped last minutes are the busiest)
        m = r1.shape[1] // k * k
        rk = r1[:, :m].reshape(n, -1, k).sum(axis=2)
        return (rk ** 2).mean(axis=1) / (k * (r1[:, :m] ** 2).mean(axis=1))
    first30 = c[:, C30] / rth_o - 1
    rest = c[:, CL] / c[:, C30] - 1
    first60 = c[:, C60] / rth_o - 1
    rest60 = c[:, CL] / c[:, C60] - 1
    last30 = c[:, CL] / c[:, C1530] - 1
    on_plus = c[:, C30] / F[:, X.RTH_PREV_CLOSE] - 1               # overnight + first 30 min
    prev = F[:, X.RTH_PREV_CLOSE]
    overnight = rth_o / prev - 1
    day = rth_c / rth_o - 1
    eff = np.abs(np.log(rth_c / rth_o)) / np.abs(r1).sum(axis=1)
    trend_day = np.abs(rth_c - rth_o) >= 0.6 * (rh - rl)
    # 30-minute opening range: first break side, follow-through to the close
    orh, orl = h[:, O:C30 + 1].max(axis=1), l[:, O:C30 + 1].min(axis=1)
    orw = orh - orl
    after_h, after_l = h[:, C30 + 1:CL + 1], l[:, C30 + 1:CL + 1]
    up_t = np.where((after_h > orh[:, None]).any(axis=1), np.argmax(after_h > orh[:, None], axis=1), 10**6)
    dn_t = np.where((after_l < orl[:, None]).any(axis=1), np.argmax(after_l < orl[:, None], axis=1), 10**6)
    broke_up = up_t < dn_t
    broke = (up_t < 10**6) | (dn_t < 10**6)
    with np.errstate(divide="ignore", invalid="ignore"):
        follow = np.where(broke_up, (rth_c - orh) / orw, (orl - rth_c) / orw)   # in OR widths, + = continued
    both_sides = (up_t < 10**6) & (dn_t < 10**6)
    # gap fill
    gap_atr = F[:, X.GAP_ATR]
    filled = np.where(overnight > 0, rl <= prev, rh >= prev)
    atr = F[:, X.ATR14]
    return pd.DataFrame({
        "rv_rth": np.sqrt(var1 * 390), "range_rth": (rh - rl) / rth_o, "atr14": atr,
        "vr5": vr(5), "vr15": vr(15), "vr30": vr(30), "vr60": vr(60),
        "first30": first30, "rest": rest, "first60": first60, "rest60": rest60,
        "last30": last30, "on_plus_first30": on_plus, "overnight": overnight, "day": day,
        "eff": eff, "trend_day": trend_day, "or_broke": broke, "or_broke_up": broke_up,
        "or_follow": np.where(broke, follow, np.nan), "or_both_sides": both_sides,
        "gap_atr": gap_atr, "gap_filled": filled,
    })


def summarise(df, dates, freq="Y"):
    key = pd.PeriodIndex(pd.DatetimeIndex(dates), freq=freq).astype(str)
    g = df.assign(period=key).groupby("period")
    def corr(a, b):
        return g.apply(lambda x: np.corrcoef(x[a], x[b])[0, 1], include_groups=False)
    def agree(a, b):
        return g.apply(lambda x: float(np.mean(np.sign(x[a]) == np.sign(x[b]))), include_groups=False)
    out = pd.DataFrame({
        "sessions": g.size(),
        "rv_rth_%": g["rv_rth"].mean() * 100,
        "range_rth_%": g["range_rth"].mean() * 100,
        "vr15": g["vr15"].mean(), "vr30": g["vr30"].mean(), "vr60": g["vr60"].mean(),
        "eff_ratio": g["eff"].mean(),
        "trend_day_%": g["trend_day"].mean() * 100,
        "corr_first30_rest": corr("first30", "rest"),
        "agree_first30_rest_%": agree("first30", "rest") * 100,
        "corr_first60_rest": corr("first60", "rest60"),
        "corr_on+first30_last30": corr("on_plus_first30", "last30"),
        "corr_overnight_day": corr("overnight", "day"),
        "or_follow_median": g["or_follow"].median(),
        "or_follow_pos_%": g.apply(lambda x: float(np.nanmean(x["or_follow"] > 0)), include_groups=False) * 100,
        "or_both_sides_%": g["or_both_sides"].mean() * 100,
        "gap_fill_%(|gap|>0.25atr)": g.apply(lambda x: float(x.loc[x["gap_atr"].abs() > 0.25, "gap_filled"].mean()), include_groups=False) * 100,
    })
    return out
