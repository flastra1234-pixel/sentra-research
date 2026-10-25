# LucidFlex 25K research rules snapshot

Research date: 2026-10-25 UTC. Official Help Center pages are the source. Product defaults changed this week: the newer Customization and Consistency pages take precedence over the older evaluation overview's blanket 50% wording. These are simulated evaluation and simulated funded rules, not the subsequent live account regime.

## Evaluation

- Starting balance: $25,000.
- Profit target: $1,250 (balance $26,250).
- Max Loss Limit amount: $1,000; EOD trailing.
- Evaluation max size: 2 minis or 20 micros. No evaluation scaling restriction.
- Consistency: largest single-day profit / total account profit <=40% standard; <=50% if that add-on was purchased. The 50% add-on has a small percentage cushion; do not assume a fixed $650 daily allowance in every scenario. For conservative modeling ignore this cushion.
- No separate minimum evaluation-day requirement was confirmed; consistency itself implies at least 3 profitable days at 40%, or 2 at 50%, absent losses. Do not model a one-day pass.
- No monthly rebilling or deadline; one-time evaluation fee, no funded activation fee. Current price not independently verified and not hard-coded.
- Daily Loss Limit is a purchase-time ON/OFF option, applies to both evaluation and funded; ON is a soft breach/lockout until next session, OFF means no firm DLL. Selection cannot be changed on the active account. Official help pages confirm optionality but did not print dollar amount. Secondary pages cite $600 for 25K from current plan cards; treat $600 as UNCONFIRMED until checked at purchase. Use DLL OFF as the clean baseline and a lower self-imposed daily risk limit.

Sources:
- https://support.lucidtrading.com/en/articles/12945790-lucidflex-evaluation-account (older overview; target/MLL/size)
- https://support.lucidtrading.com/en/articles/16226050-lucidflex-customization (updated this week; 40/50% and DLL options)
- https://support.lucidtrading.com/en/articles/12945805-lucidflex-consistency-percentage (updated this week; exact consistency formula)

## Drawdown mechanics (evaluation and simulated funded)

- Initial floor: $24,000.
- EOD high-water balance determines the next session's floor. A conservative formula: min($25,100, highest prior EOD balance minus $1,000), with high-water initialized to $25,000.
- Once balance exceeds $26,100, floor locks at $25,100.
- Any payout request immediately adjusts/locks the floor to $25,100 even if the normal trail has not reached that floor.
- Reaching the floor breaches the account. EOD describes when the floor ratchets; it does not establish permission to trade below that floor intraday. The official page says account balance reaching MLL breaches, but does not explicitly detail marked-to-market equity. For research model intraday equity touching the active floor as failure; label this conservative assumption.

Source: https://support.lucidtrading.com/en/articles/12945815-lucidflex-drawdown

## Simulated funded and payout

- Starts at $25,000; $1,000 EOD trailing loss allowance.
- No funded consistency rule.
- Contract scaling based on prior EOD simulated profit: $0-$999 => 1 mini/10 micros; $1,000+ => 2 minis/20 micros. Tier may fall after losses or payout. Updates EOD, not immediately when crossing a threshold intraday.
- Each payout cycle needs 5 separate trading days each making at least $100 profit, and positive net cycle profit. Day count resets after each approved payout.
- Minimum payout request: $500.
- Maximum request on 25K: min(50% of account profit, $1,000). The table specifies PROFIT despite a loose sentence above it saying account balance; do not compute 50% of $25,000 principal.
- Trader receives 90% of approved payout, firm 10%. Treat full gross request as balance reduction; e.g., $500 request gives trader $450 and reduces simulated balance by $500.
- No formally required payout buffer. Yet a minimum request needs at least $1,000 account profit under the 50% cap. At $26,000 balance, requesting $500 locks floor at $25,100 and leaves $400 headroom after deduction. Preserve a voluntary reserve rather than maximizing payout mechanically.
- DLL OFF: regular EOD requests. DLL ON: on-demand intraday requests possible from 18:00 to 15:45 ET; account paused for rest of day after intraday request.
- Payout requests cannot be edited/canceled; approval depends on continuing to maintain required balance.
- Maximum five sim payouts before live review/transition; risk team can move traders sooner. Do not extrapolate these simulated rules indefinitely after fifth payout.

Sources:
- https://support.lucidtrading.com/en/articles/12945795-lucidflex-funded-account
- https://support.lucidtrading.com/en/articles/12945808-lucidflex-scaling-plan
- https://support.lucidtrading.com/en/articles/12945796-lucidflex-payouts
- https://support.lucidtrading.com/en/articles/16226050-lucidflex-customization
- https://support.lucidtrading.com/en/articles/16558826-new-live-structure

## Automation, sessions and prohibited practices

- Automated trading systems and copiers are permitted; trader is responsible for errors and all normal rules still apply.
- News trading is allowed on Flex. It may produce slippage/velocity-logic effects. A strategy may voluntarily skip announcements, but do not incorrectly label that as a Flex firm prohibition.
- Flex positions flat by 16:45 New York time; trading resumes 18:00 Sunday-Thursday. Official page labels EST; use America/New_York for DST-aware simulation and flag literal EST ambiguity if necessary. Earlier holiday closes override ordinary schedule. Lucid auto-closes remaining positions and says merely holding to that auto-close does not fail an account.
- HFT is prohibited; definition is many orders in seconds/milliseconds, not a published universal numeric order cap.
- Microscalping is prohibited; review trigger is >50% of profit from trades held <=5 seconds. Genuine realistic scalping is allowed.
- Simulated-fill exploitation, price-discrepancy exploitation, latency/system-error exploitation prohibited.
- Cross-account opposite positions in same/correlated assets are prohibited, including across firms. A fleet should net signals centrally and avoid accidentally opposing accounts.
- Do not use martingale, artificial risk offsetting, or strategies designed to game simulated payouts.

Sources:
- https://support.lucidtrading.com/en/articles/11404728-other-trading-activities
- https://support.lucidtrading.com/en/articles/11404729-allowed-trading-times
- https://support.lucidtrading.com/en/articles/11404736-prohibited-high-frequency-trading
- https://support.lucidtrading.com/en/articles/11404742-prohibited-microscalping
- https://support.lucidtrading.com/en/articles/11404734-prohibited-hedging
- https://support.lucidtrading.com/en/articles/11404732-trade-with-integrity

## Simulation baseline recommendation (research choice)

Use 40% evaluation consistency and DLL OFF unless the user's existing account settings say otherwise; also report 50% sensitivity. Model $1,000 drawdown with intraday floor enforcement, EOD ratchet and payout-triggered floor locking. A $500 first payout requires $1,000 profit plus five $100 days; a more conservative payout can wait until at least $1,500 profit, leaving $900 headroom after a $500 request. Use 1-3 micros rather than sizing anywhere near permitted maximums. Price and evaluation/reset fees must be plugged in from the actual chosen checkout/account, not inferred from advertised discounts.

## Follow-up: official commissions, inactivity and agreement scope

- Official commissions table lists MNQ and MES $0.50 per side, hence $1.00 round trip; NQ and ES $1.75 per side, hence $3.50 round trip. It does not state in the viewed text whether this is an all-in rate inclusive of every platform/exchange surcharge. A baseline of $1.24 per micro round trip is a conservative research assumption rather than the official posted commission.
- Inactivity: at least one trade resulting in net profit or loss of $1 within every 30 calendar days is needed. Accounts without that activity are deemed abandoned and permanently deleted. Do not fabricate trades simply to retain an otherwise inactive research strategy; flag inactivity risk for sparse systems.
- The current Other Trading Activities article AND Lucid's general FAQ permit automated systems and copiers. A current public Flex account agreement was not located. An older Pro agreement's prior-written-approval clause cannot automatically be applied to Flex; actual account terms should be checked before deployment. This does not obstruct strategy research or simulation.

Sources:
- https://support.lucidtrading.com/en/articles/11508978-approved-products-and-commissions
- https://support.lucidtrading.com/en/articles/11404632-inactivity-policy
- https://lucidtrading.com/general-faq/
