# Slower-signal branch, before final holdout

Recorded after original297configurations and their1MNQsizing sensitivity failed late2025validation. No2026strategy performance has been examined. This expansion is hypothesis generation informed by those failures, not an independent replication. Late2025validation is reused;2026remains final historicaltest.

Fixed256new configurations, all1MNQ,1trade/day, daily-reset features and same one-minuteexecution/costmodel:
- ORB and failedORB: signalbars5/15min × openingrange15/30min × stop .25/.5ofrange × target1/2R × hold60/120min × endtime12:00/15:00 =64each.
- VWAPreversion: signalbars5/15min × band1/2ATR × stop1.5/2.5ATR × target1/2R × hold60/120min × endtime12:00/15:00 =64.
- EMApullback: signalbars5/15min × fast5/9,slow20 × stop1.5/2.5ATR × target1/2R × hold60/120min × endtime12:00/15:00 =64.

ATR5completed signalbars. Signalwindow starts09:45ET; OR signals only after completed openingrange. VWAPminimum3signalbars; EMAwarmup=max(3,fast)signalbars. Stops rounduptick and REJECT if<5or>100points. Fills next1minopen; same-barstopfirst, flats15:55. ORfractionstop ignoresATR multiplier. No news/direction/dayofweek filters.

Development2024-08-05..2025-06-30: >=50trades,PF>=1.10,closedDD<=800,stressnetpositive,>=2of3developmentperiodspositive. Rankreturn/DD;retain2perfamily. ValidationJul-Dec2025:>=20trades,PF>=1.05,positivebaseline+stressnet,closedDD<=800. Freeze1perfamily,atmost3. Same split finalJan-Oct2026;nochangesafterinspection. If no survivors, report failure and do not manufacture a strategy recommendation.

Combining allbranches produces553distinctstrategyconfigurations (297original+256slower) and additional1MNQsizing sensitivity onoriginal297. Allfailures retained. Reusedvalidation and multiplecomparisons reduce confidence; finalresults and actualforwardtesting determine nextstep.
