from pathlib import Path
import sys,json
import numpy as np,pandas as pd
sys.path.insert(0,'/workspace/market_data_v2');from load_micro import load_micro_10sec
sys.path.insert(0,'/workspace/lucid_research_v2');from validation import moving_block_bootstrap_mean_ci
from account_replay import rolling_trials,summarize_trials
r=Path(__file__).parent;days=pd.read_csv(r.parent/'S003/MNQ_markouts.csv').date.tolist()
d=load_micro_10sec('MNQ');d.index=d.index.tz_convert('America/New_York');groups={str(k):v for k,v in d.groupby(d.index.date)};res={}
for ticks in [1,2]:
 rows=[]
 for day in days:
  g=groups[day];h=g.between_time('02:00','02:59:59');first=g.between_time('02:00','02:00');last=g.between_time('03:00','03:00');assert len(first)==len(last)==1
  slip=ticks*.25;ep=float(first.open.iloc[0])+slip;stop=ep-20;xp=float(last.open.iloc[0])-slip;exit_time=last.index[0];mae=-slip;reason='time'
  for ts,b in h.iterrows():
   if b.low<=stop:
    xp=min(stop,b.open)-slip;mae=min(mae,xp-ep);exit_time=ts;reason='stop';break
   mae=min(mae,b.low-ep-slip)
  pnl=(xp-ep)*2-1.24;mae=min(mae*2-1.24,pnl,0)
  rows.append(dict(entry_time=first.index[0],exit_time=exit_time,session_date=day,pnl_usd=pnl,mae_usd=mae,quantity=1,exit_reason=reason,observed_10sec_buckets=len(h)))
 t=pd.DataFrame(rows);t.to_csv(r/f'{ticks}tick_trades.csv',index=False);a=t.pnl_usd.to_numpy();parts=np.array_split(a,2)
 s=dict(eligible_days=len(a),net=float(a.sum()),mean=float(a.mean()),median=float(np.median(a)),worst=float(a.min()),days100=int((a>=100).sum()),days150=int((a>=150).sum()),half_nets=[float(x.sum()) for x in parts],bootstrap=moving_block_bootstrap_mean_ci(a,n_boot=3000))
 for stage in ['evaluation','funded']:
  q=rolling_trials(t,days,stage=stage,payout_profit=1500);q.to_csv(r/f'{ticks}tick_{stage}_lifecycles.csv',index=False);s[stage]=summarize_trials(q)
 res[str(ticks)]=s
(r/'results.json').write_text(json.dumps(dict(results=res,evidence='exploratory_spent_history_not_independently_verified',reserved_accessed=False),indent=2));print(json.dumps(res,indent=2))
