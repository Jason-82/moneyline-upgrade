# Stink-bid study: brief for the research and design agents

## The user's request (verbatim, 2026-11-18)

"i haven't completely fleshed out this strategy, so i need your suggestions. what about a strategy that looks at
highly volatile yet 'solid' cryptos that I wouldn't mind owning, like HYPE, like NEAR, oprojects with real
revenues.... it looks at the charts and through some process figures out good levels to place 'stink bids'; that is,
bids that are way below current price, in the hopes of catching a momentary down wick to fill the trade. most of the
time the trades probably wouldn't fill, but maybe sometimes they would. and maybe it wouldnt even need to place any
trades for me, just analyze each chart and give me solid choices for the levels of the stink bids and I could place
the limit trade myself. can you help me elucidate/test?"

## Who the user is

- A US retail investor with "a decent amount of money" who trades crypto on Robinhood, uses the repo's MoneyLine
  indicator, and works on Windows in Git Bash (commands for the user must be Git Bash syntax).
- The repo (`/home/user/moneyline-upgrade`, branch `claude/youthful-goldberg-31vs8h`) is PUBLIC: never write account
  numbers, balances, positions, orders or anything personal.
- Repo convention: research -> pre-register (commit before results) -> build -> controls -> run -> audit -> write-up
  (report in `analysis_2026/reports/`, HANDOFF.md section, `analysis_2026/FINDINGS.md` entry). Report failures plainly.

## Facts already established (do not re-derive)

- **Robinhood catalog (read-only `get_currency_pairs`, 2026-11-18):** 92 tradable pairs. Limit orders are allowed on
  every pair except the stablecoins USDC/USDG. HYPE-USD is tradable (min size 0.001, max order 7,000 HYPE, price
  tick 0.001) but halted for New York residents. NEAR, SOL, ETH, BTC, AAVE, UNI, LINK, ENA, AERO, RAY, SKY, JTO, LDO,
  CRV, COMP, PYTH, ONDO, SUI, ZEC, XRP, DOGE, AVAX, ARB, OP, INJ, SEI, RENDER, FET, WLD, VIRTUAL, BNB and others are
  listed; PENDLE, JUP, TRX, MKR, GMX, CAKE, TIA, APT, TAO, HNT, KMNO, PUMP are not. Sub-agents must NOT call any
  Robinhood tool (the orchestrator does read-only calls itself); never place, review, preview or cancel orders.
- **Data access in this session:** the Binance public archive is reachable ONLY through the path-style S3 URL
  `https://s3-ap-northeast-1.amazonaws.com/data.binance.vision` (helpers `s3_ls`, `s3_get_zip_csv` in
  `analysis_2026/fetch_scalping_data.py`; checksum-verified kline builder in `analysis_2026/fetch_bb_data.py`). It has
  spot and USD-M futures klines at 1m/1h/1d (monthly and daily zips), aggTrades (trade-level, daily zips; e.g.
  NEARUSDT from 2020-10-14), and futures `metrics` (open interest etc.). HYPEUSDT spot 1m daily zips exist (2025+).
  Coinbase (api.exchange.coinbase.com), DefiLlama (api.llama.fi), Kraken, Bitstamp, CoinGecko and Hyperliquid are
  BLOCKED here by network policy (an environment that allows Coinbase and DefiLlama was created for a later
  session). Web research (WebSearch, the web-fetch agent) works for reading public pages.
- **The container is fresh:** the earlier studies' data under `data/` are gone (gitignored) and must be re-fetched if
  needed. Python 3.13, numpy 2.5, pandas 3, scipy, pyarrow, numba are installed. 4 CPUs, 15 GB RAM, ~30 GB disk free.
  New data go under `data/stinkbid/` (gitignored).
- **Related repo findings:**
  - Scalping study (HANDOFF 5.21 on this branch, `analysis_2026/reports/Scalping and market making.md`): passive
    limit orders in crypto lose to adverse selection in every band tested — directly relevant to resting bids.
  - BB-breakout study (HANDOFF 5.22, `analysis_2026/reports/Bollinger breakout replication.md`): drift-adjusted
    trade returns, month-cluster inference, luck benchmark of random entries, the 2025-10-10 crash (BTC −16%, DOGE
    −62% intraday on Binance perps) — its methods and engine (`analysis_2026/bb_*.py`) can be reused.
  - Mega-cap dip study on the default branch `origin/claude/add-price-data-csvs-MTD46` (read with `git show
    origin/claude/add-price-data-csvs-MTD46:analysis_2026/MEGACAP_DIP_PREREG.md` and HANDOFF.md section 5.21 there):
    buying top stocks after a 25% drop did no better than random entries.

## What the study must answer (for the design)

1. How often do deep down-wicks happen on such coins, at what depths, how fast do they revert, and are they
   market-wide (clustered) or coin-specific?
2. Conditional on a stink bid filling, what happens next (hours to months), against fair benchmarks (buying at
   market when the bid was placed; random entries; T-bills on idle cash; a slow-dip control at the same depth)?
3. Which level-finding process works best ("solid choices for the levels")?
4. Which exit/holding plan monetizes a wick: flip into the rebound, or own it?
5. Does a "solid / real revenue" filter avoid the knife-catching disasters (LUNA, FTT-like collapses)?
6. Would the bids actually fill for this user (US venue / Robinhood pricing, order size vs volume at the wick)?
7. What concrete, usable output can the user get (a level sheet per coin with historical fill odds and outcomes)?

## Ground rules for every agent

- No result peeking: on real data you may compute coverage, counts and FILL FREQUENCIES (how often a level would have
  been touched) — never post-fill returns, P&L or any outcome of a strategy. Outcomes are computed only after the
  pre-registration is committed.
- Write only your own files under `analysis_2026/research_notes/Stink bids/` (and data under `data/stinkbid/`,
  code under the module you are told to own). Do not commit or push. Do not edit other studies' files.
- Cite sources with links; mark unverified claims [U].
