"""Conservative historical LucidFlex 25K evaluation / first-payout replay.

Research assumptions, not an official Lucid risk engine. Each trade row represents
one micro contract, already including its commission and assumed slippage.
``mae_usd`` is preferably signed <=0: minimum equity change from just before
entry, including entry execution costs. Positive values are also accepted as
adverse-excursion magnitudes. The final realized P&L is always checked as well.
Trades must not overlap; a fleet must be netted centrally before this simulator.

The floor ratchets only at EOD, but touching it intraday is a failure. A successful
evaluation ends at EOD and starts a fresh funded account next session. The
first-payout model ends immediately after a $500 gross ($450 trader net)
withdrawal; it does NOT establish continued survival after payout. Overlapping
rolling starts are dependent historical scenarios, not independent probabilities.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable
import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Rules:
    starting_balance: float = 25000.0
    trailing_loss: float = 1000.0
    locked_floor: float = 25100.0
    eval_target: float = 1250.0
    consistency: float = 0.40
    qualifying_day_profit: float = 100.0
    required_qualifying_days: int = 5
    payout_profit: float = 1500.0
    gross_payout: float = 500.0
    trader_split: float = 0.90
    # Conservative interpretation: account is expired at start of the session
    # after 30 calendar days without a >=$1 realized net trade.
    inactivity_calendar_days: int | None = 30


def _dates(values: Iterable) -> list:
    return sorted({pd.Timestamp(x).date() for x in values})


def _date_value(x):
    if isinstance(x, pd.Timestamp) and x.tz is not None:
        return x.tz_convert('America/New_York').date()
    return pd.Timestamp(x).date()


def _prepare(trades: pd.DataFrame) -> dict:
    if trades.empty:
        return {}
    if 'pnl_usd' not in trades or 'mae_usd' not in trades:
        raise ValueError('trades require pnl_usd and mae_usd, per one micro contract')
    df = trades.copy()
    if 'session_date' not in df:
        if 'entry_time' not in df:
            raise ValueError('trades require session_date or entry_time')
        t = pd.to_datetime(df['entry_time'], utc=True)
        df['session_date'] = t.dt.tz_convert('America/New_York').dt.date
    else:
        df['session_date'] = df['session_date'].map(_date_value)
    if not np.isfinite(df[['pnl_usd','mae_usd']].to_numpy(float)).all():
        raise ValueError('Non-finite P&L / excursion values cannot be simulated')
    if 'entry_time' in df:
        df['_entry'] = pd.to_datetime(df['entry_time'], utc=True)
        df = df.sort_values('_entry', kind='stable')
        if 'exit_time' in df:
            exits = pd.to_datetime(df['exit_time'], utc=True)
            if (df['_entry'] < exits.shift()).fillna(False).any():
                raise ValueError('Overlapping trades must be netted before account replay')
    out = {}
    for day, g in df.groupby('session_date',sort=True):
        vals=[]
        for p, m in g[['pnl_usd','mae_usd']].to_numpy(float):
            # Accept either signed-negative MAE or positive loss magnitude.
            adverse = -abs(m)
            vals.append((float(p),float(min(0., adverse, p))))
        out[day]=vals
    return out


def simulate_trial(trades: pd.DataFrame, session_dates: Iterable, quantity: int=2,
                   consistency: float=0.4, payout_profit: float=1500.,
                   stage: str='evaluation', inactivity_calendar_days: int|None=30,
                   gross_payout: float=500., _prepared: dict|None=None) -> dict:
    """Replay one start through eval and funded, or start already funded.

    All supplied sessions count toward the horizon, including no-trade sessions.
    Commission/slippage are already in pnl_usd and scale with fixed quantity.
    Fixed quantities 1..10 remain under the most restrictive funded size cap.
    """
    if not isinstance(quantity,(int,np.integer)) or not 1 <= quantity <= 10:
        raise ValueError('quantity must be a fixed 1..10 micro contracts')
    if not 0 < consistency <= 1:
        raise ValueError('consistency must be in (0,1]')
    if stage not in ('evaluation','funded'):
        raise ValueError('stage must be evaluation or funded')
    if gross_payout < 500 or gross_payout > 1000:
        raise ValueError('25K payout request must be between $500 and $1,000')
    days=_dates(session_dates)
    if not days:
        raise ValueError('At least one session is needed')
    byday=_prepared if _prepared is not None else _prepare(trades)
    rules=Rules(consistency=consistency,payout_profit=payout_profit,
                inactivity_calendar_days=inactivity_calendar_days,gross_payout=gross_payout)
    cur_stage=stage
    balance=rules.starting_balance
    floor=balance-rules.trailing_loss
    high_water=balance
    biggest_day=0.
    qualifying_days=0
    eval_days=0
    funded_days=0
    last_activity=days[0]
    min_headroom=rules.trailing_loss
    eval_status='not_applicable' if stage=='funded' else 'pending'
    eval_pass_date=None
    payout_before_headroom=np.nan
    payout_after_headroom=np.nan
    failure_date=None
    outcome=None
    end_date=days[-1]
    for day in days:
        end_date=day
        if cur_stage=='evaluation':
            eval_days+=1
        else:
            funded_days+=1
        # Evaluate inactivity against real calendar elapsed time, not bars.
        if (inactivity_calendar_days is not None
            and (day-last_activity).days >= inactivity_calendar_days):
            outcome=f'{cur_stage}_inactivity'
            failure_date=day
            if cur_stage=='evaluation':
                eval_status='failed'
            break
        day_start=balance
        failed=False
        for pnl, mae in byday.get(day,[]):
            minimum_equity=balance+quantity*mae
            min_headroom=min(min_headroom,minimum_equity-floor)
            if minimum_equity <= floor+1e-9:
                outcome=f'{cur_stage}_breach'
                failure_date=day
                if cur_stage=='evaluation':
                    eval_status='failed'
                # Stop at the breach. The precise liquidation price requires
                # tick data; never continue or count this trade as a success.
                balance=minimum_equity
                failed=True
                break
            balance+=quantity*pnl
            min_headroom=min(min_headroom,balance-floor)
            if abs(quantity*pnl)>=1:
                last_activity=day
        if failed:
            break
        day_pnl=balance-day_start
        if cur_stage=='evaluation':
            biggest_day=max(biggest_day,day_pnl)
            total_profit=balance-rules.starting_balance
            if (total_profit >= rules.eval_target-1e-9
                and biggest_day <= rules.consistency*total_profit+1e-9):
                eval_status='passed'
                eval_pass_date=day
                # Funded starts with a fresh balance and risk allowance on the
                # next session; unused eval profit is not carried forward.
                cur_stage='funded'
                balance=rules.starting_balance
                high_water=balance
                floor=balance-rules.trailing_loss
                qualifying_days=0
                last_activity=day
                continue
        else:
            if day_pnl >= rules.qualifying_day_profit-1e-9:
                qualifying_days+=1
            account_profit=balance-rules.starting_balance
            max_request=min(0.5*account_profit,1000.)
            if (qualifying_days >= rules.required_qualifying_days
                and account_profit >= rules.payout_profit-1e-9
                and account_profit>0
                and rules.gross_payout <= max_request+1e-9):
                # Request locks the threshold, then the full gross amount is
                # deducted. Insufficient reserve is a failure, not a payout.
                floor=rules.locked_floor
                payout_before_headroom=balance-floor
                balance-=rules.gross_payout
                payout_after_headroom=balance-floor
                min_headroom=min(min_headroom,payout_after_headroom)
                if balance<=floor+1e-9:
                    outcome='funded_breach_on_payout'
                    failure_date=day
                else:
                    outcome='payout'
                break
        high_water=max(high_water,balance)
        floor=min(rules.locked_floor,high_water-rules.trailing_loss)
        min_headroom=min(min_headroom,balance-floor)
    if outcome is None:
        outcome=f'{cur_stage}_pending'
    return {
        'trial_start':str(days[0]),'trial_end':str(end_date),
        'outcome':outcome,'eval_status':eval_status,
        'eval_days':eval_days,'funded_days':funded_days,
        'to_payout_days':eval_days+funded_days if outcome=='payout' else np.nan,
        'eval_pass_date':None if eval_pass_date is None else str(eval_pass_date),
        'failure_date':None if failure_date is None else str(failure_date),
        'minimum_headroom':float(min_headroom),
        'ending_balance':float(balance),'ending_floor':float(floor),
        'funded_qualifying_days':qualifying_days,
        'gross_payout':rules.gross_payout if outcome=='payout' else 0.,
        'trader_net_payout':rules.gross_payout*rules.trader_split if outcome=='payout' else 0.,
        'payout_before_headroom':float(payout_before_headroom),
        'payout_after_headroom':float(payout_after_headroom),
        'quantity':quantity,'consistency':consistency,
        'payout_profit_threshold':payout_profit,
        'horizon_sessions':len(days),'starting_stage':stage,
    }


def rolling_trials(trades: pd.DataFrame, session_dates: Iterable, quantity: int=2,
                   horizon: int=120, stride: int=5, consistency: float=.4,
                   payout_profit: float=1500., stage: str='evaluation',
                   inactivity_calendar_days: int|None=30,
                   gross_payout: float=500.) -> pd.DataFrame:
    """Every ``stride``th session with a COMPLETE ``horizon`` available.

    A pending path exhausted the observation horizon; it is NOT a breach. Starts
    overlap heavily, so fractions are descriptive historical scenario results.
    """
    if horizon<1 or stride<1:
        raise ValueError('horizon and stride must be positive')
    days=_dates(session_dates)
    prepared=_prepare(trades)
    out=[]
    for start in range(0,len(days)-horizon+1,stride):
        result=simulate_trial(trades,days[start:start+horizon],quantity=quantity,
            consistency=consistency,payout_profit=payout_profit,stage=stage,
            inactivity_calendar_days=inactivity_calendar_days,
            gross_payout=gross_payout,_prepared=prepared)
        result['start_index']=start
        out.append(result)
    return pd.DataFrame(out)


def summarize_trials(trials: pd.DataFrame) -> dict:
    """Counts and observed fractions; no independence-based confidence interval."""
    if trials.empty:
        return {'trials':0,'note':'Insufficient sessions for the full horizon'}
    outcomes=trials['outcome']
    hit=outcomes.eq('payout')
    passed=trials['eval_status'].eq('passed')
    failed=outcomes.str.contains('breach|inactivity')
    pending=outcomes.str.endswith('pending')
    return {
        'trials':len(trials), 'payout_paths':int(hit.sum()),
        'eval_passed_paths':int(passed.sum()),'failed_paths':int(failed.sum()),
        'pending_paths':int(pending.sum()),
        'observed_payout_fraction':float(hit.mean()),
        'observed_eval_pass_fraction':float(passed.mean()),
        'median_sessions_to_payout':float(trials.loc[hit,'to_payout_days'].median()),
        'outcomes':outcomes.value_counts().to_dict(),
        'note':'Overlapping historical starts; fractions are NOT independent probability estimates. First payout only; evaluation/reset fees excluded.'
    }
