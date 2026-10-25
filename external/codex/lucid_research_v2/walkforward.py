"""Predeclared rolling selection and current freeze, before reserved checks."""
from pathlib import Path
import json,hashlib
from datetime import datetime,timezone
import numpy as np
import pandas as pd
from engine_v2 import backtest
from validation import rolling_folds,moving_block_bootstrap_mean_ci
from search import ROOT,OUT,load_primary,daily_summary

KEYS=['family','tf','window','stop_atr','reward_r','max_hold','context','direction']

def neighbor_indices(cs):
 def key(c):return tuple(c[k] for k in KEYS)
 lookup={key(c):i for i,c in enumerate(cs)}
 axes={'stop_atr':[1.5,2.5],'reward_r':[1,1.5,2],'max_hold':[30,90]}
 ns=[]
 for c in cs:
  row=[]
  for k,vals in axes.items():
   loc=vals.index(c[k])
   for step in [-1,1]:
    if 0<=loc+step<len(vals):
     other=dict(c);other[k]=vals[loc+step];row.append(lookup[key(other)])
  ns.append(row)
 return ns

def stats(matrix,indices):
 x=matrix[:,indices,:].astype(np.float64)
 sums=x[:,:,:4].sum(axis=1);net=sums[:,0];n=sums[:,3]
 curve=x[:,:,0].cumsum(axis=1)
 high=np.maximum.accumulate(np.column_stack([np.zeros(len(x)),curve]),axis=1)[:,1:]
 dd=(high-curve).max(axis=1)
 pf=np.divide(sums[:,1],sums[:,2],out=np.full(len(x),999.),where=sums[:,2]>0)
 avg=np.divide(net,n,out=np.zeros(len(x)),where=n>0)
 return dict(net=net,n=n,pf=pf,dd=dd,avg=avg)

def select(cs,matrix,train_indices,val_indices,neighbors):
 tr=stats(matrix,train_indices);va=stats(matrix,val_indices)
 support=np.array([np.mean(tr['net'][ids]>0) for ids in neighbors])
 train_ok=(tr['n']>=40)&(tr['pf']>=1.05)&(tr['net']>0)&(tr['avg']>=2)&(support>=.60)
 score=tr['net']/np.maximum(tr['dd'],180)
 short=[]
 for family in dict.fromkeys(c['family'] for c in cs):
  idx=[i for i,c in enumerate(cs) if c['family']==family and train_ok[i]]
  short.extend(sorted(idx,key=lambda i:(-score[i],cs[i]['id']))[:3])
 chosen=[]
 for i in short:
  if va['n'][i]>=8 and va['net'][i]>0 and va['pf'][i]>=1.05:
   balanced=min(score[i],va['net'][i]/max(va['dd'][i],180))
   chosen.append(dict(index=i,id=cs[i]['id'],family=cs[i]['family'],score=float(balanced),
                      train_net=float(tr['net'][i]),train_pf=float(tr['pf'][i]),train_trades=int(tr['n'][i]),
                      validation_net=float(va['net'][i]),validation_pf=float(va['pf'][i]),validation_trades=int(va['n'][i]),
                      positive_neighbor_fraction=float(support[i]),config=cs[i]))
 chosen.sort(key=lambda r:(-r['score'],r['id']))
 result=[];used=set()
 for r in chosen:
  if r['family'] in used:continue
  used.add(r['family']);result.append(r)
  if len(result)==3:break
 return result,dict(training_eligible=int(train_ok.sum()),training_shortlisted=len(short),validated_variants=len(chosen))

def merge_fleet(frames):
 if not frames:return pd.DataFrame(columns=['entry_time','exit_time','session_date','pnl_usd','mae_usd','quantity'])
 x=pd.concat(frames,ignore_index=True)
 if x.empty:return x
 x=x.sort_values(['entry_time','selection_score','selection_priority','asset','config_id'],ascending=[True,False,True,True,True],kind='stable')
 accepted=[];last=None;counts={}
 for _,row in x.iterrows():
  date=row.session_date
  if counts.get(date,0)>=2 or (last is not None and row.entry_time<=last):continue
  accepted.append(row);last=row.exit_time;counts[date]=counts.get(date,0)+1
 return pd.DataFrame(accepted).reset_index(drop=True)

def trade_metrics(t,dates):
 dates=[str(z) for z in dates]
 if t.empty:return dict(trades=0,net=0,pf=0,max_closed_dd=0,intraday_eod_dd=0,sessions=len(dates),qualifying_days=0)
 x=t.sort_values('entry_time').copy();x['date_str']=x.session_date.astype(str)
 p=x.pnl_usd.to_numpy(float);eq=np.r_[0,p.cumsum()]
 daily=x.groupby('date_str').pnl_usd.sum().reindex(dates,fill_value=0)
 before=x.groupby('date_str').pnl_usd.cumsum()-x.pnl_usd
 lows=(before+x.mae_usd).groupby(x.date_str).min().reindex(dates,fill_value=0).clip(upper=0)
 de=daily.cumsum();prior=de.shift(1,fill_value=0)
 high=np.maximum.accumulate(np.r_[0,de.to_numpy()])[:-1]
 wins=p[p>0].sum();loss=-p[p<0].sum()
 monthly=daily.groupby(pd.to_datetime(daily.index).to_period('M')).sum()
 return dict(trades=len(x),net=float(p.sum()),pf=float(wins/loss) if loss else 999,
             max_closed_dd=float((np.maximum.accumulate(eq)-eq).max()),
             intraday_eod_dd=float((high-prior.to_numpy()-lows.to_numpy()).max()),
             sessions=len(dates),qualifying_days=int((daily>=100).sum()),
             win_rate=float((p>0).mean()),mean_trade=float(p.mean()),
             positive_months=int((monthly>0).sum()),months=len(monthly),
             top5_winner_share=float(np.sort(p[p>0])[-5:].sum()/p.sum()) if p.sum()>0 else None,
             daily_bootstrap=moving_block_bootstrap_mean_ci(daily.to_numpy(),n_boot=2000) if len(daily)>=20 else None)

def daily_pnl(t,dates):
 if t.empty:return pd.Series(0.,index=pd.Index([str(x) for x in dates],name='session_date'))
 return t.assign(ds=t.session_date.astype(str)).groupby('ds').pnl_usd.sum().reindex([str(x) for x in dates],fill_value=0)

def main():
 all_wf={1:[],2:[]};all_dates=set();current=[];foldmeta={};currentmeta={}
 for asset in ['NQ','ES']:
  directory=OUT/asset;cs=json.loads((directory/'configs.json').read_text())
  manifest=json.loads((directory/'manifest.json').read_text());dates=manifest['sessions']
  matrix=np.load(directory/'daily_stressed.npz')['daily'];neighbors=neighbor_indices(cs)
  market=load_primary(asset);cache={}
  def logs(config,ticks):
   key=(config['id'],ticks)
   if key not in cache:cache[key]=backtest(market,config,slip_ticks=ticks)
   return cache[key]
  folds=rolling_folds(dates,120,30,30,30);records=[]
  for fold in folds:
   tr=[dates.index(d) for d in fold.train_dates];va=[dates.index(d) for d in fold.validation_dates]
   selected,info=select(cs,matrix,tr,va,neighbors)
   records.append(dict(**fold.as_dict(),**info,selections=selected))
   all_dates.update(fold.test_dates)
   for rank,item in enumerate(selected):
    for ticks in [1,2]:
     frame=logs(item['config'],ticks);keep=frame.session_date.astype(str).isin(fold.test_dates)
     t=frame.loc[keep].copy();t['asset']=asset;t['config_id']=item['id'];t['fold_id']=fold.fold_id
     t['selection_priority']=rank;t['selection_score']=item['score']
     all_wf[ticks].append(t)
  foldmeta[asset]=records
  train=list(range(len(dates)-150,len(dates)-30));val=list(range(len(dates)-30,len(dates)))
  selected,info=select(cs,matrix,train,val,neighbors)
  currentmeta[asset]=dict(train_first=dates[train[0]],train_last=dates[train[-1]],validation_first=dates[val[0]],validation_last=dates[val[-1]],**info,selections=selected)
  current.extend(dict(item,asset=asset) for item in selected)
 current.sort(key=lambda r:(-r['score'],r['id']));current=current[:3]
 freeze={'utc':datetime.now(timezone.utc).isoformat(),'risk_budget':60,'selection_history_consumed':True,
         'reserved_checks_opened':False,'current_fleet':current,'asset_latest_selection':currentmeta,
         'plan_sha256':hashlib.sha256((ROOT/'PLAN.md').read_bytes()).hexdigest(),
         'engine_sha256':hashlib.sha256((ROOT/'engine_v2.py').read_bytes()).hexdigest()}
 (OUT/'current_frozen.json').write_text(json.dumps(freeze,indent=2))
 (OUT/'walkforward_selection.json').write_text(json.dumps(foldmeta,indent=2))
 dates=sorted(all_dates);summaries={}
 for ticks in [1,2]:
  fleet=merge_fleet(all_wf[ticks]);fleet.to_csv(OUT/f'walkforward_fleet_{ticks}tick_trades.csv',index=False)
  summary=trade_metrics(fleet,dates);summaries[str(ticks)]=summary
  daily_pnl(fleet,dates).to_csv(OUT/f'walkforward_fleet_{ticks}tick_daily.csv')
 (OUT/'walkforward_fleet_metrics.json').write_text(json.dumps(summaries,indent=2))
 print('Frozen current selections',[(x['id'],x['family'],round(x['score'],3)) for x in current])
 print('Walk-forward',json.dumps(summaries,indent=2))

if __name__=='__main__':main()
