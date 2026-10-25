# Final Nasdaq research branch: time-based entries

Registered before any 2026 strategy performance was examined. Earlier branches failed validation; this is a distinct hypothesis inspired by time-based approaches discussed in the source videos. All previous failures remain reported, and late-2025 validation is reused, so it is not an independent confirmation.

216 configurations: entry at 10:00/10:30/11:00/14:00 ET; direction long/short/opening_momentum (sign of latest completed close minus 09:30 open); stop 0.25/0.5/1 times the completed 15-minute opening range; target 1/2R; maximum hold 30/60/120 minutes. One MNQ, one trade daily, stops rejected outside 5..100 points, same tick rounding and baseline/stressed costs. Signal on minute immediately preceding entry, execution next-minute open. Mandatory 15:55 flatten. No overnight or news features.

Development Aug2024-Jun2025: >=50trades, PF>=1.10, closed drawdown<=800, positive stressed net, >=2/3positive development thirds. Retain top2 per direction mode by return/drawdown. Validation Jul-Dec2025: >=20trades, PF>=1.05, baseline+stress positive, drawdown<=800. Freeze top1 per direction mode, at most3. Final Jan-Oct2026 remains untouched until ALL branches frozen.

No more strategy search after this and the separately registered MES branch. Final assessment will report all frozen candidates. A positive historical final test is only a forward-test candidate, not authorization or evidence for live deployment. Final screening requires positive baseline AND stressed PNL, PF>=1.10, >=30holdout trades, and conservative intraday drawdown<=800. Account replay and bootstrap uncertainty will also be reported; no confidence claim based on overlapping replay starts.
