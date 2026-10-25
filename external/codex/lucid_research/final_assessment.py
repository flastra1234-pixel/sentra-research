"""One-time final assessment of already frozen candidates. Never select here."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib,json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import study,es_study
from engine import daily_equity
from prop_sim import rolling_trials,summarize_trials

ROOT=Path(__file__).parent
OUT=ROOT/'final_results'
OUT.mkdir(exist_ok=True)

def main():
 branches=['results','results_risk','results_higher_tf','results_time','results_es']
 freezes={b:json.loads((ROOT/b/'frozen_selection.json').read_text()) for b in branches}
 manifest={b:hashlib.sha256((ROOT/b/'frozen_selection.json').read_bytes()).hexdigest() for b in branches}
 (OUT/'pre_holdout_freeze_manifest.json').write_text(json.dumps({'time_utc':datetime.now(timezone.utc).isoformat(),'frozen_sha256':manifest,'selections':freezes},indent=2))
 assert all(not freezes[b]['configs'] for b in branches[:-1]),'Review non-ES frozen candidates before using this assessment script'
 frozen=freezes['results_es'];cs=frozen['configs']
 if not cs:print('No candidate. Final period remains untested.');return
 d=es_study.load(include_holdout=True)
 rows=[];replays={};monthly=[]
 fig,axs=plt.subplots(2,1,figsize=(11,7),height_ratios=[2,1],sharex=True)
 for c in cs:
  for part in ['development','validation','holdout']:
   x=es_study.split(d,part);dates=sorted(x.session_date.unique())
   for label,ticks in [('baseline',1),('stress',2)]:
    t=es_study.run_backtest(x,c,slip_ticks=ticks)
    t.to_csv(OUT/f'{c["id"]}_{part}_{label}_trades.csv',index=False)
    m=es_study.metrics(t,dates,q=2);ci=study.block_ci(t,dates,q=2)
    daily=daily_equity(t,dates);daily.to_csv(OUT/f'{c["id"]}_{part}_{label}_daily_oneMES.csv')
    row=dict(id=c['id'],split=part,cost=label,quantity=2,sessions=len(dates),first=str(dates[0]),last=str(dates[-1]),**m,daily_mean_ci_low=ci[0],daily_mean_ci_high=ci[1],qualifying_100_days=int((daily.pnl_usd*2>=100).sum()))
    rows.append(row)
    mm=(daily.pnl_usd*2).groupby(pd.to_datetime(daily.index).to_period('M')).sum()
    monthly.extend(dict(id=c['id'],split=part,cost=label,month=str(k),pnl=v) for k,v in mm.items())
    if part=='holdout':
     row['final_screen_pass']=m['trades']>=30 and m['pf']>=1.10 and m['pnl']>0 and m['intraday_dd']<=800
     for stage,horizon in [('evaluation',120),('funded',60)]:
      trials=rolling_trials(t,dates,quantity=2,horizon=horizon,stride=5,stage=stage,payout_profit=1500)
      key=f'{c["id"]}_{label}_{stage}_{horizon}'
      trials.to_csv(OUT/f'{key}_replays.csv',index=False)
      replays[key]=summarize_trials(trials)
     eq=daily.pnl_usd.cumsum()*2
     ax=axs[0];ax.plot(pd.to_datetime(eq.index),eq.values,label=f'{label}: {ticks} tick(s)/side')
     hwm=np.maximum.accumulate(np.r_[0,eq.values])[1:]
     axs[1].plot(pd.to_datetime(eq.index),eq.values-hwm,label=label)
  # Full chronology replay is reported as selected-sample descriptive only.
  for label,ticks in [('baseline',1),('stress',2)]:
   full=d.loc[d.session_date.astype(str)>='2025-06-20'].copy();full.attrs.update(d.attrs)
   t=es_study.run_backtest(full,c,slip_ticks=ticks)
   t.to_csv(OUT/f'{c["id"]}_all_{label}_trades.csv',index=False)
   dates=sorted(full.session_date.unique())
   for stage,horizon in [('evaluation',120),('funded',60)]:
    trials=rolling_trials(t,dates,quantity=2,horizon=horizon,stride=5,stage=stage,payout_profit=1500)
    key=f'{c["id"]}_{label}_{stage}_{horizon}_all_selected'
    trials.to_csv(OUT/f'{key}_replays.csv',index=False);replays[key]=summarize_trials(trials)
 pd.DataFrame(rows).to_csv(OUT/'split_metrics.csv',index=False)
 pd.DataFrame(monthly).to_csv(OUT/'monthly_pnl.csv',index=False)
 (OUT/'account_replay_summary.json').write_text(json.dumps(replays,indent=2))
 axs[0].set_title('Frozen E028: 2026 historical holdout, 2 MES (ES price proxy)')
 axs[0].set_ylabel('Cumulative net P&L ($)');axs[1].set_ylabel('Closed daily drawdown ($)')
 for ax in axs:ax.axhline(0,color='gray',lw=.7);ax.grid(alpha=.2);ax.legend()
 axs[1].axhline(-1000,color='red',ls='--',label='Account loss allowance (not a replay)')
 fig.tight_layout();fig.savefig(OUT/'holdout_equity.png',dpi=160);plt.close(fig)
 print(pd.DataFrame(rows).to_string(index=False));print(json.dumps(replays,indent=2))

if __name__=='__main__':main()
