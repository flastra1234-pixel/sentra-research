from pathlib import Path
import sys,json
import numpy as np,pandas as pd
sys.path.insert(0,'/workspace/market_data_v2');from load_micro import load_micro_1min
sys.path.insert(0,'/workspace/lucid_research_v2');from validation import moving_block_bootstrap_mean_ci
from account_replay import rolling_trials,summarize_trials
R=Path(__file__).parent
markets={};features=[]
for asset in ['MES','MNQ']:
 d=load_micro_1min(asset);et=d.index.tz_convert('America/New_York');d=d.copy();d['day']=et.date.astype(str);d['minute']=et.hour*60+et.minute;d=d.loc[(d.minute>=570)&(d.minute<960)&(et.dayofweek<5)].copy()
 count=d.groupby('day').size();d=d[d.day.isin(count[count==390].index)].copy();g=d.groupby('day')
 d['r1']=g.close.pct_change()*10000;d['r5']=(d.close/g.close.shift(5)-1)*10000;d['vol']=d.r1.groupby(d.day).transform(lambda x:x.rolling(30).std());d['hour']=(d.minute-570)/390
 d['entry']=g.open.shift(-1);d['exit']=g.open.shift(-6);d['y']=(d.exit/d.entry-1)*10000
 d['row']=np.arange(len(d));markets[asset]=d
common=sorted(set(markets['MES'].day)&set(markets['MNQ'].day))
for asset in markets:
 d=markets[asset];d=d[d.day.isin(common)].copy();d['row']=np.arange(len(d));markets[asset]=d
out={};allp=[]
for asset,pv,stop in [('MES',5,8),('MNQ',2,20)]:
 d=markets[asset];other=markets['MNQ' if asset=='MES' else 'MES'];z=d.join(other[['r1','r5']].rename(columns={'r1':'other1','r5':'other5'}),how='inner')
 z['stale1']=z.groupby('minute').other1.shift(1);z['stale5']=z.groupby('minute').other5.shift(1)
 z=z[(z.minute>=600)&(z.minute<=920)&(z.minute%5==0)].dropna(subset=['r1','r5','vol','other1','other5','stale1','stale5','y'])
 records=[]
 for start in range(60,len(common)-19,20):
  train=z[z.day.isin(common[start-60:start])];test=z[z.day.isin(common[start:start+20])].copy()
  assert train.day.max()<test.day.min()
  for model,cols in [('own',['r1','r5','vol','hour']),('cross',['r1','r5','vol','hour','other1','other5']),('stale',['r1','r5','vol','hour','stale1','stale5'])]:
   a=train[cols].to_numpy();b=test[cols].to_numpy();mu=a.mean(0);sd=a.std(0);sd[sd==0]=1;a=np.column_stack([np.ones(len(a)),(a-mu)/sd]);b=np.column_stack([np.ones(len(b)),(b-mu)/sd]);coef=np.linalg.solve(a.T@a+1e-6*np.eye(a.shape[1]),a.T@train.y.to_numpy());test[model]=b@coef
  test['fold']=start//20;records.append(test)
 pred=pd.concat(records).sort_index();pred.to_csv(R/f'{asset}_predictions.csv');days=sorted(pred.day.unique());summaries={}
 for model in ['own','cross','stale']:
  for ticks in [1,2]:
   logs=[];counts={};last_exit=None;cost=1.24+pv
   for ts,b in pred.iterrows():
    gross=b[model]*b.close/10000*pv
    if abs(gross)<=cost+2 or counts.get(b.day,0)>=2:continue
    i=int(b.row);ei=i+1;xi=i+6
    if last_exit is not None and d.index[ei]<=last_exit:continue
    side=1 if gross>0 else -1;slip=ticks*.25;ep=float(d.open.iloc[ei])+side*slip;sp=ep-side*stop;xp=float(d.open.iloc[xi])-side*slip;ex=xi;mae=-slip
    for j in range(ei,xi):
     bar=d.iloc[j];hit=(bar.low<=sp)if side==1 else(bar.high>=sp)
     if hit:xp=(min(sp,bar.open)-slip)if side==1 else(max(sp,bar.open)+slip);mae=min(mae,side*(xp-ep));ex=j;break
     mae=min(mae,(bar.low-ep-slip)if side==1 else(ep-bar.high-slip))
    pnl=side*(xp-ep)*pv-1.24;logs.append(dict(entry_time=d.index[ei],exit_time=d.index[ex],session_date=b.day,pnl_usd=pnl,mae_usd=min(mae*pv-1.24,pnl,0),quantity=1));last_exit=d.index[ex];counts[b.day]=counts.get(b.day,0)+1
   t=pd.DataFrame(logs,columns=['entry_time','exit_time','session_date','pnl_usd','mae_usd','quantity']);t.to_csv(R/f'{asset}_{model}_{ticks}tick_trades.csv',index=False)
   daily=t.groupby('session_date').pnl_usd.sum().reindex(days,fill_value=0);monthly=daily.groupby(pd.to_datetime(daily.index).to_period('M')).sum()
   s=dict(eligible_days=len(days),trades=len(t),net=float(daily.sum()),mean=float(daily.mean()),median=float(daily.median()),worst=float(daily.min()),days100=int((daily>=100).sum()),days150=int((daily>=150).sum()),inactive_days=int((daily==0).sum()),positive_months=int((monthly>0).sum()),bootstrap=moving_block_bootstrap_mean_ci(daily,n_boot=2000))
   for stage in ['evaluation','funded']:
    trials=rolling_trials(t,days,stage=stage,payout_profit=1500);trials.to_csv(R/f'{asset}_{model}_{ticks}tick_{stage}_lifecycles.csv',index=False);s[stage]=summarize_trials(trials)
   summaries[f'{model}_{ticks}tick']=s
 error={m:((pred.y-pred[m])**2).groupby(pred.day).mean()for m in ['own','cross','stale']};gain=error['own']-error['cross'];diag=moving_block_bootstrap_mean_ci(gain,n_boot=3000);allp.append((asset,diag['centered_bootstrap_p_value']))
 out[asset]=dict(models=summaries,incremental_mse_gain=diag,zero_forecast_mse=float((pred.y**2).mean()),own_mse=float(error['own'].mean()),cross_mse=float(error['cross'].mean()),stale_mse=float(error['stale'].mean()))
prev=0
for i,(asset,p)in enumerate(sorted(allp,key=lambda x:x[1])):prev=max(prev,min(1,p*(2-i)));out[asset]['incremental_holm_p']=prev
(R/'results.json').write_text(json.dumps(dict(results=out,evidence='spent_history_pseudo_out_of_sample',reserved_accessed=False),indent=2));print(json.dumps({k:{'gain':v['incremental_mse_gain'],'holm':v['incremental_holm_p'],'models':{m:{a:b for a,b in s.items()if a in ['net','trades','eligible_days','days100','days150','inactive_days']}for m,s in v['models'].items()}}for k,v in out.items()},indent=2))
