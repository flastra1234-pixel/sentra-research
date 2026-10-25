from pathlib import Path
import json
import numpy as np
import pandas as pd
from account_replay import rolling_trials,summarize_trials
R=Path(__file__).parent; O=R/'assessment';O.mkdir(exist_ok=True)
summary={}; daily_rows=[]
for tick in [1,2]:
 d=pd.read_csv(R/f'results/walkforward_fleet_{tick}tick_daily.csv');a=d.pnl_usd.to_numpy();n=len(a)
 t=pd.read_csv(R/f'results/walkforward_fleet_{tick}tick_trades.csv')
 s={'eligible_sessions':n,'net':float(a.sum()),'days_100':int((a>=100).sum()),'days_150':int((a>=150).sum()),'rate_100':float((a>=100).mean()),'rate_150':float((a>=150).mean()),'losing_days':int((a<0).sum()),'inactive_days':int((a==0).sum()),'zero_cash_baseline_net':0,'zero_gross_edge_fee_only_baseline':float(-1.24*t.quantity.sum())}
 rng=np.random.default_rng(20261025);idx=(rng.integers(0,n-4,size=(3000,int(np.ceil(n/5))))[:,:,None]+np.arange(5)).reshape(3000,-1)[:,:n]
 for threshold in [100,150]:s[f'rate_{threshold}_95_block_interval']=np.quantile((a[idx]>=threshold).mean(axis=1),[.025,.975]).tolist()
 for stage in ['evaluation','funded']:
  for reserve in [1500,1000]:
   trials=rolling_trials(t,d.iloc[:,0],horizon=120,stride=10,stage=stage,payout_profit=reserve)
   trials.to_csv(O/f'fleet_{tick}tick_{stage}_reserve{reserve}_lifecycles.csv',index=False)
   s[f'{stage}_reserve{reserve}']=summarize_trials(trials)
 summary[str(tick)]=s
# Every configuration: denominator includes ALL complete primary sessions.
grid={}
for asset in ['NQ','ES']:
 m=np.load(R/f'results/{asset}/daily_stressed.npz')['daily']; pnl=m[:,:,0];cs=json.load(open(R/f'results/{asset}/configs.json'))
 rate100=(pnl>=100).mean(axis=1);rate150=(pnl>=150).mean(axis=1)
 table=pd.DataFrame({'id':[x['id'] for x in cs],'eligible_days':pnl.shape[1],'days100':(pnl>=100).sum(axis=1),'days150':(pnl>=150).sum(axis=1),'rate100':rate100,'rate150':rate150,'inactive_days':(m[:,:,3]==0).sum(axis=1)})
 table.to_csv(O/f'{asset}_all_grid_daily_targets.csv',index=False)
 grid[asset]={'configurations':len(cs),'active':int((m[:,:,3].sum(axis=1)>0).sum()),'max_rate100':float(rate100.max()),'max_rate150':float(rate150.max()),'passing70pct100':int((rate100>=.7).sum()),'passing70pct150':int((rate150>=.7).sum())}
# Reconcile the original E028 costs using actual saved fills.
p=R.parent/'lucid_research/final_results'
b=pd.read_csv(p/'E028_holdout_baseline_trades.csv');s=pd.read_csv(p/'E028_holdout_stress_trades.csv')
assert np.allclose(b.pnl_usd,b.pnl_points*5-1.24)
assert np.allclose(s.pnl_usd,s.pnl_points*5-1.24)
x=b.merge(s,on=['entry_time','session_date','direction'],suffixes=('_base','_stress'),validate='one_to_one')
x['position_delta']=2*(x.pnl_usd_stress-x.pnl_usd_base)
x.to_csv(O/'E028_fill_reconciliation.csv',index=False)
audit={'MES_point_value':5,'contracts':2,'roundtrip_fee_per_contract':1.24,'tick_points':.25,'baseline_slippage_ticks_per_side':1,'stress_slippage_ticks_per_side':2,'matched_trades':len(x),'baseline_net':float(2*b.pnl_usd.sum()),'stress_net':float(2*s.pnl_usd.sum()),'delta':float(x.position_delta.sum()),'changed_exit_reason':int((x.exit_reason_base!=x.exit_reason_stress).sum()),'changed_exit_timestamp':int((x.exit_time_base!=x.exit_time_stress).sum()),'fee_delta':0,'naive_fixed_path_extra_slippage':-len(x)*2*5*.25*2,'explanation':'A fixed-path two-sided subtraction is not an exact reconciliation: stops/targets anchor to the slipped entry; targets pay modeled adverse exit slip; stress can change target/stop hits and exit times. Saved fill-by-fill PNL is authoritative. Target market-style execution is not a resting-limit model.'}
# Exact contribution split by changed vs same exit outcomes.
for changed in [False,True]:
 mask=(x.exit_reason_base!=x.exit_reason_stress)|(x.exit_time_base!=x.exit_time_stress)
 audit['delta_changed_paths' if changed else 'delta_unchanged_paths']=float(x.loc[mask==changed,'position_delta'].sum())
(O/'metrics.json').write_text(json.dumps({'daily_targets':summary,'grid':grid,'E028_audit':audit,'decision':'NO VERIFIED IMPROVEMENT','untouched_data_accessed':False},indent=2))
print(json.dumps({'grid':grid,'audit':audit,'fleet':{k:{a:v for a,v in z.items() if not isinstance(v,dict)} for k,z in summary.items()}},indent=2))
