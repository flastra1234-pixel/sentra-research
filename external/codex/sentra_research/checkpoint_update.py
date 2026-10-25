from pathlib import Path
import json,hashlib
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
R=Path(__file__).parent
s1=json.loads((R/'experiments/S001/results.json').read_text());s3=json.loads((R/'experiments/S003/results.json').read_text());s4=json.loads((R/'experiments/S004/results.json').read_text())
ps=[('S003_'+k,v['bootstrap']['centered_bootstrap_p_value']) for k,v in s3['results'].items()]+[('S004_'+k,v['bootstrap']['centered_bootstrap_p_value']) for k,v in s4['results'].items()]
adj={};prev=0
for i,(name,p) in enumerate(sorted(ps,key=lambda v:v[1])):prev=max(prev,min(1,p*(len(ps)-i)));adj[name]=prev
(R/'experiments/exploratory_holm.json').write_text(json.dumps({'adjusted_p':adj,'limitation':'Four correlated exploratory comparisons; does not repair selection on spent data or human iteration.'},indent=2))
for tick in [1,2]:
 t=pd.read_csv(R/f'experiments/S004/{tick}tick_trades.csv');assert len(t)==201 and (t.quantity==1).all();assert(t.mae_usd<=t.pnl_usd+1e-8).all();assert(t.pnl_usd.min()>-60);assert(t.session_date.tolist()==pd.read_csv(R/'experiments/S003/MNQ_markouts.csv').date.tolist())
checkpoint={'updated':datetime.now(ZoneInfo('America/New_York')).isoformat(),'mission':'ACTIVE_RESEARCH_NOT_COMPLETE','execution':'This checkpoint is durable; no claim of background execution after turn/session ends.','owner_directive':'OWNER_DIRECTIVE.md','current_best_independently_verified_trading_baseline':None,'safe_cash_baseline':{'market_pnl':0,'withdrawals':0,'meets_owner_targets':False},'verified_improvement':False,
'completed':[{'id':'V1','outcome':'1025 configurations rejected','artifact':'/workspace/lucid_research/REPORT.md'},{'id':'V2','outcome':'12960 configurations,9024 active; rolling fleet negative; no owner-target qualification','artifact':'/workspace/lucid_research_v2/ASSESSMENT.md'},{'id':'S001','outcome':'Failed-auction single-event coverage22-27%; standalone70%target architecture rejected, predictive sleeve untested'},{'id':'S002','outcome':'Genuine source-side parser implemented;4fixture tests pass; fullflowhypothesis DATA-BLOCKED'},{'id':'S003','outcome':'MES fixed-hour drift negative;MNQ positive unprotected diagnostic,CIincludesloss andHolm4p>.05;notcandidate'},{'id':'S004','outcome':'Fixed20pt protectiveMNQvariant negative aftercost,5/9overlapping account pathsbreach,noevalpasses/requests;closed withoutstop/hour tuning'}],
'data_spent':['Prior primaryNQAug2024-Oct9/2026 andESJun2025-Oct9/2026','HFD2026MES/MNQpriorOct10 overnight/opening event availability and2-3am return/risk diagnostics'],
'reserved':['ES native3min2024/preJune2025 strategyperformance','HFD MES/MNQ Oct12-16/2026 strategyperformance'],
'queue':[{'priority':1,'id':'S005','task':'Nested incremental-information test: price-only overnight/failedauction baseline versus same baseline plus genuine signed flow','status':'BLOCKED_DATA','prerequisite':'Authorized contract-identified trade+quote history covering overnight andcashopen acrossmultiplechronologicalperiods;no purchase authorized','next_action':'Validate any supplied authorized export with flow_contract.py, thenpreregister event definitions,chronologicalsplits,costs,unchangedrisk anddaily/lifecyclepasscriteria BEFOREoutcomes'},{'priority':2,'id':'S006','task':'Assess whether synchronized cross-market price-discovery innovations contain incremental predictive information beyond own-market returns','status':'NEEDS_LITERATURE_AND_DATA_QUALIFICATION','prerequisite':'Establish economic direction/lead mechanism andcontract/time alignment;freezeonehypothesisandmultiplicityfamilybeforetesting;do not use remainingreserveddatafortuning'},{'priority':3,'id':'S007','task':'Conditional overnight drift using measuredpriorcloseimbalance,notprice-gap surrogate','status':'BLOCKED_DATA','prerequisite':'Actualpriorclose orderimbalance/quote-trade data,adequate historyincludingearlierregimes; current2026cannotreplicatepre2021decay'}],
'next_exact_action':'Read this checkpoint, DATA_ACCESS_AUDIT.md and LITERATURE.md; qualify S005 data if an authorized export becomes available, otherwise research/qualify S006 before any new performance test. Do not rerun V1/V2 or tune S004.',
'reproduction':['python -m unittest test_flow_contract.py -v','python experiments/S001/run.py','python experiments/S003/run.py','python experiments/S004/run.py','python checkpoint_update.py'],
'safety':{'live_orders':False,'purchases':False,'risk_increases':False,'invented_signing':False,'reserved_outcomes_accessed':False},'holms':adj}
# Preserve subsequent completed work and publication recovery state on rerun.
if (R/'CHECKPOINT.json').exists():
 previous=json.loads((R/'CHECKPOINT.json').read_text())
 seen={x['id'] for x in checkpoint['completed']}
 checkpoint['completed'].extend(x for x in previous.get('completed',[]) if x['id'] not in seen)
 for key in ['queue','next_exact_action','publication']:
  if key in previous: checkpoint[key]=previous[key]
(R/'CHECKPOINT.json').write_text(json.dumps(checkpoint,indent=2));print(json.dumps({'S004_integrity_checks':'PASS','holm4':adj,'checkpoint':str(R/'CHECKPOINT.json')},indent=2))
