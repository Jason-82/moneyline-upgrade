# Stink bids: how a deep resting bid works, and whether it would fill for this user

> **Scope.** Topic note for the stink-bid study (brief of 2026-11-18). It covers:
> 1. Robinhood crypto limit orders: types, life, routing, what triggers a fill, costs, cash, past crashes and outages.
> 2. Legal US venues for resting bids, and which list HYPE and NEAR.
> 3. Why wicks happen and why their depth differs by venue, with a descriptive check on the Binance archive.
> 4. The economics of a resting limit buy, kept short; the literature is in the sibling note `evidence.md` (sections 1-4).
>
> It ends with implications for the design (section 5) and open questions (section 6).
>
> **How this was verified (2026-11-18).**
> - **Direct fetching was blocked.** WebFetch could not resolve robinhood.com or en.wikipedia.org, so no further hosts were tried. Every web finding below comes from search-engine retrieval of page text; no full document was opened. Allowing robinhood.com in the session's network settings would let a later agent read Robinhood's pages directly.
> - **Tags:**
>   - **[A]** text returned from the primary source's own page or filing (Robinhood, an exchange, a regulator, a journal record), via search retrieval.
>   - **[S]** secondary source: press, research firms, reviews, blogs, preprints.
>   - **[U]** unverified, inferred, conflicting or from memory. Treat it as a lead.
>   - **[M]** the Robinhood MCP tool schemas loaded in this session. Only the descriptions were read; **no Robinhood tool was called.**
>   - **[R]** an existing repo file.
>   - **[T]** this session's own descriptive computation on the Binance public archive. It covers wick depth and fill capacity only, with no post-fill returns, P&L or strategy outcomes (ground rules). The method is in section 3.3 so it can be re-run. The scratch scripts sit in this session's scratchpad (`stinkbid_mech/scripts/wick_venues.py`, `wick_capacity.py`) and will not survive.
> - **No personal data.** No account, balance, position or order information was read or written.

---

## 0. Bottom line

1. **On Robinhood a stink bid is a 90-day order.**
   - Crypto limit orders are good-till-cancelled and lapse after 90 calendar days. IOC is never supported. The limit price must sit on the pair's tick; an off-tick price is rejected, not rounded [A][M].
   - A standing ladder therefore has to be re-placed every 90 days, and agent-placed orders need an in-app approval each time [R].
2. **What fills the order depends on the route. Neither route means "the Binance low touched my price".**
   - **Market-maker routing (the app default).** The order executes only when **Robinhood's ask** is at or below the limit [A]. The ask carries Robinhood's spread, about 0.96% above mid in Robinhood's own example, of which $0.95 per $100 goes to Robinhood (from 2026-06-15) [A]. Spreads widen in fast markets [S]. So the market mid must fall about 1% **below** the bid (more in a crash [U]) before it fills, and the fill price is still the limit.
   - **Exchange routing (Legend; optional in the app for supported coins).** The order rests on **Bitstamp's single order book**. Bitstamp is Robinhood's affiliate since June 2025. The order fills only if Bitstamp itself trades down to it; Robinhood warns it may not fill if the target price is available only on another venue [A]. Cost: 0.50% maker below $10k of 30-day volume, falling with volume; buying power is reserved at the 0.95% taker rate [A][R].
3. **Binance-perp wicks overstate what a spot venue prints, by an amount that varies by event** [T].
   - 2025-10-10: SOL spot −23.6% vs perp −36.0%; DOGE −61.8% vs −66.3%; NEAR (−46%) and AAVE (−71%) about equal.
   - 2021-05-19: ETH spot −44.1% vs perp −58.5%. 2024-08-05: within one point everywhere.
   - Single-venue prints can be absurd. On 2025-10-10, ATOM, IOTX and ENJ printed near $0 on Binance **spot**, while their perps and Binance's multi-venue index bottomed at −61% to −96% [T][S].
   - On the same day Coinbase's bitcoin price stayed at a premium to Binance's [S].
4. **Capacity at the very bottom is tiny** [T]. On 2025-10-10, the largest liquidation day on record, Binance spot (the world's deepest spot book) printed:
   - below 1% above the day's low: about $18k of sell-initiated NEAR and $16k of AAVE (BTC: about $15M);
   - below 5% above the low: about $263k NEAR and $64k AAVE.
   - A large bid at the extreme level would mostly not fill. Size has to shrink as the level deepens, i.e. a ladder.
5. **For HYPE the history is short and mostly offshore.**
   - Robinhood listed HYPE on 2025-10-23, after the 2025-10-10 wick. Coinbase followed on 2026-02-05; Binance.US had it from 2025-06-06 [S].
   - Binance's archive has HYPE perps from 2025-05-30 and HYPE spot only from **2026-09-24**, not 2025 as the brief assumed [T].
   - HYPE is halted on Robinhood for New York residents (brief).
   - Hyperliquid's own front end treats US persons as restricted [S]. It is not an option, and the restriction must not be circumvented.
6. **Economically, a resting bid is a put option given away free** (Copeland and Galai 1983 [A]).
   - The market exercises it against you when the seller knows more (adverse selection). Near the touch, the repo found fills followed by 5-19 bp adverse moves within 5 minutes [R].
   - It is also exercised when the seller is forced to sell.
   - It can only pay when fills come mainly from **forced, non-informational selling** that overshoots and later reverts as capital arrives: liquidation cascades, auto-deleveraging, stop-loss clustering, outages (Handa and Schwartz 1996; Duffie 2010; Coval and Stafford 2007; Nagel 2012 [A]).
   - A coin-specific collapse on news (LUNA, FTT) is the opposite case.
7. **Idle cash has a cost.**
   - 3-month T-bills yield about 4.2% (FRED, 2026-11-02) [A]. Robinhood Gold's sweep pays 3.35% [A].
   - Whether cash reserved for an open crypto limit order keeps earning sweep interest is not documented [U].
   - Non-execution is usually the bigger cost: the price never comes down and you never own the coin you wanted (Handa and Schwartz [A]).
8. **In crypto, fills at absurd prices have usually stood; equity venues have broken them.**
   - Trades stood after GDAX 2017 (ETH $0.10), Bitstamp 2019 (BTC −20%) and Binance.US 2021 (BTC $8,200) [S].
   - US equity venues broke 2010 flash-crash trades more than 60% away [A], and Blue Ocean cancelled overnight trades on 2024-08-05 [S].
   - Robinhood Crypto may treat a trade "substantially inconsistent with the prevailing price" as erroneous [U: clause-library text attributed to "RHC"; not confirmed on Robinhood's site].
9. **Round numbers decide queue position.**
   - BTC's Binance spot low was exactly $30,000.00 (2021-05-19), $49,000.00 (2024-08-05) and $102,000.00 (2025-10-10); the perp overshot below each [T].
   - Resting orders cluster at round numbers (Osler 2003 [A]; `evidence.md` §3). A bid at exactly the round number queues behind that crowd; a bid slightly above it fills first.

---

## 1. Robinhood crypto limit orders today

### 1.1 Order types, life, ticks and sizes

| Item | Finding | Tag / source |
|---|---|---|
| Order types | Market, limit, stop ("stop_loss": a stop-triggered market order, buy or sell) and stop limit; recurring buys in the app. | [M]; [A] [Buying and selling crypto](https://robinhood.com/us/en/support/articles/crypto-buying-and-selling/) |
| Limit order life | GTC only. "At Robinhood, a GTC order will expire after 90 calendar days." The MCP says "limit orders are always for 90 days". | [A] [Crypto glossary](https://robinhood.com/us/en/support/articles/robinhood-crypto-glossary); [A] [Why hasn't my crypto order filled?](https://robinhood.com/us/en/support/articles/why-hasnt-my-cryptocurrency-order-filled); [M] |
| Stop and stop limit life | gtc (90 days), gfd, gfw (7 days), gfm (30 days); default gfd. | [M] |
| Not available | IOC ("NEVER supported for crypto"). No post-only, hidden or reserve flag in the API. | [M] |
| Ticks | The limit price must be a multiple of the pair's `min_order_price_increment`; an off-tick price is rejected, not rounded. Quantity must be a multiple of the quantity increment. | [M] |
| HYPE-USD | Min 0.001 HYPE, max 7,000 HYPE per order, tick 0.001. Halted for NY residents. | brief (orchestrator's read-only `get_currency_pairs`, 2026-11-18) |
| Minimum notional | $0.01 on market-maker routing, $0.03 on smart exchange routing. | [A] [Buying and selling crypto](https://robinhood.com/us/en/support/articles/360001298246) (via search) |
| Position limits | A maximum cost basis per coin: $50M for BTC, ETH, DOGE and a few others, $20M for the rest; subject to change. | [A] same page (one version); [U] which coins |
| Dollar-amount limit orders | Quantity = dollar amount ÷ limit price at placement. A buy's debit is capped at the dollar amount (fee rounding ≤ 1 cent on "fee-priced accounts"). | [M] |
| Distance from market | No documented band rejects a crypto limit buy far below the market; a far bid simply stays pending. Equity limit orders can be rejected by unspecified "risk checks". | [A] [Why was my order rejected?](https://robinhood.com/us/en/support/articles/why-was-my-order-rejected) (equities); [U] crypto |
| Market-order collars | Buy up to +1%, sell up to −5%; outside the collar the order stays pending. Unfilled market orders may be cancelled after 2 minutes (US page). | [A] [Buying and selling crypto](https://robinhood.com/support/articles/crypto-buying-and-selling/); [M] |
| Trading hours | 24/7, with occasional scheduled maintenance windows (e.g. 2021-05-12, 23:00-23:15 PDT). A wick during maintenance cannot fill. | [A] [status page](https://status.robinhood.com/incidents/5bdv47dk6r5z); [U] current frequency |

### 1.2 Two routes, two fill rules

| | Market-maker routing | Exchange routing ("smart exchange routing") |
|---|---|---|
| Where it applies | Default in the mobile app and classic web [A]. | The only option on Legend [A]. Selectable in the app's order-type menu for supported coins, and it then stays the default [A] (sources conflict on the default [U]). It covered 66 of 90 US assets on 2026-09-08 [S]. The route cannot be changed after placement [S]. |
| What triggers a limit buy | "Your limit buy order will only execute when the crypto's ask price meets or falls below your limit price." [A] | Limit and stop-limit orders "will generally be routed to Bitstamp, a partner exchange and affiliate of Robinhood Crypto, to rest on Bitstamp's order book until your order becomes executable." [A] Market and stop orders go to whichever partner exchange gives the best price after fees; the partners include EDX Markets and Bitstamp [A][S]. |
| What you pay | No fee, but the spread is in the price. "For every $100 of notional crypto order volume executed through market maker routing, Robinhood Crypto receives $0.95 from its market maker" (as of 2026-06-15). Robinhood's example: a 0.96% buy spread, $0.95 of it to Robinhood [A]. | Maker fee if the order rests and is matched later; taker fee if it executes at once [A]. The tiers use trailing 30-day exchange-routed volume: 0.50% maker / 0.95% taker under $10k, down to 0.00% / 0.03% at $25M+ [A][R]. Buying power is sized at the taker rate, "since we can't guarantee your order will receive maker pricing" [A]. Maker pricing is still rolling out, and some accounts or API orders may get taker pricing [S][U]. |
| Main failure modes | The ask never comes down to the bid. Robinhood also lists "not enough order depth" and "a trading venue is unable to process your order" [A]. | Disclosure: "because limit and stop-limit orders rest on a single order book, there is a risk that these orders will not execute if the target price is only available" on another venue [A]. |
| Queue | None visible. The market maker's ask has to cross the bid. | Price-time priority on Bitstamp, starting when the order arrives there [U: standard for the venue]. Each 90-day re-placement goes to the back of the queue. |
| Which route agent orders use | Unknown [R]. The MCP mentions "fee-priced accounts" [M]. | Same. |

Sources: [Crypto order routing](https://robinhood.com/us/en/support/articles/crypto-order-routing/); [Crypto fee tiers](https://robinhood.com/us/en/support/articles/crypto-fee-tiers); [Robinhood Crypto Risk Disclosures (doc ID dated 2026-08-28)](https://cdn.robinhood.com/assets/robinhood/legal/Robinhood%20Crypto%20Risk%20Disclosures.pdf); [Robinhood Crypto Customer Agreement](https://robinhood.com/us/en/crypto-customer-agreement/); [RHC fee schedule PDF](https://cdn.robinhood.com/assets/robinhood/legal/rhc-fee-schedule.pdf) via `crypto_data_feasibility.md` §6 [R]; [CryptoSlate review](https://cryptoslate.com/crypto-exchanges/robinhood-exchange-review/) [S].

**What this means for a bid at price L:**

- **Market-maker route.** It fills when ask = mid × (1 + s) ≤ L, i.e. when mid ≤ L ÷ (1 + s). The buy spread s is about 0.96% in normal conditions, so the mid must fall about 1% through L.
  - s is wider in volatile or weekend markets [S], and nothing documents its size in a crash [U].
  - **The app's chart shows the mid** [A]. A chart that "touched" your price does not mean the order filled. This is exactly the confusion Robinhood's "why hasn't my order filled" page answers.
- **Exchange route.** It fills when a Bitstamp trade reaches L and the queue ahead of you at L is used up, or when Bitstamp trades through L. The cost is L × (1 + maker fee).
  - Bitstamp is one venue. A wick that happens only on Binance, or only on Hyperliquid, does not fill it.
- **In both cases the fill is at L "or better"** [A]. Whether a gap through L gives price improvement on the market-maker route is not documented [U].

### 1.3 How Robinhood prices crypto

- **The app shows the mid.** "For crypto, the price we show in the app is the mark price, which is the midpoint between the bid price and the ask price" [A] ([glossary](https://robinhood.com/us/en/support/articles/robinhood-crypto-glossary); [Why do the crypto mid price and order price differ?](https://robinhood.com/us/en/support/articles/crypto-prices-differ)).
- **Market-maker quotes.** On the default route the bid and ask come from market makers Robinhood does not name [A]. How they hedge, and on which venues, is not disclosed [U].
- **Bitstamp.**
  - Robinhood closed its $200M cash acquisition of Bitstamp in early June 2025; Robinhood's newsroom post is dated 2025-06-02 ([Robinhood newsroom](https://robinhood.com/us/en/newsroom/robinhood-completes-acquisition-of-bitstamp/) [A]; [The Block](https://www.theblock.co/post/356701/robinhood-bitstamp-acquisition) [S]).
  - At closing Bitstamp was "already connected to Robinhood Legend and its Smart Exchange Routing offering" [S].
  - In the US it operates through licensed entities, but some states are reported as excluded (Hawaii, Nevada) [S] ([review](https://wherelegalcrypto.pages.dev/exchanges/bitstamp/review/)).
- **No price history through the MCP.** It has no historical crypto candles [R] (`AGENTIC_TRADING_PLAN.md` §1). Robinhood's past quotes cannot be reconstructed, so any backtest of Robinhood fills uses other venues as proxies (section 5).

### 1.4 Cash: what is reserved and what it earns

- **Reservation.** Open buy orders reduce buying power. On exchange routing the hold includes the taker fee [A]. The Agentic account is cash or "limited margin" with no borrowing [R], so every bid must be fully cash-backed. Whether crypto can be bought on margin in any Robinhood account: [U].
- **Interest.**
  - Interest is paid on settled cash swept to program banks [A]. For stock purchases, Robinhood says cash keeps earning "until the trade settles" [A].
  - **No source says whether cash reserved for an open crypto limit order stays in the sweep** [U].
  - A practical check: place a large, far-away bid and see whether the app's "cash earning interest" figure drops.
  - Rates: Gold standard APY 3.35% (Feb 2026, still quoted in July 2026); 5% or 7% promotions on the first $10k for 60 days [A][S] ([APY page](https://robinhood.com/us/en/support/articles/earning-interest/); [Gold boost](https://robinhood.com/us/en/support/articles/yes-gold-apy-superboost/)).
- **Benchmark.** The 3-month Treasury yielded 4.21% on 2026-11-02 ([FRED DGS3MO](https://fred.stlouisfed.org/series/dgs3mo)) [A]. Keeping $100k in bids for a year therefore costs:
  - about $4.2k against T-bills if the reserved cash earns nothing;
  - about $0.9k if it still earns 3.35% (arithmetic).

### 1.5 Robinhood in past crashes and volatile markets

| Date | What happened | Tag / source |
|---|---|---|
| Jan 2021 | Robinhood reported a "major outage" in crypto trading as bitcoin slid below $30k. Within days, as bitcoin surged past $37k, it restricted crypto trading (instant buying power) citing extraordinary market conditions. Restrictions can come in surges as well as crashes. | [S] [The Block](https://www.theblock.co/news/ecosystems/2021-01-27-robinhood-crypto-outage-bitcoin-slide-92779); [S] [The Block](https://www.theblock.co/linked/93097/); [U] exact dates |
| 2021-04-15 | "Major outage" in US crypto trading. | [S] [BNN Bloomberg](https://www.bnnbloomberg.ca/robinhood-restores-crypto-trading-after-major-outage-1.1591004) |
| 2021-05-04 | Partial crypto outage of about an hour during the DOGE spike; stocks unaffected. | [S] [Fortune](https://fortune.com/2021/05/04/robinhood-crypto-outage-dogecoin-reaction-memes/); [A] [status](https://status.robinhood.com/incidents/6r0wrcty5v8h) |
| 2021-05-19 | No Robinhood-specific outage report found. Coinbase and Binance had outages; Binance stopped transaction-level reporting for 40 minutes mid-crash. | [S] [The Block](https://www.theblock.co/news/markets/2021-05-19-exchanges-outages-market-volatility-eth-105366); [A] [Baumgartner and Güttler, IWH DP 25/2022](https://www.iwh-halle.de/en/publications/detail/bitcoin-flash-crash-on-may-19-2021-what-did-really-happen-on-binance) |
| Jul 2021 | Beta code showed a planned "price volatility protection" that could override orders on fast price spikes; whether it launched is unknown. | [S] [Decrypt](https://decrypt.co/77026/robinhood-tackle-crypto-volatility-overriding-some-trades-report); [U] |
| 2022-02-25 | Display error: the app showed BTC about $4k below market for about an hour. Orders could be entered but did not fill at the displayed price. | [S] [The Block](https://www.theblock.co/linked/135438/bitcoin-price-briefly-shown-at-steep-discount-on-robinhood-app); [S] [Benzinga](https://benzinga.com/z/25833672) |
| 2024-08-05 | Equities only: Robinhood's 24 Hour Market venue (Blue Ocean ATS) suspended overnight trading and **cancelled trades** from about 1:45 to 3:06 a.m. ET. No crypto effect found. | [S] [Markets Media](https://www.marketsmedia.com/blue-ocean-ats-resumes-after-cancelling-trades); [S] [Bloomberg](https://www.bloomberg.com/news/articles/2024-08-06/biggest-overnight-stock-venue-suspends-trading-after-volatility) |
| 2025-10-06 | Platform-wide outage at the Monday open. | [S] [CoinGape](https://coingape.com/robinhood-outage-reported-by-users-hood-stock-drops) |
| 2025-10-10 | No Robinhood-specific outage or halt report found for the crash. HYPE was not yet listed. | [U] (absence of evidence) |
| 2025-10-20 | AWS outage: Robinhood and Coinbase users unable to trade for more than two hours. | [S] [Cointelegraph](https://cointelegraph.com/news/amazon-aws-outage-coinbase-app-robinhood) |
| 2026-02-19 | A headline "Bitcoin's price crashed to $35K on Robinhood today" has no article text; it may be the 2022 display error recycled. | [U] |

Robinhood says exchange-imposed halts in equities, options and futures do not directly affect crypto trading ([trading halts](https://robinhood.com/us/en/support/articles/trading-halts)) [A]. Its catalog can carry per-pair halts (the HYPE halt for NY), per the MCP description of `get_currency_pairs` [M]. Whether open orders can be cancelled during a pair halt: [U].

### 1.6 Did Binance-perp wicks appear in Robinhood's prices?

**This cannot be measured here.** Robinhood offers no crypto history through the MCP [R], and Bitstamp, Coinbase and Kraken are blocked from this session (brief). The indirect evidence all points the same way: Robinhood's prices are shallower than Binance-perp prices.

- **Robinhood fills off its own ask or Bitstamp's book, not Binance** (section 1.2) [A].
- **The 2025-10-10 Binance-only prints did not happen elsewhere.**
  - ATOM, IOTX and ENJ "crashed to zero" on Binance "despite the tokens staying well above $0 on other centralized crypto exchanges" ([Cointelegraph](https://cointelegraph.com/news/why-did-some-altcoins-on-binance-crash-to-zero)) [S].
  - Binance blamed a UI and decimal-place display issue ([Cointelegraph](https://cointelegraph.com/news/binance-tokens-not-crash-0-display-issue); [Finextra](https://www.finextra.com/blogposting/29592/system-stress-market-makers-and-the-largest-crypto-liquidation-ever-regulatory-lessons)) [S]. Yet the archive's 1-minute spot klines, which are built from trades, do show lows of $0.001, $0.000001 and $0.00001 [T].
- **Binance's own index was much shallower.** Binance's multi-venue index for the ATOM, IOTX and ENJ perps fell 62-96%, not 100% [T].
- **Coinbase traded at a premium to Binance.** CryptoQuant's Coinbase Premium Index (Coinbase BTC/USD vs Binance BTC/USDT) reached 0.182 on 2025-10-10, its highest since March 2024 ([CryptoQuant](https://cryptoquant.com/insights/quicktake/68ec26489792d0004764379b-Bitcoins-Coinbase-Premium-Hits-19-Month-High-During-Crash-Signaling-Major-Instit)) [S]. SOL was "at one time roughly $20 lower on Binance than on Coinbase" ([Yahoo Finance](https://finance.yahoo.com/news/heres-investors-know-weekends-massive-170219939.html)) [S].
- **HYPE overshot on the Binance perp.** HYPE's reported low was $23.50 [S] ([CCN](https://www.ccn.com/analysis/crypto/hyperliquid-price-aster-dex/)). The Binance perp printed $21.03 and Binance's index $23.74 [T].
- **The opposite also happens.** Bitstamp itself had a venue-only crash on 2019-05-17 (section 3.4). A Bitstamp-resting bid can fill when nothing happens elsewhere.

**Working assumption for the design:**
- Robinhood's attainable lows are at most as deep as a multi-venue spot composite, and usually shallower than Binance perps.
- Under market-maker routing they are a further ~1% (plus the crash spread) shallower.

---

## 2. Legal venues for a US resident's resting bids

| Venue | HYPE spot | NEAR spot | Resting limit orders | Maker fee, entry tier | Notes |
|---|---|---|---|---|---|
| **Robinhood** (app; Legend) | Yes, from 2025-10-23 [S] ([The Defiant](https://thedefiant.io/robinhood-adds-hype-for-spot-trading)); halted for NY residents (brief) | Yes (brief); listing date not confirmed, NY included [S][U] ([Bloomingbit](https://en.bloomingbit.io/feed/news/108972)) | GTC 90 days; two routes (section 1.2) | Spread ~0.96% (market-maker route) or 0.50% maker (exchange route) [A] | Agentic trading not available in NY [R]. HYPE and NEAR exchange-routing eligibility unknown [U]. |
| **Coinbase Advanced** | Yes: roadmap 2026-01-29, trading 2026-02-05 [S] ([KuCoin news](https://www.kucoin.com/news/articles/coinbase-to-list-hype-for-spot-trading-market-opportunities-and-risks-amid-hyperliquid-ecosystem-surge); [Coinbase price page](https://www.coinbase.com/price/hyperliquid)) | Yes, since 2022 [S][U] | Limit GTC, or GTD with an end time; optional `post_only` [A] ([API orders guide](https://docs.cdp.coinbase.com/coinbase-app/advanced-trade-apis/guides/orders); [edit order](https://docs.cdp.coinbase.com/api-reference/advanced-trade-api/rest-api/orders/edit-order)) | 0.50% maker / 0.90% taker (US, from 2026-09-16; tiers from $10k) [S] ([CryptoDaily](https://cryptodaily.co.uk/2026/09/coinbase-advanced-fees-usdc-vip-tiers)) | Prices must be multiples of the product's quote increment [A]. Limit orders are subject to a "Price Protection Point" ([trading rules](https://www.coinbase.com/ru/legal/trading_rules)) [A]; its size is unknown [U]. Pairs can be put in limit-only mode [S] ([example](https://cryptobriefing.com/coinbase-grass-usd-limit-only-mode/)). In 2019 Coinbase said trades are final under its rules [S]. |
| **Kraken Pro** | Spot listed late Jan 2026 [S]; **US eligibility unclear** [U] ([crypto.news](https://crypto.news/hyperliquid-kraken-parent-explore-u-s-futures-launch/)) | Yes [U] | Limit with post-only option [S] | Tier 1: 0.40% maker / 0.80% taker (from 2026-07-09) [A] ([Kraken blog](https://blog.kraken.com/product/pro/new-kraken-pro-fee-tiers)) | Also US HYPE exposure via CME-listed futures (Kraken Derivatives US) and perps through Bitnomial (from June 2026) [S]. These are not spot bids. |
| **Bitstamp** (by Robinhood) | Not confirmed [U] | Not confirmed [U] | Limit, market, stop, trailing stop, instant [S] | 0.30% maker / 0.40% taker [S][U] | Most US states [S]. This is the book Robinhood's exchange-routed limit orders rest on. |
| **Binance.US** | Yes, from 2025-06-06 [S] ([Crypto Briefing](https://cryptobriefing.com/hyperliquid-hype-spot-trading-binance/); [Messari](https://messari.io/project/hyperliquid/markets)) | Yes [S] | Limit [U: GTC not checked] | **0% maker / 0.02% taker** on all spot pairs from 2026-04-22 [A] ([Binance.US blog](https://blog.binance.us/zero-fee-trading/)) | Not available in NY and some other states; counts vary (16 states excluded, or licences in 32 states) [S] ([Motley Fool review](https://www.fool.com/money/cryptocurrency/binanceus-review/)). Volumes described as "abysmal" [S] ([The Block](https://www.theblock.co/amp/post/370097/crypto-exchange-binance-us-cuts-fees-as-trading-volumes-remain-abysmal)). |
| **US spot HYPE ETFs** | 21Shares THYP (Nasdaq, 2026-05-12); Bitwise BHYP (NYSE, 2026-05-15) [S] ([The Block](https://www.theblock.co/post/401047/first-ever-hyperliquid-etf-launches-posts-very-solid-first-day-of-trading-analyst)) | — | Ordinary equity limit orders | $0 commission at Robinhood; fund fee about 0.30% a year [S] | **Cannot catch most crypto wicks.** The 2025-10-10 lows came at about 21:20 UTC (17:20 ET) on a Friday, outside the regular session. Thin extended-hours ETF books need not track a 10-minute crypto wick [U]. |
| **Hyperliquid** (on-chain) | — | — | — | — | Its terms of use treat anyone residing, located or incorporated in the US, and US citizens, as "Restricted Persons", enforced by front-end geofencing [S] ([Datawallet](https://www.datawallet.com/crypto/is-hyperliquid-available-in-the-usa); [OneKey](https://onekey.so/blog/ecosystem/geo-block-hyperliquid-dydx-us/)). Using a VPN to get around this violates the terms [S]. **Not an option for this user; do not circumvent.** Regulated US routes are in development: ICE with Trade[XYZ] (announced 2026-10-29, needs CFTC approval), and Kraken's parent Payward planning HIP-3 perps for US clients [S] ([CryptoTimes](https://www.cryptotimes.io/2026/10/29/hyperliquid-token-hype-price-rises-14-after-ice-and-tradexyz-announces-regulated-u-s-perpetuals-venue/)). These are derivatives, not spot. |

**Takeaways:**
- **Zero maker fee.** Of the legal US spot venues, only Binance.US has it without a volume tier. Its books are thin and it is not available in New York.
- **Cheapest route for a Robinhood user.** Exchange routing (0.50% maker at the entry tier) beats the ~0.96% embedded spread, but only for coins that support it. It also changes which book the bid can fill on: Bitstamp only.
- **HYPE history on US-reachable spot venues is short.** It is about 13 months on Robinhood and about 9 on Coinbase, so most of HYPE's wick history comes from Binance perps (from 2025-05-30) or venues blocked here.

---

## 3. Why wicks happen, and why they differ by venue

### 3.1 Mechanisms

- **Liquidation cascades.**
  - Leveraged perp longs pass maintenance margin. The exchange's liquidation engine sends forced, price-insensitive sell orders. Their impact pushes the price into the next band of liquidation prices.
  - This chain is described in minute-level studies of seven BTC cascades, including 2025-10-10 ([arXiv 2607.27070](https://arxiv.org/pdf/2607.27070); [arXiv 2608.03616](https://arxiv.org/html/2608.03616)) [S: preprints].
  - On 2025-10-10, more than $19B was liquidated in about 24 hours (CoinGlass), and Binance's one-per-second liquidation feed undercounts it [S] ([CoinShares](https://coinshares.com/us/insights/knowledge/billions-in-liquidations-what-happened/); [Datawallet](https://www.datawallet.com/crypto/october-10-crypto-crash-explained)).
- **Mark-price design.**
  - Binance liquidates on the **mark** price, not the last trade, "to avoid unnecessary liquidations and to combat market manipulation" ([Binance FAQ](https://www.binance.com/en-AE/support/faq/360033525271)) [A].
  - A delayed or stale mark lets the executable price overshoot the liquidation boundary ([MDPI 2026](https://www.mdpi.com/2571-9394/8/5/76)) [S].
  - On 2025-10-10, the mark "undershot both spot and futures" ([Lim, SSRN 6579278](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6579278)) [S; abstract only].
  - In this session's archive check, the 1-minute mark low sat 1.8% above the last-trade low on SOL and 5.7% on DOGE [T], matching the repo's hourly check [R] (`data_inventory.md`).
- **Auto-deleveraging (ADL).**
  - When insurance funds or backstop vaults run out, exchanges force-close profitable opposite positions.
  - On 2025-10-10, Hyperliquid ran its first cross-margin ADL in over two years, closing about $2.1B of positions ([arXiv 2512.01112](https://arxiv.org/pdf/2512.01112)) [S]. Hedged shorts were cut too ([FTI Consulting](https://www.fticonsulting.com/insights/articles/crypto-crash-october-2025-leverage-met-liquidity)) [S].
  - ADL removes hedges and the natural buyers that short-covering would supply.
- **Thin books and market-maker withdrawal.**
  - Visible depth fell from about $103.6M to $0.17M (−98%) per Amberdata ([Datawallet](https://www.datawallet.com/crypto/october-10-crypto-crash-explained)) [S].
  - At the peak, meaningful bids appeared only 4-10% from mid, mainly on Binance, Crypto.com and Kraken; Coinbase had essentially nothing within 0.1% of mid. These are Kaiko figures as relayed by secondary summaries ([Kaiko](https://research.kaiko.com/insights/cryptos-pricing-problem-laid-bare)) [S][U: exact figures].
  - Wintermute measured the median token down about 54% ([Molly White](https://www.citationneeded.news/anatomy-of-a-crypto-meltdown/)) [S].
  - This is the general finding that endogenous liquidity providers keep supplying in a single-stock extreme move but **demand** liquidity when many assets move at once ([Brogaard et al. 2018, JFE 128(2)](https://econpapers.repec.org/RePEc:eee:jfinec:v:128:y:2018:i:2:p:253-265)) [A].
- **Venue-specific collateral and pricing.**
  - Binance valued USDe, wBETH and BNSOL collateral off its own order book. USDe printed about $0.66 on Binance vs about $0.90-0.95 elsewhere, between 21:36 and 22:16 UTC [S] ([TradingView/NewsBTC](https://www.tradingview.com/news/newsbtc:edd5e2f2a094b:0-crypto-crash-triggered-by-binance-margin-exploit-uphold-research-chief-claims/); [Kaiko](https://research.kaiko.com/insights/cryptos-pricing-problem-laid-bare)).
  - Binance reimbursed $283M [S].
- **Arbitrage lag.**
  - Cross-exchange gaps open when moving capital between venues is costly or slow ([Makarov and Schoar 2020, JFE 135(2)](https://econpapers.repec.org/RePEc:eee:jfinec:v:135:y:2020:i:2:p:293-319)) [A].
  - In a crash, arbitrageurs hit risk limits and transfers lag, so a venue's book can run far from the others for minutes. The Binance-only ATOM, IOTX and ENJ prints are the extreme case [S][T].
- **Single large orders, stop clusters and bugs.**
  - GDAX 2017: one sell order, then about 800 stop-loss and margin liquidations [S].
  - Bitstamp 2019: a 5,000 BTC sale [S].
  - Binance.US 2021: a client's algorithm bug [S].
  - Stop-loss orders cluster just beyond round numbers, which speeds a fall once a level breaks (Osler 2003) [A].
- **Outages.** BitMEX went offline 02:16-02:40 UTC on 2020-03-13 during the cascade [S] ([Cointelegraph](https://cointelegraph.com/news/bitmex-denies-it-made-bitcoin-price-drop-to-37k-after-going-offline)). Binance went dark on transaction data for 40 minutes on 2021-05-19 [A].

### 3.2 Why Binance-perp wicks are usually deeper than spot, and US spot shallower still

- **The forced selling happens in the perp book.** Leverage sits in perps, so liquidation orders and ADL hit the perp book first. Spot moves only through arbitrage, which lags in a crash (section 3.1).
- **Perp depth has its own withdrawal.** Perp makers hedge on spot and pull quotes when they cannot. The perp book can then empty further than the spot book, e.g. SOL on 2025-10-10: perp −36.0% vs spot −23.6% [T].
- **US retail spot venues carry little forced flow.** Retail spot at Robinhood, Coinbase or Bitstamp is unlevered, or lightly levered where margin exists. Falls there are driven by arbitrage from offshore perps and by discretionary panic.
  - On 2025-10-10 Coinbase BTC traded at a premium to Binance [S] (section 1.6).
- **It is not a law.**
  - On 2024-08-05 spot and perp lows were within about one point for every coin checked [T].
  - On 2025-10-10 the deepest prints of ATOM, IOTX and ENJ were on Binance **spot**, not perps [T].
  - Bitstamp crashed on its own in 2019 [S].
  - The gap is event-specific and coin-specific, so the study should measure it rather than assume a constant.

### 3.3 This session's archive check (descriptive only)

**Method:**
- Binance public archive, through the repo's S3 helpers (`analysis_2026/fetch_scalping_data.py`).
- **Kline files.**
  - 1-minute spot klines: `data/spot/daily/klines/{S}/1m/`.
  - USD-M perp files: `klines`, `markPriceKlines` and `indexPriceKlines` under `data/futures/um/daily/`.
- **Depth measure.** Each low is measured against the 00:00 UTC open of the same day.
- **Index price.** Binance computes it from several spot venues; its constituents and weights are [U].
- **Capacity.**
  - Source: the daily `aggTrades` files.
  - Measure: the USD notional of **sell-initiated** trades (`is_buyer_maker = true`) that printed strictly below the day's low × (1 + x).
  - Reading: roughly the most a new bid at that level could have absorbed on that venue, ignoring the queue already resting at that price.
- **No post-low returns were computed.**

**Table A — 2025-10-10. Low vs the 00:00 UTC open (all lows between 21:19 and 21:29 UTC):**

| Coin | Spot | Perp (last trade) | Perp mark | Binance index | Spot low | Perp low |
|---|---|---|---|---|---|---|
| BTC | −16.2% | −16.5% | −16.2% | −15.7% | 102,000.00 | 101,516.5 |
| ETH | −21.4% | −22.1% | −21.5% | −21.4% | 3,435.00 | 3,400.00 |
| SOL | −23.6% | **−36.0%** | −34.9% | −30.4% | 168.79 | 141.28 |
| NEAR | −46.2% | −46.4% | −46.0% | −45.4% | 1.550 | 1.543 |
| HYPE | no Binance spot until 2026-09-24 | −52.2% | −51.7% | −46.0% | — | 21.029 |
| AAVE | −71.0% | −70.8% | −70.1% | −70.1% | 79.51 | 80.01 |
| DOGE | −61.8% | −66.3% | −64.3% | −61.4% | 0.0950 | 0.08385 |
| SUI | −83.6% | −83.4% | −83.0% | −83.0% | 0.5597 | 0.5669 |
| ENA | −76.0% | −76.6% | −76.0% | −75.3% | 0.1313 | 0.1280 |
| ATOM | **−99.98%** | −64.0% | −62.9% | −61.6% | 0.001 | 1.46 |
| IOTX | **−100.0%** | −95.0% | −95.0% | −96.4% | 0.000001 | 0.00119 |
| ENJ | **−99.98%** | −63.2% | −66.2% | −68.8% | 0.00001 | 0.0225 |

**Table B — earlier events. Low vs the 00:00 UTC open, spot / perp (low price in brackets):**

| Coin | 2021-05-19 | 2024-08-05 |
|---|---|---|
| BTC | −30.0% (30,000.00) / −33.1% (28,688.0) | −15.8% (49,000.00) / −15.9% (48,888.0) |
| ETH | −44.1% (1,888.00) / **−58.5%** (1,400.73) | −21.5% (2,111.00) / −21.4% (2,112.00) |
| SOL | −52.7% (26.50) / −54.9% (25.228) | −20.5% (110.00) / −21.1% (109.162) |
| NEAR | −48.9% (2.900) / −50.3% (2.8242) | −25.6% / −25.6% |
| AAVE | −44.3% (350.00) / **−59.6%** (253.56) | −21.6% / −21.6% |
| DOGE | −55.6% / −58.9% | −22.4% / −22.5% |

On 2021-05-19 Binance's index fell less than Binance spot for SOL (−45.7% vs −52.7%) and AAVE (−41.9% vs −44.3%) [T]. Binance's own books were the deep ones that day.

**Table C — fill capacity on 2025-10-10.** Sell-initiated USD notional that printed strictly below the day's low × (1 + x), on Binance [T]:

| Instrument (day's volume) | +0.5% | +1% | +2% | +5% | +10% |
|---|---|---|---|---|---|
| NEAR spot ($221M) | $15k | $18k | $56k | $263k | $691k |
| NEAR perp ($786M) | $38k | $262k | $312k | $864k | $5.3M |
| AAVE spot ($97M) | $0.7k | $16k | $18k | $64k | $120k |
| AAVE perp ($550M) | $3k | $12k | $26k | $690k | $1.2M |
| SOL spot ($1.93B) | $0.4M | $3.4M | $6.4M | $27M | $133M |
| SOL perp ($12.4B) | $0.3M | $2.0M | $11M | $58M | $127M |
| BTC spot ($7.35B) | $6.0M | $15M | $32M | $195M | $1.03B |
| BTC perp ($45.1B) | $49M | $114M | $245M | $1.21B | $5.46B |

**Reading:**
- **Depth and size trade off steeply.** On the biggest forced-selling day on record, Binance spot could have filled only about $15-20k of NEAR or AAVE at a level within 1% of the eventual bottom, and a few hundred thousand dollars 5% above it.
- **US venues are thinner** [S][U]. Binance.US's market share was reported near 0.2% [S] ([Yahoo Finance](https://finance.yahoo.com/news/binance-us-cuts-fees-near-205834438.html)), and Bitstamp's crash-time depth is unknown.
- **So the size that can fill at the extreme is a hard limit**, not a detail.

**Round numbers:**
- BTC's spot low landed exactly on a $1,000 multiple in all three events. SOL ($110.00), AAVE ($350.00), NEAR ($2.900) and DOGE ($0.0950) spot lows were also round.
- Perp lows overshot below them (28,688; 48,888; 101,516.5) [T].
- This is consistent with large resting bids absorbing the spot sweep at round prices (`evidence.md` §3). n is small; it is descriptive only.

### 3.4 Documented venue-specific wicks

| Date | Venue | What printed | Elsewhere | Did fills stand? | Source |
|---|---|---|---|---|---|
| 2017-06-21 | GDAX (Coinbase) ETH-USD | One large sell moved $317.81 → $224.48, then about 800 stop-loss and margin liquidations took it to **$0.10** | Not seen elsewhere | Yes. Trades honoured; Coinbase credited stop and margin victims; CFTC reportedly looked into it | [S] [TechCrunch](https://techcrunch.com/2017/06/24/coinbase-is-reimbursing-losses-caused-by-the-ethereum-flash-crash) |
| 2019-05-17 | **Bitstamp** BTC-USD | About 5,000 BTC sold 03:45-04:15 London time; low **$6,178** (about −20%) | BitMEX's index used Bitstamp, so about $250M of BitMEX longs were liquidated | Yes. "They got filled on their entire order"; Bitstamp then cut its large-order threshold from 10% to 5% of the book | [S] [The Block](https://www.theblock.co/post/23780/bitcoin-price-on-bitstamp-crashed-by-nearly-20-in-11-minutes); [S] [The Block](https://www.theblock.co/post/49725/bitstamps-big-flash-crash-wasnt-manipulation-exchange-says-but-the-event-spurred-internal-investigation) |
| 2020-03-12/13 | Market-wide; BitMEX offline 02:16-02:40 UTC | BTC low about $3,600-3,900 depending on venue | Varied | — | [S] [Cointelegraph](https://cointelegraph.com/news/bitmex-denies-it-made-bitcoin-price-drop-to-37k-after-going-offline) |
| 2021-05-19 | Market-wide; Binance perps deepest | ETH perp $1,400.73 vs spot $1,888 [T]; BTC −20% in 45 minutes | Coinbase and Binance outages | — | [S] [Deribit](https://insights.deribit.com/exchange-updates/the-flash-crash-of-may-19-2021/) |
| 2021-10-21 | **Binance.US** BTC-USD | $65k → **$8,200** for about a minute (−87%); a client's algorithm bug | $65,500 → $64,200 | Not reported reversed [U]. Binance.US and Coinbase rules then had no circuit breakers or price bands | [S] [The Block](https://www.theblock.co/post/121657/binance-us-blames-bitcoin-flash-crash-to-8200-on-a-bug-in-a-clients-trading-algorithm); [S] [BNN Bloomberg](https://ampvideo.bnnbloomberg.ca/how-crypto-exchanges-could-stop-flash-crashes-if-they-wanted-to-1.1670335) |
| 2025-04-01 | Binance (ACT and other alts) | ACT −50% in minutes | Binance-specific | — | [S] [The Block](https://www.theblock.co/news/markets/2025-04-01-binance-altcoins-crash-minutes-349022) |
| 2025-10-10 | Market-wide; Binance perps and some Binance spot books deepest | Section 3.3 | Coinbase at a premium | Binance reimbursed $283M for collateral depegs; no reversal of fills reported [U] | sections 1.6 and 3.1 |

**Equity precedent (the opposite rule):**
- On 2010-05-06, stub quotes filled at $0.01 (Accenture). Exchanges cancelled every trade between 2:40 and 3:00 p.m. that was 60% or more away from the last 2:40 p.m. price ([SEC-CFTC joint report](https://SEC.GOV/files/marketevents-report.pdf)) [A].
- **An equity stink bid's best fills are exactly the ones that get busted.** In crypto they have generally stood, but Robinhood Crypto's erroneous-trade clause is unverified [U] (section 0, item 8).

### 3.5 Liquidity now (one year after 2025-10-10)

- **Majors have recovered.** CoinDesk Research (2026-10-10): BTC 1%-depth is about +75% vs the crash day, and ETH 0.5%-depth has doubled.
- **Altcoins have not.** The altcoin basket's **dollar** depth has fallen at every measurement since 2025-01-01, by about 33%, to about $2M at the 5% band [S] ([CoinDesk](https://www.coindesk.com/markets/2026/10/10/one-year-after-10-10-bitcoin-and-ether-liquidity-have-rebuilt-but-other-altcoins-still-face-risks); [Phemex summary](https://phemex.com/news/article/bitcoin-and-ether-liquidity-rebounds-one-year-postcrash-as-altcoin-depth-erodes-99411)).
- **Implication.** Thinner altcoin books make deep wicks more likely in HYPE, NEAR and similar coins, and also mean less size fills at the bottom.

---

## 4. The economics of a resting limit buy

The literature is reviewed in `evidence.md` §1-§4. This section states the mechanics-level logic the design needs.

### 4.1 A free put option

- **What the bid gives away.** A resting buy at L gives the market the right to sell you the coin at L whenever it likes, for 90 days, at no premium. That is a short put struck at L, given away free.
  - The quote-as-option framing is Copeland and Galai (1983, JF 38(5)) [A record] ([HUJI record](https://cris.huji.ac.il/en/publications/information-effects-on-the-bidask-spread/)).
- **Contrast with selling a listed put.** A cash-secured put pays a premium for the same obligation. A stink bid is paid only through the discount at which it buys, and only if the price recovers.
- **Who exercises it:**
  - sellers who know or expect the price is going lower (informed, adverse selection);
  - sellers who must sell now (liquidation engines, ADL, margin calls, triggered stops, panicked or mistaken traders).
  - The trade is good only when the second group dominates the flow at the moment you are filled.

### 4.2 Two risks: being filled, and not being filled

- **Two risks.** Handa and Schwartz (1996, JF 51(5)) [A] ([IDEAS](https://ideas.repec.org/a/bla/jfinan/v51y1996i5p1835-61.html)) name both: "an adverse information event can trigger an undesirable execution", and "favorable news can result in a desirable execution not being obtained".
- **Non-informational volatility.** Their working paper adds that limit trading "is, in fact, sub-optimal when transaction prices change solely in response to new information". It needs non-informational, liquidity-driven volatility.
- **For this user:**
  - Most stink bids never fill. The non-execution cost is the forgone return on a coin the user says he wants to own, plus the carry on idle cash (section 1.4).
  - The bids that do fill are selected on the price having just fallen hard.

### 4.3 Queue position, and what "touching" means on each route

- **Exchange route (Bitstamp).**
  - Price-time priority. A bid placed weeks ahead sits early in the queue at its price. Bids already resting at the same price, often large ones at round numbers, are ahead of it.
  - A wick that just reaches L may fill only the orders queued at L before yours.
  - The repo's backtests already distinguish "touch" from "trade-through" fills (`practicalities_us.md`, implication 2) [R].
- **Market-maker route.** There is no queue to win. The market maker's ask must reach L, which needs the mid about 1% plus the crash spread below L (section 1.2).
- **Round numbers.** Take-profit and limit orders cluster at round numbers, and stop-losses just beyond them (Osler 2003, JF 58(5)) [A] ([IDEAS](https://ideas.repec.org/a/bla/jfinan/v58y2003i5p1791-1819.html); [NY Fed SR125](https://www.newyorkfed.org/medialibrary/media/research/staff_reports/sr125.pdf)).
  - Bidding slightly **above** a round number puts the bid ahead of that cluster.
  - Bidding slightly **below** one only fills once the cluster is gone and the stops beyond it are firing. That is a deeper level, with worse information content.

### 4.4 Adverse selection

- **Repo evidence near the touch** (`reports/Scalping and market making.md` §3a) [R].
  - Passive crypto quotes on Binance captured +1.3 to +5.9 bp of spread at the fill.
  - The price then moved 4.8-19.2 bp against them within 5 minutes, so every band lost.
- **Retail limit orders in general** show the same price-contingent bias (Linnainmaa 2010, JF 65(4)) [R] ([IDEAS](https://ideas.repec.org/a/bla/jfinan/v65y2010i4p1473-1506.html)).
- **Stink bids are a different regime:**
  - fills are rare and come in clusters;
  - the move that fills them is large;
  - the question is whether a fill marks the end of forced selling or the start of an information-driven slide.
- **That is the study's empirical question; nothing here answers it.** The knife-catching base rate and "real revenue" filters are in `evidence.md` §4.4-4.5.

### 4.5 When the trade-off can be favourable: forced-liquidation overshoots

Theory and cross-asset evidence say that price moves caused by forced, non-informational supply overshoot and then revert as slow-moving capital arrives:
- Duffie (2010, JF 65(4)) [A] ([IDEAS](https://ideas.repec.org/a/bla/jfinan/v65y2010i4p1237-1267.html)).
- Fire sales by distressed funds (Coval and Stafford 2007, JFE 86(2)) [A] ([NBER](https://www.nber.org/papers/w11357)).
- The return to supplying liquidity jumps when the VIX is high (Nagel 2012, RFS 25(7)) [A] ([NBER](https://nber.org/papers/w17653)).
- Deribit's practitioners: once liquidations "have been fully worked through, generally the market rebounds higher as the main source of selling in the market has now abated" [S] ([Deribit](https://insights.deribit.com/market-research/market-dislocations-in-crypto-and-how-to-benefit-from-them/)) [U: the quote may come from a companion Deribit piece].
- An AEA 2026 paper reports that perpetual-futures drawdowns mean-revert quickly [S] ([AEA](https://www.aeaweb.org/conference/2026/program/paper/ByyFEfr4)).
- **Counter-view.** A non-peer-reviewed practitioner test calls apparent "post-cascade alpha" leveraged beta [S] ([Medium](https://medium.com/coinmonks/chasing-liquidation-cascade-alpha-in-crypto-how-to-get-299-return-with-sharpe-3-58-322ef625a8d1)).

**For this user, four conditions must hold at once:**
1. **The fall must be forced, not news about the coin.** Example: a market-wide liquidation cascade, not a hack or insolvency. Cascades cluster across coins; coin-specific news does not.
2. **The bid's venue must print the wick.** On Robinhood that means its own ask or Bitstamp's book (section 1).
3. **The bid must fit in the capacity at that level.** On 2025-10-10, tens of thousands of dollars per altcoin near the bottom, even on Binance (Table C).
4. **The fill must be honoured.** It has been in crypto so far (section 3.4).

### 4.6 An identity for the pre-registration (no numbers)

Per bid placed:
- **E[value]** = P(fill) × (E[mark-to-market at horizon h | fill] − L × (1 + cost)) − (1 − P(fill)) × (non-execution cost) − carry on reserved cash.
- **cost:** ~0.96% embedded (market-maker route) or the maker fee (exchange route).
- **Non-execution cost:** the return of the fair alternative over the bid's life: buying at market when the bid was placed, a random entry, or T-bills.

Each term needs a fair benchmark. The brief lists them: market buy at placement, random entries, T-bills, and a slow-dip control at the same depth.

---

## 5. Implications for the study design

1. **Model the bid's life.** A bid lives 90 days, then is re-placed (Robinhood). Re-placement resets the queue. Prices round down to the pair's tick; quantities to the increment.
2. **Use several fill rules and report them side by side:**
   - **RH-MM.** The bid fills when a reference **mid** reaches L ÷ (1 + s). Use s = 1% as base, with sensitivities 2%, 3% and 5% for crash spreads. The cost basis is L.
   - **RH-exchange.** A Bitstamp trade-through at L, at cost L × (1 + maker fee). No Bitstamp data is reachable here. Use a proxy and label it.
   - **Venue-native trade-through** (Binance spot), and **touch** as an optimistic bound only. Never treat a perp wick as a fill.
3. **Choose the reference series in this order:**
   - (a) a US spot venue (Coinbase; Bitstamp if reachable), once a session allows those hosts;
   - (b) **Binance's index price** (`indexPriceKlines`), a free multi-venue composite that filters single-venue prints such as ATOM $0.001;
   - (c) Binance spot;
   - (d) Binance perp last price as an upper bound for depth only.
   - Report how many fills would vanish moving from (d) to (b).
4. **Cap fill size by capacity.** Fill at most the sell-initiated notional that traded through L (Table C method). Report results at several order sizes, e.g. $1k, $10k, $100k per level. The user's "decent amount" is the binding constraint at deep altcoin levels.
5. **Add a dwell requirement as a fill-rule variant for the market-maker route.** For example, require at least one full 1-minute bar below the threshold, since a market maker's ask may not follow a seconds-long wick [U]. This is a fill rule, not an outcome.
6. **Respect listing dates and gaps:**
   - HYPE on Robinhood from 2025-10-23. Binance HYPE perp from 2025-05-30; spot from 2026-09-24.
   - NY residents: no HYPE on Robinhood.
   - Exclude or flag fills in windows when the venue was down (section 1.5).
7. **Treat events as clustered.** Many coins fill in the same 10 minutes (e.g. 2025-10-10 21:19-21:29 UTC). Inference must cluster by event or day, not count coin-fills as independent; the BB study's month-cluster method can be reused [R].
8. **Round-number rule as a pre-registered level variant.** Compare "L slightly above the nearest round number" with "L exactly at it". This is a fill-probability question and can be pre-registered.
9. **Carry.** Charge reserved cash at the T-bill rate minus whatever it earns. Run two cases: 0%, and 3.35% Gold sweep. The sweep question is open [U].
10. **ETF route.** For HYPE via THYP/BHYP, test only fills inside ETF trading sessions. Most crypto wicks will be out of session, so expect few.

---

## 6. Open questions (check in the app or in a session with wider network access)

- **Interest on reserved cash.** Does cash reserved for an open crypto limit order keep earning sweep interest?
- **Exchange routing coverage.** Are HYPE and NEAR eligible for exchange routing in the app? Which route does an agentic (MCP) order use? Is maker pricing live for this account?
- **Market-maker spread in stress.** How wide does the market-maker spread get in a crash? A read-only quote poll during the next volatile hour (orchestrator only) would give a first number.
- **Erroneous-trade clause.** What is the exact clause in the current Robinhood Crypto Customer Agreement (revised 2025-10-22)?
- **Bitstamp history.** What were Bitstamp's HYPE and NEAR lows on 2025-10-10, if listed? This needs Bitstamp's public API, blocked here.
- **Coinbase.** How large is Coinbase's limit-order "Price Protection Point"? What were Coinbase's lows on the event days? Coinbase is reachable from the environment created for a later session (brief).
- **Robinhood history.** Does any read-only Robinhood surface (e.g. Legend charts) expose historical crypto candles that would show Robinhood's own wick depth on past crash days?

---

## Sources

**Robinhood:**
- Support pages:
  - [Crypto order routing](https://robinhood.com/us/en/support/articles/crypto-order-routing/)
  - [Buying and selling crypto](https://robinhood.com/us/en/support/articles/crypto-buying-and-selling/)
  - [Why hasn't my crypto order filled?](https://robinhood.com/us/en/support/articles/why-hasnt-my-cryptocurrency-order-filled)
  - [Crypto glossary](https://robinhood.com/us/en/support/articles/robinhood-crypto-glossary)
  - [Crypto fee tiers](https://robinhood.com/us/en/support/articles/crypto-fee-tiers)
  - [Why do the crypto mid price and order price differ?](https://robinhood.com/us/en/support/articles/crypto-prices-differ)
  - [Why was my order rejected?](https://robinhood.com/us/en/support/articles/why-was-my-order-rejected)
  - [Trading halts](https://robinhood.com/us/en/support/articles/trading-halts)
  - [High-Yield Cash Program APY](https://robinhood.com/us/en/support/articles/earning-interest/)
  - [Gold boost](https://robinhood.com/us/en/support/articles/yes-gold-apy-superboost/)
  - [Cash sweep program](https://robinhood.com/us/en/support/articles/360034303352)
- Legal and corporate:
  - [Crypto Risk Disclosures](https://cdn.robinhood.com/assets/robinhood/legal/Robinhood%20Crypto%20Risk%20Disclosures.pdf)
  - [Crypto Customer Agreement](https://robinhood.com/us/en/crypto-customer-agreement/)
  - [RHC fee schedule](https://cdn.robinhood.com/assets/robinhood/legal/rhc-fee-schedule.pdf)
  - [Bitstamp acquisition (newsroom)](https://robinhood.com/us/en/newsroom/robinhood-completes-acquisition-of-bitstamp/)
  - [status page incident](https://status.robinhood.com/incidents/6r0wrcty5v8h)
- MCP tool schemas `place_crypto_order`, `preview_crypto_order`, `get_currency_pairs` (descriptions loaded 2026-11-18; not called).

**Other venues:**
- Coinbase:
  - [Advanced Trade API orders](https://docs.cdp.coinbase.com/coinbase-app/advanced-trade-apis/guides/orders)
  - [Edit order](https://docs.cdp.coinbase.com/api-reference/advanced-trade-api/rest-api/orders/edit-order)
  - [Coinbase trading rules](https://www.coinbase.com/ru/legal/trading_rules)
  - [CryptoDaily on Coinbase fees](https://cryptodaily.co.uk/2026/09/coinbase-advanced-fees-usdc-vip-tiers)
- Kraken: [Kraken Pro fee tiers](https://blog.kraken.com/product/pro/new-kraken-pro-fee-tiers)
- Binance.US:
  - [Binance.US zero-fee](https://blog.binance.us/zero-fee-trading/)
  - [Motley Fool Binance.US review](https://www.fool.com/money/cryptocurrency/binanceus-review/)
- Bitstamp: [Bitstamp review](https://wherelegalcrypto.pages.dev/exchanges/bitstamp/review/)
- Hyperliquid:
  - [Datawallet on Hyperliquid and the US](https://www.datawallet.com/crypto/is-hyperliquid-available-in-the-usa)
  - [OneKey](https://onekey.so/blog/ecosystem/geo-block-hyperliquid-dydx-us/)
- HYPE listings and products:
  - [The Defiant (Robinhood HYPE)](https://thedefiant.io/robinhood-adds-hype-for-spot-trading)
  - [Crypto Briefing (Binance.US HYPE)](https://cryptobriefing.com/hyperliquid-hype-spot-trading-binance/)
  - [Messari HYPE markets](https://messari.io/project/hyperliquid/markets)
  - [The Block (HYPE ETF)](https://www.theblock.co/post/401047/first-ever-hyperliquid-etf-launches-posts-very-solid-first-day-of-trading-analyst)
  - [CryptoTimes (ICE / Trade[XYZ])](https://www.cryptotimes.io/2026/10/29/hyperliquid-token-hype-price-rises-14-after-ice-and-tradexyz-announces-regulated-u-s-perpetuals-venue/)

**Crashes and wicks:**
- 2025-10-10:
  - [Galaxy Research](https://www.galaxy.com/insights/research/cryptos-flash-crash-liquidation-binance-adl-auto-deleveraging)
  - [CoinShares](https://coinshares.com/us/insights/knowledge/billions-in-liquidations-what-happened/)
  - [Datawallet](https://www.datawallet.com/crypto/october-10-crypto-crash-explained)
  - [Kaiko](https://research.kaiko.com/insights/cryptos-pricing-problem-laid-bare)
  - [Cointelegraph (zero prints)](https://cointelegraph.com/news/why-did-some-altcoins-on-binance-crash-to-zero)
  - [Cointelegraph (display issue)](https://cointelegraph.com/news/binance-tokens-not-crash-0-display-issue)
  - [Finextra](https://www.finextra.com/blogposting/29592/system-stress-market-makers-and-the-largest-crypto-liquidation-ever-regulatory-lessons)
  - [FTI Consulting](https://www.fticonsulting.com/insights/articles/crypto-crash-october-2025-leverage-met-liquidity)
  - [CryptoQuant](https://cryptoquant.com/insights/quicktake/68ec26489792d0004764379b-Bitcoins-Coinbase-Premium-Hits-19-Month-High-During-Crash-Signaling-Major-Instit)
  - [CoinDesk one year later](https://www.coindesk.com/markets/2026/10/10/one-year-after-10-10-bitcoin-and-ether-liquidity-have-rebuilt-but-other-altcoins-still-face-risks)
- Mechanism papers and exchange documents:
  - [arXiv 2512.01112 (ADL)](https://arxiv.org/pdf/2512.01112)
  - [Lim, SSRN 6579278](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6579278)
  - [Binance liquidation FAQ](https://www.binance.com/en-AE/support/faq/360033525271)
- Earlier events:
  - [TechCrunch (GDAX 2017)](https://techcrunch.com/2017/06/24/coinbase-is-reimbursing-losses-caused-by-the-ethereum-flash-crash)
  - [The Block (Bitstamp 2019)](https://www.theblock.co/post/23780/bitcoin-price-on-bitstamp-crashed-by-nearly-20-in-11-minutes)
  - [The Block (Binance.US 2021)](https://www.theblock.co/post/121657/binance-us-blames-bitcoin-flash-crash-to-8200-on-a-bug-in-a-clients-trading-algorithm)
  - [Deribit (2021-05-19)](https://insights.deribit.com/exchange-updates/the-flash-crash-of-may-19-2021/)
  - [IWH (Binance 2021-05-19)](https://www.iwh-halle.de/en/publications/detail/bitcoin-flash-crash-on-may-19-2021-what-did-really-happen-on-binance)
  - [SEC-CFTC 2010 report](https://SEC.GOV/files/marketevents-report.pdf)

**Literature:**
- [Copeland and Galai 1983](https://cris.huji.ac.il/en/publications/information-effects-on-the-bidask-spread/)
- [Handa and Schwartz 1996](https://ideas.repec.org/a/bla/jfinan/v51y1996i5p1835-61.html)
- [Osler 2003](https://ideas.repec.org/a/bla/jfinan/v58y2003i5p1791-1819.html)
- [Coval and Stafford 2007](https://www.nber.org/papers/w11357)
- [Duffie 2010](https://ideas.repec.org/a/bla/jfinan/v65y2010i4p1237-1267.html)
- [Linnainmaa 2010](https://ideas.repec.org/a/bla/jfinan/v65y2010i4p1473-1506.html)
- [Nagel 2012](https://nber.org/papers/w17653)
- [Brogaard et al. 2018](https://econpapers.repec.org/RePEc:eee:jfinec:v:128:y:2018:i:2:p:253-265)
- [Makarov and Schoar 2020](https://econpapers.repec.org/RePEc:eee:jfinec:v:135:y:2020:i:2:p:293-319)

**Rates:** [FRED DGS3MO](https://fred.stlouisfed.org/series/dgs3mo).

**Repo:**
- `AGENTIC_TRADING_PLAN.md` §1
- `analysis_2026/research_notes/Scalping and market making/crypto_data_feasibility.md` §6
- `analysis_2026/research_notes/Scalping and market making/practicalities_us.md`
- `analysis_2026/reports/Scalping and market making.md` §3a
- `analysis_2026/research_notes/Bollinger breakout replication/data_inventory.md` and `rules_and_evidence.md` §3.7
- Sibling note: `analysis_2026/research_notes/Stink bids/evidence.md`
