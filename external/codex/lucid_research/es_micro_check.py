"""Post-freeze E028 actual-MES check; not an independent selection holdout."""
from pathlib import Path
import json,hashlib
import pandas as pd
from engine import prepare_data
import es_study

ROOT=Path(__file__).parent
OUT=ROOT/'results_es'/'micro_check'
OUT.mkdir(exist_ok=True)
MICRO=Path('/workspace/market_data/MES_topstep_1min.csv')
frozen_path=ROOT/'results_es'/'frozen_selection.json'
frozen=json.loads(frozen_path.read_text())
assert len(frozen['configs'])==1 and frozen['configs'][0]['id']=='E028'
c=frozen['configs'][0]
m=pd.read_csv(MICRO)
m.index=pd.to_datetime(m.pop('datetime'),utc=True)
m=prepare_data(m[['open','high','low','close','volume']])
main=es_study.load(include_holdout=True)
shared=sorted(set(main.session_date.unique()) & set(m.session_date.unique()))
assert all('2026-01-01'<=str(z)<='2026-04-15' for z in shared)
m=m.loc[m.session_date.isin(shared)].copy()
main=main.loc[main.session_date.isin(shared)].copy()
rows=[];logs={}
for label,data in [('MES_TopstepX',m),('ES_BARS_proxy',main)]:
    for cost,slip in [('baseline',1),('stress',2)]:
        t=es_study.run_backtest(data,c,slip_ticks=slip)
        t.to_csv(OUT/f'{label}_{cost}_trades.csv',index=False)
        logs[(label,cost)]=t
        stats=es_study.metrics(t,shared,q=2)
        rows.append(dict(dataset=label,cost=cost,quantity=2,shared_sessions=len(shared),first=str(shared[0]),last=str(shared[-1]),**stats))
r=pd.DataFrame(rows);r.to_csv(OUT/'metrics.csv',index=False)
# Price comparison is separate from strategy performance. Keep all days in
# outcome metrics; report roll-week differences without selecting around them.
px=main[['open','high','low','close']].join(m[['open','high','low','close']],lsuffix='_ES',rsuffix='_MES',how='inner')
px['close_diff']=px.close_ES-px.close_MES
px['roll_week']=((px.index.tz_convert('America/New_York').strftime('%Y-%m-%d')>='2026-03-15') & (px.index.tz_convert('America/New_York').strftime('%Y-%m-%d')<='2026-03-20'))
price_rows=[]
for label,pp in [('all',px),('outside_roll_week',px.loc[~px.roll_week]),('roll_week',px.loc[px.roll_week])]:
    price_rows.append(dict(sample=label,bars=len(pp),same_close_fraction=float((pp.close_diff==0).mean()),median_abs_close_difference=float(pp.close_diff.abs().median()),mean_abs_close_difference=float(pp.close_diff.abs().mean())))
pd.DataFrame(price_rows).to_csv(OUT/'price_audit.csv',index=False)
a=logs[('MES_TopstepX','baseline')].set_index('session_date')
b=logs[('ES_BARS_proxy','baseline')].set_index('session_date')
cols=['entry_time','direction','stop_points','pnl_usd','exit_reason']
a[cols].join(b[cols],lsuffix='_MES',rsuffix='_ES',how='outer').to_csv(OUT/'daily_trade_comparison.csv')
meta={'purpose':'Postselection price-proxy check, not independent validation or retuning',
      'frozen_config':c,'quantity':2,'shared_sessions':len(shared),'all_dates_retained_for_performance':True,
      'notes':['Both reports use same frozen E028 rules and2MES;1.24dollars commission per roundtrip perMES;1tick baseline/2tick stress per side.','The MES feed is actual micro futures bars from contributed TopstepX source;primaryESfeed is a separate contributor.','Raw feeds may follow different contracts inMarch15-20rollweek. All shared dates remain in strategy metrics;outside-roll comparison is only a price audit.','MinuteOHLC is insufficient to establish executable bidask or queue fills.'],
      'sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [MICRO,frozen_path,ROOT/'es_study.py',ROOT/'engine.py',ROOT/'es_micro_check.py']}}
(OUT/'provenance.json').write_text(json.dumps(meta,indent=2))
print(r.to_string(index=False));print(pd.DataFrame(price_rows).to_string(index=False))
