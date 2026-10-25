# S001 — failed-auction availability bound (not an edge test)
Frozen before event results, October25,2026 America/New_York.

Question: can a strategy that trades only a predefined failed cash-open auction reach$100 on70%of all eligible days? Necessary condition:event exists on at least70%of eligible days. A signed-flow confirmation may remove events but cannot increase their count. No P&L is required for this upper-bound test.

Data: guarded HFD actualMES/MNQ1-minute aggregates, NY dates beforeOctober10,2026 only. These dates are researcher-consumed through prior2026work, not independent confirmation. No2024reserve orOct12–16performance access. Full390-minuteRTH session required. Overnight prior18:00 throughcurrent09:29 must contain all930minute timestamps; nofill. For a separate gap-conditioned variant require the actual previous business-day15:59close; holidays withoutit are missing, not filled.

Operational event at09:45, afterfirst15cashminutes: longfailure=first15low below observedovernightlow AND09:44close back aboveovernightlow; shortfailure=first15high aboveovernighthigh AND09:44close back belowovernighthigh. Both-sided failures are ambiguous and do not count as tradable; also report anyfailure coverage as a more generous upperbound.

Gapproxy variant requiresopeninggap direction match the failedextension and abs(open09:30-previouscashclose)>=0.25*overnightrange. This is a PRICEproxy, NOT actualpositioninventory. No candle signing, absorption, or syntheticquoteinformation.

Reportmissing-data exclusions and denominators, countsingle-sided/anyfailure/gap-conditioned events. Primaryunconditionedfailure upperbound versus70%eligible days. If below70%, rejectONLYthisevent-onlyarchitecture as standalone daily-targetsolution. Do not rejectconditional predictiveedge orfleetsleeve oncoveragealone. No automaticthresholdtuning. No tradingP&L,position sizing,oraccount-survival claim. Additionalrepeatedintradayauctionevents require a distinctpreregisteredmechanism,not relabelingthisone.
