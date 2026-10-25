# S006 — NO VERIFIED IMPROVEMENT

Two cross-index forecasts were tested in120chronological rolling test sessions,60training/20test windows. All source dates are researcher-consumed2026; no independent confirmation or reserved-data access.

Adding other-index1/5minute returns worsened mean daily forecast-MSE relative to own-history controls: MES gain−0.09076basis-points-squared (95%blockCI−0.14309..−0.04645); MNQ gain−0.35002(CI−0.55537..−0.17801). Positive gain would mean improvement. Holm-adjustedone-sidedp for positive improvement=1 forboth. Internal bootstrap utility uses generic keymean_daily_pnl, but here its units are FORECASTERROR,notdollars.

| Stressed single-micro model | MES net | MNQ net |
|---|---:|---:|
| Own-history control |$20.06|−$1,829.90|
| Add synchronized other-index returns |$83.84|−$1,826.98|
| Prior-session other-index placebo |−$3.67|−$1,007.44|

Crossmodel hit$100 on1/120MESdays and7/120MNQdays. SparseMESpositiveP&L(9trades) does not override the failed incremental-information prediction test or dailygoal. MNQsignaltradedfrequently butlostaftercosts. No model passes the70%goal. Positions remainONEmicro,protective nominalrisk~$40,atmost2chronologicaltrades/day. Simultaneousentry/previous-exitbar overlaps are rejected conservatively; no retrospectivebesttrade selection.

Onlyone complete120-sessionlifecycle fits permodel-costcase. MESpaths expiredforinactivity;MNQpaths breached; noevalpasses orpayoutrequests. No positiveownercash/sustainablewithdrawalclaim. Commissions/slippageincluded; actualeval/reset/hostingfeesunknownandexcluded.

The mechanism tested was price-only low-frequency cross-indexincrementalinformation, NOT genuine orderflow, latencyarbitrage, ETF/futuresarbitrage orquoteOFI. Bar synchronization doesnot establishmillisecond executability; continuous-seriescontractmapping remains limited. Correlatedmodels and humaniterationreduceconfidence; no otherlag/hour/model sweep follows thisfailure.

Primarysources motivated a falsifiable extrapolation, not a promise: OFR2019 cross-assetorderflow/price discovery and Lo/MacKinlay1989 nonsynchronoussampling. These do not establish MES/MNQprice leadership.
