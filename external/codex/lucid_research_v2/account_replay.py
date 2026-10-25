"""LucidFlex 25K historical account replay for TOTAL-position v2 trade logs.

P&L and MAE already include actual micro quantity and modeled trading costs.
This module never multiplies them by quantity. It models eligibility for a
simulated payout request, immediate gross deduction, and continued trading;
neither approval nor real payment is established. Requests are capped at three,
then trading continues to the horizon. Overlapping starts are dependent.
"""
from __future__ import annotations

import json
from typing import Iterable
import numpy as np
import pandas as pd


def _dates(values: Iterable) -> list:
    """Honor supplied calendar session dates (not trading timestamps)."""
    return sorted({pd.Timestamp(x).date() for x in values})


def normalize_trades(trades: pd.DataFrame) -> pd.DataFrame:
    """Validate chronological, nonoverlapping TOTAL-position trade records.

    quantity is used only to verify contract limits. If absent it defaults to
    one for synthetic/accounting inputs. Positive MAE is accepted as a loss
    magnitude, matching the v1 convention; output MAE is signed nonpositive.
    Naive entry/exit timestamps are interpreted as UTC.
    """
    x=trades.copy()
    if x.empty:
        return pd.DataFrame(columns=['session_date','pnl_usd','mae_usd','quantity'])
    if not {'pnl_usd','mae_usd'} <= set(x.columns):
        raise ValueError('TOTAL-position pnl_usd and mae_usd are required')
    for c in ['pnl_usd','mae_usd']:
        x[c]=pd.to_numeric(x[c],errors='raise')
    if not np.isfinite(x[['pnl_usd','mae_usd']].to_numpy(float)).all():
        raise ValueError('Non-finite trade P&L or MAE')
    if 'quantity' not in x:x['quantity']=1
    q=pd.to_numeric(x.quantity,errors='raise')
    if not (np.isfinite(q)&(q>=1)&(q==np.floor(q))).all():
        raise ValueError('quantity must be positive integer micro contracts')
    x['quantity']=q.astype(int)
    if 'entry_time' in x:
        x['entry_time']=pd.to_datetime(x.entry_time,utc=True)
        if x.entry_time.isna().any():raise ValueError('Missing entry timestamp')
        x=x.sort_values('entry_time',kind='stable')
        derived=x.entry_time.dt.tz_convert('America/New_York').dt.date
        if 'session_date' not in x:x['session_date']=derived
        else:
            x['session_date']=x.session_date.map(lambda z:pd.Timestamp(z).date())
            if not (x.session_date.to_numpy()==derived.to_numpy()).all():
                raise ValueError('session_date disagrees with New York entry date')
        if 'exit_time' in x:
            x['exit_time']=pd.to_datetime(x.exit_time,utc=True)
            if x.exit_time.isna().any() or (x.exit_time<x.entry_time).any():
                raise ValueError('Invalid exit timestamp')
            if (x.entry_time<x.exit_time.shift()).fillna(False).any():
                raise ValueError('Overlapping positions must be centrally netted')
    elif 'session_date' in x:
        x['session_date']=x.session_date.map(lambda z:pd.Timestamp(z).date())
        order=['session_date']+(['entry_idx'] if 'entry_idx' in x else [])
        x=x.sort_values(order,kind='stable')
        if {'entry_idx','exit_idx'}<=set(x.columns):
            if (x.exit_idx<x.entry_idx).any() or (x.entry_idx<x.exit_idx.shift()).fillna(False).any():
                raise ValueError('Invalid or overlapping index-based positions')
    else:raise ValueError('session_date or entry_time is required')
    x['mae_usd']=np.minimum(-x.mae_usd.abs(),np.minimum(x.pnl_usd,0))
    return x.reset_index(drop=True)


def _prepared(trades: pd.DataFrame) -> dict:
    x=normalize_trades(trades)
    return {d:list(zip(g.pnl_usd.astype(float),g.mae_usd.astype(float),g.quantity.astype(int)))
            for d,g in x.groupby('session_date',sort=True)}


def simulate_trial(trades: pd.DataFrame, session_dates: Iterable,
                   stage: str='funded', payout_profit: float=1500.,
                   consistency: float=.4, gross_request: float=500.,
                   max_payouts: int=3, inactivity_calendar_days: int|None=30,
                   _byday: dict|None=None) -> dict:
    """Replay all supplied sessions, including after simulated payout requests.

    Floor ratchets EOD but is enforced against intraday MAE. Funded cycle net
    profit excludes withdrawals and resets after each request. Fixed $500 gross
    requests give $450 simulated trader net; fees for eval/reset/hosting excluded.
    """
    if stage not in ['evaluation','funded']:raise ValueError('Invalid starting stage')
    if not 0<consistency<=1:raise ValueError('Invalid consistency')
    if not 500<=gross_request<=1000:raise ValueError('Request outside 25K limits')
    if not 1<=max_payouts<=3:raise ValueError('Research request cap must be 1..3')
    days=_dates(session_dates)
    if not days:raise ValueError('At least one session required')
    byday=_byday if _byday is not None else _prepared(trades)
    current=stage;balance=25000.;floor=24000.;high=25000.;locked=False
    largest_day=0.;cycle_profit=0.;qualifying=0;eval_days=0;funded_days=0
    eval_status='pending' if stage=='evaluation' else 'not_applicable'
    eval_pass_date=None;failure=None;failure_date=None;last_activity=days[0]
    minimum_headroom=1000.;events=[];first_idx=None;first_headroom=np.nan
    minimum_after_first=np.nan;last_success_idx=-1;end_idx=0
    first_funded_index=0 if stage=='funded' else None
    for i,day in enumerate(days):
        end_idx=i
        if current=='evaluation':eval_days+=1
        else:funded_days+=1
        if inactivity_calendar_days is not None and (day-last_activity).days>=inactivity_calendar_days:
            failure=f'{current}_inactivity';failure_date=day;break
        before=balance
        # Prior EOD account profit determines funded scaling, not this trade's P&L.
        size_limit=20 if current=='evaluation' or before-25000>=1000-1e-9 else 10
        for pnl,mae,quantity in byday.get(day,[]):
            if quantity>size_limit:
                failure=f'{current}_size_violation';failure_date=day;break
            low=balance+mae  # Already TOTAL-position MAE; never multiply quantity.
            minimum_headroom=min(minimum_headroom,low-floor)
            if first_idx is not None:minimum_after_first=min(minimum_after_first,low-floor)
            if low<=floor+1e-9:
                balance=low;failure=f'{current}_breach';failure_date=day;break
            balance+=pnl
            minimum_headroom=min(minimum_headroom,balance-floor)
            if first_idx is not None:minimum_after_first=min(minimum_after_first,balance-floor)
            if abs(pnl)>=1:last_activity=day
        if failure:break
        day_net=balance-before
        if current=='evaluation':
            largest_day=max(largest_day,day_net)
            profit=balance-25000
            if profit>=1250-1e-9 and largest_day<=consistency*profit+1e-9:
                eval_status='passed';eval_pass_date=day;current='funded'
                balance=25000.;floor=24000.;high=25000.;locked=False
                qualifying=0;cycle_profit=0.;last_activity=day
                first_funded_index=i+1;last_success_idx=i
                continue
        else:
            cycle_profit+=day_net
            if day_net>=100-1e-9:qualifying+=1
            account_profit=balance-25000
            cap=min(.5*account_profit,1000.)
            if (len(events)<max_payouts and qualifying>=5 and cycle_profit>0
                    and account_profit>=payout_profit-1e-9 and gross_request<=cap+1e-9):
                request_before=balance;floor=25100.;locked=True
                balance-=gross_request
                headroom=balance-floor
                event={'date':str(day),'session_index':i,'balance_before':request_before,
                       'gross_request':gross_request,'simulated_trader_net':gross_request*.9,
                       'balance_after':balance,'headroom_after':headroom,
                       'qualifying_days':qualifying,'cycle_trading_profit':cycle_profit}
                events.append(event)
                if first_idx is None:
                    first_idx=i;first_headroom=headroom;minimum_after_first=headroom
                else:minimum_after_first=min(minimum_after_first,headroom)
                minimum_headroom=min(minimum_headroom,headroom)
                qualifying=0;cycle_profit=0.
                if balance<=floor+1e-9:
                    failure='funded_breach_on_request';failure_date=day;break
        high=max(high,balance)
        if locked:floor=25100.
        else:
            floor=min(25100.,high-1000.)
            if floor>=25100.-1e-9:locked=True
        minimum_headroom=min(minimum_headroom,balance-floor)
        if first_idx is not None:minimum_after_first=min(minimum_after_first,balance-floor)
        last_success_idx=i
    if failure and current=='evaluation':eval_status='failed'
    if failure:
        outcome=failure+('_after_request' if events else '')
    elif current=='evaluation':outcome='evaluation_pending'
    else:outcome='funded_alive_after_request' if events else 'funded_alive_no_request'
    observed_after=0 if first_idx is None else max(0,end_idx-first_idx)
    alive_after=0 if first_idx is None else max(0,last_success_idx-first_idx)
    survived20=None
    if first_idx is not None:
        if alive_after>=20:survived20=True
        elif failure:survived20=False
    to_first=None if first_idx is None else first_idx+1
    funded_to_first=None if first_idx is None else first_idx-first_funded_index+1
    return dict(trial_start=str(days[0]),trial_end=str(days[end_idx]),horizon_sessions=len(days),
        observed_sessions=end_idx+1,starting_stage=stage,ending_stage=current,outcome=outcome,
        eval_status=eval_status,eval_pass_date=None if eval_pass_date is None else str(eval_pass_date),
        eval_days=eval_days,funded_days=funded_days,failure_date=None if failure_date is None else str(failure_date),
        account_survived_horizon=failure is None,ending_balance=balance,ending_floor=floor,
        remaining_headroom=balance-floor,minimum_headroom=minimum_headroom,
        simulated_payout_requests=len(events),payout_count=len(events),
        gross_requested_total=len(events)*gross_request,simulated_trader_net_total=len(events)*gross_request*.9,
        first_request_date=None if not events else events[0]['date'],to_first_request_sessions=to_first,
        funded_sessions_to_first_request=funded_to_first,first_request_headroom=first_headroom,
        post_first_request_sessions_observed=observed_after,post_first_request_sessions_survived=alive_after,
        survived_20_sessions_after_first_request=survived20,
        post_first_request_minimum_headroom=minimum_after_first,
        cycle_qualifying_days=qualifying,cycle_trading_profit=cycle_profit,
        payout_profit_threshold=payout_profit,request_cap=max_payouts,consistency=consistency,
        request_events_json=json.dumps(events))


def rolling_trials(trades: pd.DataFrame,session_dates: Iterable,horizon: int=120,
                   stride: int=10,stage: str='funded',payout_profit: float=1500.,**kwargs) -> pd.DataFrame:
    """Every stride-th start with a FULL horizon; starts are dependent."""
    if horizon<1 or stride<1:raise ValueError('Positive horizon/stride required')
    days=_dates(session_dates);byday=_prepared(trades);rows=[]
    for i in range(0,len(days)-horizon+1,stride):
        r=simulate_trial(trades,days[i:i+horizon],stage=stage,payout_profit=payout_profit,_byday=byday,**kwargs)
        r['start_index']=i;rows.append(r)
    return pd.DataFrame(rows)


def recent_trial(trades: pd.DataFrame,session_dates: Iterable,lookback_sessions: int=120,
                 allow_short: bool=True,stage: str='funded',payout_profit: float=1500.,**kwargs) -> pd.DataFrame:
    """One most-recent window, optionally shorter than requested lookback."""
    days=_dates(session_dates)
    if lookback_sessions<1:raise ValueError('Positive lookback required')
    if not days or (len(days)<lookback_sessions and not allow_short):return pd.DataFrame()
    used=days[-lookback_sessions:]
    r=simulate_trial(trades,used,stage=stage,payout_profit=payout_profit,**kwargs)
    r.update(start_index=max(0,len(days)-lookback_sessions),short_horizon=len(used)<lookback_sessions)
    return pd.DataFrame([r])


def summarize_trials(trials: pd.DataFrame) -> dict:
    """Descriptive counts only; simulated request is not approved cash payment."""
    note=('Overlapping historical starts are dependent, not independent payout probabilities. '
          'Requests are simulated eligibility events, not approvals or real payments. '
          'Trading continues after requests; evaluation/reset/hosting fees excluded.')
    if trials.empty:return {'trials':0,'note':note}
    requested=trials.simulated_payout_requests>0
    failed=~trials.account_survived_horizon.astype(bool)
    survival=trials.survived_20_sessions_after_first_request
    known=survival.notna()
    return dict(trials=len(trials),eval_passed_paths=int((trials.eval_status=='passed').sum()),
        paths_with_request=int(requested.sum()),paths_with_two_requests=int((trials.simulated_payout_requests>=2).sum()),
        paths_with_three_requests=int((trials.simulated_payout_requests>=3).sum()),
        total_simulated_requests=int(trials.simulated_payout_requests.sum()),failed_paths=int(failed.sum()),
        failed_after_request_paths=int((failed&requested).sum()),
        alive_horizon_paths=int((~failed).sum()),
        observed_request_fraction=float(requested.mean()),
        mean_simulated_trader_net=float(trials.simulated_trader_net_total.mean()),
        median_sessions_to_first_request=None if not requested.any() else float(trials.loc[requested,'to_first_request_sessions'].median()),
        post_request_20_session_assessable_paths=int(known.sum()),
        post_request_20_session_survivors=int(survival.eq(True).sum()),
        post_request_20_session_censored_paths=int((requested&~known).sum()),
        outcomes=trials.outcome.value_counts().to_dict(),note=note)
