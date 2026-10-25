"""Post-final audit and minimum-withdrawal sensitivity; no strategy selection."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from prop_sim import rolling_trials,summarize_trials

ROOT=Path(__file__).parent
OUT=ROOT/'final_results'


def independent_first_path(t,dates,stage='evaluation',horizon=120,quantity=2,payout_profit=1500):
    """Independent compact rules replay, for matching outcome counts only."""
    byday={str(d):g for d,g in t.groupby('session_date')}
    bal=25000.;floor=24000.;hwm=25000.;maxday=0.;qual=0;passed=False
    cur=stage;last=pd.Timestamp(dates[0]);ed=fd=0
    for date in dates[:horizon]:
        day=pd.Timestamp(date)
        if cur=='evaluation':ed+=1
        else:fd+=1
        if (day-last).days>=30:return f'{cur}_inactivity',passed,ed,fd
        start=bal
        for row in byday.get(str(date),pd.DataFrame()).itertuples():
            if bal+quantity*min(0.,row.pnl_usd,-abs(row.mae_usd))<=floor+1e-9:
                return f'{cur}_breach',passed,ed,fd
            bal+=quantity*row.pnl_usd
            if abs(quantity*row.pnl_usd)>=1:last=day
        dp=bal-start
        if cur=='evaluation':
            maxday=max(maxday,dp)
            if bal-25000>=1250-1e-9 and maxday<=.4*(bal-25000)+1e-9:
                passed=True;cur='funded';bal=25000.;hwm=25000.;floor=24000.;qual=0;last=day
                continue
        else:
            qual+=int(dp>=100-1e-9)
            if qual>=5 and bal-25000>=payout_profit-1e-9 and min(.5*(bal-25000),1000)>=500-1e-9:
                return ('payout' if bal-500>25100 else 'funded_breach_on_payout'),passed,ed,fd
        hwm=max(hwm,bal);floor=min(25100.,hwm-1000.)
    return f'{cur}_pending',passed,ed,fd


def main():
    out={
        'purpose':'Post-final fixed-strategy minimum first-payout threshold sensitivity, not retuning or selecting a strategy/policy.',
        'strategy':'E028','instrument':'MES priced from ES bars','quantity':2,
        'primary_policy_profit_threshold':1500.,'sensitivity_profit_threshold':1000.,
        'gross_request':500.,'trader_net_if_approved':450.,
        'minimum_policy_example':{'profit':1000.,'balance_before':26000.,'gross_request':500.,'balance_after':25500.,'locked_floor':25100.,'remaining_headroom':400.},
        'reserve_policy_example':{'profit':1500.,'balance_before':26500.,'gross_request':500.,'balance_after':26000.,'locked_floor':25100.,'remaining_headroom':900.},
        'sessions':'194 complete holdout RTH sessions, 2026-01-02 through 2026-10-09',
        'limitations':['Historical starts overlap and are dependent; observed fractions are not independent success probabilities.',
                       'First payout only; no post-payout survival, approvals, evaluation/reset fees or actual MES order-book execution simulated.',
                       'Both evaluation and funded stages share the same 120-session total horizon; funded-only uses60 sessions.',
                       'A failed first-payout objective is distinguished from an account breach; pending means horizon ended.'],
        'results':{},'audit':{}}
    for cost in ['baseline','stress']:
        t=pd.read_csv(OUT/f'E028_holdout_{cost}_trades.csv')
        d=pd.read_csv(OUT/f'E028_holdout_{cost}_daily_oneMES.csv')
        dates=pd.to_datetime(d.iloc[:,0]).dt.date.to_list()
        # Reconcile recorded one-MES P&L against point values without using
        # convert_mes(), the code under audit.
        np.testing.assert_allclose(t.pnl_usd.to_numpy(),t.pnl_points.to_numpy()*5-1.24,atol=1e-10)
        assert np.all(t.mae_usd<=np.minimum(t.pnl_usd,0)+1e-8)
        pnl=2*t.pnl_usd.to_numpy()
        equity=np.r_[0.,np.cumsum(pnl)]
        closeddd=(np.maximum.accumulate(equity)-equity).max()
        check={'net_2MES':float(pnl.sum()),'closed_trade_drawdown_2MES':float(closeddd),
               'trade_count':len(t),'pnl_conversion':'Every row: pnl_points * $5/MES - $1.24 round-trip fee, then quantity2.',
               'mae_check':'Every row signed MAE <= min(realized PNL,0).'}
        for stage,horizon in [('evaluation',120),('funded',60)]:
            primary=rolling_trials(t,dates,quantity=2,horizon=horizon,stride=5,stage=stage,payout_profit=1500)
            prior=pd.read_csv(OUT/f'E028_{cost}_{stage}_{horizon}_replays.csv')
            assert primary.outcome.to_list()==prior.outcome.to_list()
            assert primary.eval_status.to_list()==prior.eval_status.to_list()
            # Independently reconstruct each primary scenario's end outcome.
            for row in primary.itertuples():
                start=int(row.start_index)
                r=independent_first_path(t,dates[start:start+horizon],stage=stage,horizon=horizon)
                assert r[0]==row.outcome,(cost,stage,start,r,row.outcome)
                assert r[2]==row.eval_days and r[3]==row.funded_days
            sensitivity=rolling_trials(t,dates,quantity=2,horizon=horizon,stride=5,stage=stage,payout_profit=1000)
            name=f'E028_{cost}_{stage}_{horizon}_minimum_payout_policy_replays.csv'
            sensitivity.to_csv(OUT/name,index=False)
            out['results'][f'{cost}_{stage}_{horizon}']={
                'primary_reserve_policy':summarize_trials(primary),
                'minimum_payout_policy':summarize_trials(sensitivity),
                'trials_file':name,
                'minimum_policy_payout_after_headroom':sensitivity.loc[sensitivity.outcome.eq('payout'),'payout_after_headroom'].to_list(),
            }
        out['audit'][cost]=check
    out['audit']['conclusion']='No accounting bug found in MES point-value conversion or primary replay outcomes. Every saved primary trial matched independent reconstruction.'
    # Strict JSON uses null for medians with no payouts.
    def clean(value):
        if isinstance(value,dict):return {k:clean(v) for k,v in value.items()}
        if isinstance(value,list):return [clean(v) for v in value]
        if isinstance(value,float) and not np.isfinite(value):return None
        return value
    out=clean(out)
    (OUT/'minimum_payout_policy_sensitivity.json').write_text(json.dumps(out,indent=2,allow_nan=False))
    print(json.dumps(out,indent=2,allow_nan=False))

if __name__=='__main__':main()
