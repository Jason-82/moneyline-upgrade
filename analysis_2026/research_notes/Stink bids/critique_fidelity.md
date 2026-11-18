# Stink bids: simulation-fidelity critique of the design draft

An adversarial review of [`design_draft.md`](design_draft.md), written 2026-11-18 for the orchestrator, who folds the
accepted changes into `analysis_2026/STINKBID_PREREG.md` before it is frozen.

**Lens: simulation fidelity.** Does the engine reproduce what this user's orders would actually have done?
- look-ahead in level computation and placement;
- fill realism: trade-through against touch, queue position, capacity from aggTrades, partial fills;
- venue differences, Robinhood pricing and outages, maker/taker costs, ticks, minimum and maximum order sizes;
- exit realism;
- outages and bad prints, data errors on delisting days;
- 1-minute against hourly resolution.

**What was read in full:**
- the draft;
- the three sibling notes: [`mechanics.md`](mechanics.md), [`evidence.md`](evidence.md), [`data_inventory.md`](data_inventory.md);
- the sibling [`critique_statistics.md`](critique_statistics.md), so that nothing here duplicates it;
- the draft's scratch scripts (`design_sim/fillcal.py`, `fillcal7.py`, `fillsum7.py`, `power.py`).

**Tags:**
- **[C]** computed here: counts on real data (nothing after a fill is used for any return), or synthetic outcomes;
- **[R]** a repo file;
- **[A] / [S]** a primary or secondary web source, as tagged in the sibling notes;
- **[U]** unverified, inferred or a judgment call.

**Ground rules followed:**
- No post-fill return, P&L or strategy outcome was computed on real data. Every outcome below is synthetic.
- On real data, prices after a fill were read only for these purposes:
  - whether another series also reached the level (a fill on another venue);
  - how much seller volume traded below the level (fill size);
  - whether data exist (coverage).
- No Robinhood tool was called. Nothing was committed. In the repo, only this file and derived data under
  `data/stinkbid/critique_fidelity/` (gitignored) were written.
- Scripts from an interrupted first pass of this critique were reviewed and re-run, and new ones were added
  (section 5). The draft is not edited. Each proposal gives replacement text for the pre-registration.

---

## 0. Bottom line

The draft's fill model is sound at its core:
- trade-through by a tick, fills at the limit price;
- exits live only from the next minute;
- capacity defined as the seller volume that printed below the level;
- a multi-venue gate (F3).

Its hourly fill calendar agrees with minute data on every fill [C].

Three gaps would mislead the study, and each needs a change before the freeze:

1. **K1b's known answer is not zero (V1, must).** When a wick gaps through a bid, the bid is under water from the
   moment it fills. Under a martingale, a correct engine therefore shows a negative mean, −1.9% to −8.9% in the
   synthetic test here. As drafted, K1b fails a correct engine and passes an engine that books fills at the
   minute's close.
2. **Data availability leaks the future (V2, must).** "No bid life crosses a segment boundary", and the
   calendar's "drop a life with more than half its hours missing", both decide which bids exist from data after
   placement.
   - K4 cannot see this, because it never deletes data.
   - On 90-day lives, 10 dropped bid-lives would have filled before trading stopped.
3. **The flip assumes a bot (V3, must).** The sell is live one minute after the fill. This user places orders by
   hand, and 38% of P1 fills started between 00:00 and 06:59 ET or on a weekend.
   - In synthetic wicks, the flip's mean moves by −2.6 to +5.7 points with the sell's latency. That is the size of
     H1's MDE.

The should items (V4-V10):
- **The F3 gate** removes about twice what the draft estimates (10.3% of fills at s = 1%), and its spot fallback
  would let Binance-only prints through.
- **The K5 audit** rejects correct gap-through fills.
- **The live sheet cannot have Sunday's close at Monday 00:00 UTC.** The archive publishes it 1.5-3 hours later.
- **The one-position rule** silently shrinks H2's sample to 887 fills.
- **36% of fills are on coins Robinhood does not list.**
- **Delisting days and redenominations are mis-valued.**
- **The sheet prints a different bid from the one H1 tests.**

Five could items (V11-V15) tidy bad prints, rebrands, capacity, route-specific advice, ticks and order sizes.

---

## 1. How this was checked

### 1.1 Counts on real data [C]

**Calendar.** The draft's `fillcal7.parquet`:
- weekly bids at k = 5..12 on Binance hourly spot bars;
- P1 = U-Q1 fills at k = 6, 8, 10, PAX excluded: 1,274 fills, matching the draft.

**Data fetched for this note** (Binance archive through the path-style S3 URL; sha256-checked against each
`.CHECKSUM`):
- **USD-M 1d klines** (index and last price) for the 79 U-Q1 coins with P1 fills, including LUNA classic's own
  contract.
- **1m spot klines** for the fill day ±1 day, for all 854 P1 fill coin-days.
- **1m index klines** for the fill day and the next day: 1,539 day-files fetched; 37 are not in the archive.
- **Hourly BUSDUSDT, USDCUSDT and TUSDUSDT bars**, as a USDT/USD proxy.

**Also used:** the inventory's 13 event-day aggTrades files.

**Checks:**
- minute-level consistency of the hourly calendar;
- capacity, by the draft's 1-minute approximation C₁ and against aggTrades;
- the F3 index gate at weekly and minute resolution, with dwell, in USD, and with index update counts;
- gap-through fill minutes;
- the look-ahead audits of delisting weeks and lives;
- data gaps inside post-fill windows;
- delisting-day data quality;
- rebrand successors in the universe;
- the clock time of fills;
- Robinhood listing;
- the archive's publication times, from the S3 `LastModified` stamps of 2026-11-10..17.

### 1.2 Synthetic simulations [C]

**`sim_k1_latency.py` (first pass, re-run).**
- 1-minute martingale paths with compensated exponential jumps (mean 18%, 1.5 a week).
- Three cases: permanent jumps; half-transient jumps (30-minute half-life, as in K2); and half-transient jumps with
  a fading rebound bump.
- Weekly bids at 8σ (σ = 4.5%), X-FLIP or a 72-hour hold.
- Two engines: fills at L (correct) against fills booked at the fill minute's close.

**`sim_latency2.py` (new).**
- One wick per path: from D above the bid (uniform 0.05-0.36 in log) to an exponential overshoot o below it.
- After the wick, three parts:
  - a permanent share π;
  - a transient share reverting with half-life hr;
  - an optional rebound bump that peaks in about 30 minutes and fades over about 2 hours.
- Plus 4%-daily Brownian noise, on a 1-minute grid.
- 8,000 paths per case.
- Part 1: K1b's known answer for overshoot means of 2%, 5% and 10% (π = 1).
- Part 2: X-FLIP's mean by the sell's latency (1, 15, 60, 240 and 480 minutes, and a manual mix of 60 and 480
  minutes in the 62/38 proportion of real P1 fills by clock time).

### 1.3 What could not be checked here

- **Robinhood's own quotes and spreads in a crash.** There is no history (`mechanics.md` §1.6).
- **Bitstamp's books, Robinhood's past listing dates, and Robinhood's tick table.** The scalping study's saved
  snapshot has no ticks; the orchestrator's `currency_pairs.json` will.
- **Order types.** Whether Robinhood offers any one-triggers-other or bracket order for crypto. `mechanics.md` §1.1
  lists market, limit, stop and stop-limit only [U].
- **Exact redenomination ratios** from Binance announcements. Here they are inferred from price ratios across the
  data gaps [U].
- **Post-fill outcomes** (ground rules). So the size of the gap-through loss in real data, the flip's real latency
  sensitivity, and how often the delisting valuation flips a knife are not measured. Only their mechanisms and
  frequencies are.

---

## 2. Evidence

### 2.1 Look-ahead through data availability [C]

**The drafted rule.** §4.4 says no "bid life or exit window crosses a segment boundary". The draft's calendar
implements it as: drop a life if more than 50% of its hours are missing. Both use data after placement: at t0
nobody knows the coin will stop trading next week.

**What it removed, for U-B coins that stopped trading on Binance spot** (lives that contain the coin's last trade;
rungs 6, 8, 10):

| life | lives containing a last trade | dropped by the rule | dropped bid-lives that would have filled before trading stopped | kept bid-lives that would have filled |
|---|---|---|---|---|
| 7 days | 21 (21 coins) | 18 | 0 of 54 | 3 |
| 30 days | 19 | 10 | 0 of 30 | 8 |
| 90 days | 19 | 10 | **10 of 30** (AGIX, D, FTM, RNDR) | 13 |

- **In U-Q1, 5 weekly placements were dropped:** BTT 2022-01-17, XMR 2024-02-19, RNDR 2024-07-22, MATIC 2024-09-09
  and FTM 2025-01-13. In each, the last trade falls inside the week. None would have filled.
- **The weekly P1 counts are therefore unaffected.** The 90-day "set and forget" life (D2, a sensitivity row) is
  affected.
- **The damage is in the principle.** The rule is written into the pre-registration, and K4 cannot detect it: K4
  multiplies prices and volumes after a cut, but never deletes data.

### 2.2 When the data exist: the archive's publication lag [C]

S3 `LastModified` of the daily files, 2026-11-10..17 ([Binance public data](https://github.com/binance/binance-public-data/)):

| files for day d | published on d + 1, UTC |
|---|---|
| spot 1d and 1m klines, spot aggTrades | 01:36-03:12 |
| USD-M `metrics` (open interest) | 06:34-08:19 |
| USD-M 1m klines, index and mark-price klines | 07:36-12:59 |

- **The mismatch.** At Monday 00:00 UTC, the backtest's placement time and §15.2's instruction to the user, Sunday's
  close is not yet published. Sunday's open interest (M7) and index (HYPE's proxy) arrive later still.
- **Fills that sit inside the gap:**
  - 17 P1 fills (1.3%) came in the first 3 hours of the weekly life, 15 of them on 2025-02-03;
  - 29 (2.3%) in the first 12 hours, adding 11 on 2024-08-05.
- **Two market-wide Monday crashes sit exactly where the live routine and the backtest differ.**

### 2.3 K1b: the known answer under gap-through jumps [synthetic, C]

A resting bid fills at L. When a wick jumps from above L to below it, the price right after the fill is below L.
Under a martingale the expected exit equals that price. The mean of a correct engine is then negative: the cost
of the free option a resting bid writes ([Copeland and Galai 1983](https://cris.huji.ac.il/en/publications/information-effects-on-the-bidask-spread/)).

| wick model (non-reverting) | correct engine: fill at L, hold 72 h | wrong engine: fill booked at the fill minute's close |
|---|---|---|
| overshoot mean 2% | −1.90% (SE 0.08) | +0.06% (SE 0.08) |
| overshoot mean 5% | −4.64% (SE 0.09) | +0.21% (SE 0.08) |
| overshoot mean 10% | −8.87% (SE 0.12) | +0.18% (SE 0.08) |
| first pass: exponential jumps, mean 18% | −13.84% (SE 0.33) | −0.08% (SE 0.28) |

**What this means for K1b and K2:**
- **K1b as drafted inverts.** It requires the mean r_f and the mean Δ to be within 2 SE of 0. That fails the correct
  engine and passes the wrong one.
- **The wrong engine is not harmless.** With half-transient jumps (the K2 market), it reported +29.9% against the
  correct +8.5%.
- **Gap-through fills are real.** In real data, 4.2% of P1 fill minutes open below L, and 1.3% lie wholly below it
  (2.4).

### 2.4 Gap-through entries and the K5 audit [C]

Minute data, the calendar's rule (low ≤ L × 0.999):

| P1 fill minutes (1,274) | count |
|---|---|
| open below L | 53 (4.2%) |
| wholly below L (high < L) | 17 (1.3%); 13 at k = 6, 3 at k = 8, 1 at k = 10 |
| ... of which the previous minute traded and closed above L (a true gap through L) | 3 |
| follow a missing or zero-trade minute | 0 |
| first qualifying minute is the (non-live) placement minute | 0 |

- **The correct price is outside the minute's range.** For a minute wholly below L, a resting bid would have traded
  at L, so L is the correct fill price. Yet L lies above the minute's high.
- **K5 would stop a correct run.** K5 requires "every fill and exit price within [low, high] of its minute" and stops
  the run on a violation.
- **Exits have the same problem.** Resting sell targets that a minute gaps over do too, as do marketable sells once
  latency is modelled (V3).

### 2.5 Exit latency [C]

**When fills happen** (P1, New York time):
- 23% of fills start between 00:00 and 06:59;
- 27% start on a Saturday or Sunday;
- 38% start in one or the other;
- the 17:00 hour alone holds 15% (2025-10-10).

**Synthetic flip means by the sell's latency** (before costs; SE 0.10-0.16):

| wick case | 1 min (draft) | 15 min | 60 min | 240 min | 480 min | manual mix | target reached within 72 h |
|---|---|---|---|---|---|---|---|
| half transient (20-min half-life), no rebound bump | +8.47% | +8.47% | +8.47% | +8.47% | +8.47% | +8.47% | 16.6% |
| half transient, bump (peak ~30 min, fades ~2 h) | +10.92% | +10.96% | +12.50% | +8.41% | +8.30% | +10.95% | 38.1% |
| 70% transient (30-min), larger bump | +15.15% | +15.99% | +20.87% | +15.65% | +14.22% | +18.34% | 59.0% |

**Reading:**
- Latency does not matter when the 72-hour stop decides the exit.
- It matters, by −2.6 to +5.7 points, exactly where an edge would live: a brief rebound.
- **Late can beat early.** A sell that goes live while the price is above the target executes at the market price
  instead of being capped at the target.
- **Early can beat late.** A sell that goes live after the bounce has faded misses it.
- **The sign is unknown, so the rule must be stated** and applied to twins too.
- **This user cannot pre-place the sell.** Robinhood crypto has no order that sells a coin before it is owned
  (`mechanics.md` §1.1: market, limit, stop, stop-limit [U: no OTO or bracket orders]).

### 2.6 The venue gate F3 [C]

**Weekly life, Binance's 1d index klines.** Of 1,272 F1 fills with index coverage (2 partial):

| F3 spread s | F1 fills kept | removed | the draft's estimate (§8.1) |
|---|---|---|---|
| 0% | 97.8% | 2.2% | — |
| 1% | 89.7% | **10.3%** | 5-8% |
| 2% | 81.7% | 18.3% | — |
| 3% | 76.3% | **23.7%** | "about a fifth" |
| 5% | 65.9% | 34.1% | — |

- **By rung at s = 1%:** removed 12.0% (k = 6), 8.0% (k = 8), 8.7% (k = 10). At s = 3%: 27.7%, 19.0%, 18.7%.
- **F3 hardly touches the big crashes.** The seven largest fill days keep 96-100% at s = 1%:
  - 2025-10-10: 99%;
  - 2023-08-17: 100%;
  - 2023-06-10: 98%;
  - 2021-05-19: 100%;
  - 2022-11-08: 98%;
  - 2022-05-11: 100%;
  - 2021-12-04: 96%.
- **The haircut falls on smaller episodes.** The eighth-largest day, 2022-11-09, keeps 91%. At s = 1% / 3%:
  2024-07-05 kept 88% / 73%, and 2026-02-06 kept 90% / 67%.
- **So F3 does not test whether the big crashes were Binance-only.** At P1's depths those prints were multi-venue.
- **F5** (perpetual last price) also filled 99.7% of F1 fills.
- **The other direction.** The index reached L while Binance spot (hourly, 10 bp) did not on 5 placements, and
  reached L/1.01 on 1.

**Minute resolution** (1,247 fills with index data, fill day and next day):

| rule | kept |
|---|---|
| index low ≤ L (s = 0) | 97.5% |
| F3: index low ≤ L/1.01 | 89.1% |
| F3d: a whole index minute ≤ L/1.01 | 80.0% |

- **On the six largest days:** F3 keeps 98.4%, F3d 94.6%.
- **On other days:** F3 keeps 85.2%, F3d 73.7%.
- **Brief dips:** 7.2% of F3 fills had only 1-2 index minutes below L/1.01.

**Index data gaps.**
- 37 of 1,576 index day-files needed at minute resolution are missing from the archive. Examples: ETHUSDT and
  LTCUSDT on 2020-03-12, QTUMUSDT and ZILUSDT on 2021-05-19, ETCUSDT, IOTAUSDT, VETUSDT and XLMUSDT on 2020-09-03.
- The drafted fallback to Binance spot would let these fills through the venue gate on some of the most
  venue-specific days.

**Index outages.**
- The index klines' trade-count field holds the number of index updates in the minute (60 = one a second), not
  trades. The drafted rule "a minute with trades = 0 never fills" therefore has no meaning for F3.
- At the first F3 minute of every fill, the count was at least 50 (median 60). Staleness is not a problem in this
  sample; the rule still needs a definition.

**USD against USDT.**
- Robinhood quotes USD; Binance's pairs and index are USDT.
- Between placement and the fill hour, the USDT/USD proxy moved by more than 0.25% on 127 fills, more than 0.5% on
  19, and more than 1% on 6.
- **On 2025-10-10, USDT strengthened by a median 0.4%** (up to 1.5%), which makes USD prices fall less than USDT
  prices. On 2022-05-11 it weakened by up to 0.95%.
- **Converted to USD, F3 at s = 1% changed for 10 of 1,247 fills** (4 lost, 6 gained). That is negligible for the
  gate.
- The first pass's printed label for the sign was reversed. A stronger USDT makes the USD price shallower.

### 2.7 Capacity and partial fills [C]

**C₁ capacity of P1 fills** (the draft's 1-minute approximation, over its capacity window):

| | all P1 fills |
|---|---|
| median | $1.10M |
| 10th percentile | $45k |
| 25th percentile | $197k |
| below $10k | 2.7% (θ = 0.25: 9.2% below $40k) |
| below $100k | 16.9% (θ = 0.25: 34.1% below $400k) |
| mean share of Q = $10k filled | 98.9% (θ = 1); 95.3% (θ = 0.25) |

- **Capacity binds at $100k, not at $10k.** Median C₁ by rung: $0.89M (k = 6), $1.56M (k = 8), $1.22M (k = 10).
  Below $10k: 1.9%, 2.3%, 5.7%.
- **How long the wick stayed below L.** In the capacity window the price stayed below L for a median 5 minutes;
  14.1% of fills had a single minute below L.
- **No isolated prints.** No fill had one minute below L and less than $1k of seller volume.
- **C₁ against exact aggTrades capacity** (15 P1 fills on the inventory's event days): median ratio 0.98, 14 within
  0.89-1.10, one at 0.58 (SOL k = 8, 2025-10-10). The approximation is good enough for U-B.

### 2.8 Hourly against minute resolution [C]

- **Fills.** Every one of the 1,274 hourly calendar fills has a qualifying minute inside its fill hour. None falls in
  a zero-trade minute.
- **Speed classes.** The s24 speed class (fast / middle / slow) changes for 12 fills (0.9%) at minute resolution. 10
  of them move from fast to middle.
- **The hourly calendar is a faithful screen** for fills and speed. Its weaknesses are elsewhere (2.1, 2.2).

### 2.9 The one-position rule thins the samples [C]

Fills kept when a fill blocks its (coin, rung) until the position closes:

| exit | P1 fills kept |
|---|---|
| flip, 72 h | 1,236 of 1,274 (97%) |
| hold 90 days (H2) | 887 (70%) |
| hold 365 days | 458 (36%) |

- **Power.** The power study used 1,244 fills for H2.
- **Composition.** The rule keeps the first fill of each crash sequence and drops the later legs.
- **Pairing.** The flip and the 90-day hold produce different fill sets, so D8's paired comparison is not defined.

### 2.10 Could this user have had these fills? [C]

- **Not on Robinhood today.** 454 of the 1,274 P1 fills (36%) are on coins outside the 75-coin Robinhood set (c),
  built from the 2026-10-18 snapshot and the brief's list. The 92-pair catalog of 2026-11-18 may add a few [U].
- **Not on Robinhood then.** Most of the other fills came before their coin was on Robinhood. Robinhood listed few
  coins before 2024 [U: listing dates].

### 2.11 Delisting days, redenominations and data gaps [C]

**Data gaps inside post-fill windows:**
- **P1:** no internal missing day in any 72-hour, 90-day or 365-day window. Trading ends inside the window for 11
  fills (90 d) and 34 (365 d).
- **U-B, rungs 6/8/10, 4,391 fills:** internal gaps in 10 (90 d) and 26 (365 d) windows; trading ends in 53 and
  162.
- **The gaps inside U-B windows:**
  - FTT, 2022-11-15: 310 days, then relisted;
  - LUNA, 2022-05-13: ticker reuse, next-open/last-close ratio 20,000;
  - SUN, 2021-06-14: 3 days, ratio 0.0010;
  - COCOS, 2021-01-19: 3 days, ratio 1,000.
- **Other redenomination-like gaps in U-B coins:** BNX 2023-02 (0.01), DREP 2021-03 (100), BTCST 2021-03 (0.1).
- **The swap list misses them.** None of SUN, COCOS, BNX, DREP and BTCST is in §4.4's swap list. As drafted, a
  position open at such a gap is closed by the delisting rule, a spurious −30%. An engine that read across the gap
  would book −99.9% or +99,900%.

**The last day of the 133 dead U-B coins:**
- **Last trade against that day's VWAP:** differs by more than 5% for 48 coins, more than 10% for 23, and more than
  20% for 9. Examples: WTC −46%, GFT −41%, PNT +38%.
- **Last trade against the prior week's median close:** differs by more than 10% for 85 coins. Most of that is the
  real delisting-announcement fall.
- **Thin trading:** last-day trades were a median 0.21 of the prior month's daily median.
- **The last trade is a noisy valuation point.**

### 2.12 Rebrand successors leave the universe [C]

Under the drafted rules, a successor ticker starts its listing age and rank history from zero. U-Q1 coin-months lost
(top 100, would qualify with the predecessor's age and ranks):

| predecessor → successor | U-Q1 months lost |
|---|---|
| FTM → S | 15 |
| RNDR → RENDER | 15 |
| MATIC → POL | 4 |
| BTT → BTTC | 3 |
| EOS → A, MKR → SKY, LIT → HEI | 0 |
| **total** | **37 coin-months (about 160 coin-weeks, ×3 rungs)** |

### 2.13 Outages and crash-window completeness [C]

- **No P1 fill falls on a reported Robinhood outage date:**
  - 2021-01-21/22 [U: date];
  - 2021-04-15;
  - 2021-05-04;
  - 2022-02-25 (display error);
  - 2025-10-06;
  - 2025-10-20.
- **The drafted outage exclusion is moot for P1.** The real risk is unreported degraded service in a crash, which no
  list captures [U].
- **Binance's 1m spot archive is complete in the crash windows.** It has no missing or zero-trade minute on
  2021-05-19 12:00-14:30 (24 coins) or 2025-10-10 21:00-22:30 (31 coins). The reported 40-minute pause in Binance's
  transaction reporting on 2021-05-19 (`mechanics.md` §1.5) does not show as missing data.

### 2.14 What the draft already gets right (keep)

- **F1:** trade-through by one tick, fill at L, and F2 (touch) only as an "illusion" row.
  [Lo, MacKinlay and Zhang](https://web.mit.edu/Alo/www/Papers/limit10.html) warn that hypothetical touches are
  poor proxies for real executions.
- **Timing:** fills stamped at the minute's end, exits live from the next minute, and no rule that depends on the
  order of the high and the low within a minute.
- **Capacity:** the counterfactual (seller-initiated volume that printed below L would have hit a bid at L first)
  is the right construction. Its 1-minute approximation tracks aggTrades.
- **Venues:** F3 and F5 are kept separate from F1. Perpetual wicks are never treated as fills for this user.
- **Benchmarks:** B-MKT is compared per placement, not per fill.
- **Controls:** K4's perturbation and K6's capacity check (both need the extensions below).
- **The hourly screen** resolved on minute bars before a fill is recorded (U-B streaming). Section 2.8 supports it.

---

## 3. Proposals

Each proposal states its severity, the sections it changes and the bias it causes if left. Then come the problem,
the evidence and the replacement text or rule.

### V1. K1b: test against an oracle, not against zero

**must · §11.2 K1 (and K2) · false negative (a correct engine fails a control that stops the study); false positive
(a fill-at-close engine passes K1b and inflates reverting cases)**

**Problem.**
- K1b requires the mean Δ and the mean r_f to lie within 2 SE of 0 before costs, in a market whose jumps do not
  revert.
- A correct engine fills at L. Every fill that a jump carries through L starts under water, so under a martingale
  the correct means are negative.
- The draft's rule fails that engine. It passes an engine that books fills at the fill minute's close or low.

**Evidence:**
- **Synthetic (2.3):** −1.9% to −8.9% (correct) against +0.1% to +0.2% (fill at close). In the K2 market, the
  wrong engine reported +29.9% against the correct +8.5%.
- **Real data:** 4.2% of P1 fill minutes open below L.

**Replacement (§11.2, K1):**
> **K1 Known answer.** K1a (no jumps) and K1b (market-wide jumps that do not revert) pass when the engine's mean r_f
> and mean Δ, before costs, each lie within 2 SE of an oracle computed directly from the injected paths by separate
> code:
> - each bid fills at L in its first live minute whose low ≤ L − τ;
> - each exit follows the program's rule on the same path;
> - each twin enters at the open of its entry minute.
>
> The oracle is about −τ/L in K1a. It is negative in K1b, because a gap-through fill sits above the price that
> follows it. Its value is reported.
>
> **Negative checks.** Two engine variants must fail K1b: one that books each fill at its fill minute's close, and
> one that books it at the minute's low.
>
> **K2** passes on the same oracle rule.

### V2. No placement, life, fill or exit may depend on data after its own time

**must · §4.4 Segments, §7.1, §7.4 (method), §11.2 K4, §16 (engine) · false positive (removes the bids that fill
before delistings and swaps); counts and power conditional on the future**

**Problem.**
- "No ... bid life or exit window crosses a segment boundary", applied as an exclusion, uses data after placement.
- The calendar implements it as "drop a life with more than 50% of its hours missing".
- K4 scales prices and volumes after a cut but never deletes data, so it cannot catch this.

**Evidence (2.1):**
- 18 of 21 weekly U-B lives that contain a dead coin's last trade were dropped, and 5 U-Q1 weeks.
- On 90-day lives, 10 dropped bid-lives (AGIX, D, FTM, RNDR) would have filled before trading stopped.

**Replacement (§4.4, Segments, first bullet):**
> Bids are placed from information at t0 only. When a segment boundary or the end of trading arrives during a bid's
> life, the bid is cancelled at the boundary; fills before it stand. A position open at the boundary is valued by the
> swap, redenomination or delisting rules below. No placement, bid life, fill or exit is dropped or shortened because
> of data after its own time stamp. σ windows and level look-backs still never reach back across a boundary.

**Add to §11.2, K4:**
> **K4b Data-availability look-ahead.** At each K4 cut t:
> 1. delete every bar of that coin after t, as if it stopped trading at t;
> 2. separately, insert a 3-day gap after t.
>
> In both cases, every universe membership, placement, level, fill and exit decision stamped before t must be
> unchanged, for every life.

**Also:**
- Rebuild the fill calendar under this rule and restate §7.4's counts before the freeze.
- This matches S10 of the statistics critique (twins through delistings).

### V3. Model the exit latency of a user who sells by hand

**must · §9 (X-FLIP, time stops), §8.2, §11.1 B-TWIN, §11.2 K2, §12.3 H1, §12.5, §15.1 (flip target), §15.2 step 4 ·
false positive or false negative (sign unknown); interpretability (the sheet's flip advice assumes a bot)**

**Problem.**
- X-FLIP's limit sell is "live from the minute after the fill".
- The brief's user places orders himself, and cannot place the sell before he owns the coin.
- The engine therefore simulates a bot, while the sheet gives the result to a person.

**Evidence (2.5):**
- 38% of P1 fills started between 00:00 and 06:59 ET or on a weekend.
- In synthetic wicks with a brief rebound, the flip's mean moves by −2.6 to +5.7 points between a 1-minute and a
  60- or 480-minute latency. That is comparable to H1's MDE of 4.6-6.1%.

**Replacement (§9, the X-FLIP row):**
> **Live time.** The limit sell at R½ is live from fill + ℓ. Primary ℓ (manual, as in the brief): 60 minutes after
> the fill when that falls between 07:00 and 22:59 America/New_York, else 07:00 New York time the next morning.
> Sensitivities: ℓ = 1 minute (labelled "bot") and ℓ = 8 hours.
>
> **Execution.** If the price is at or above R½ when the sell goes live, it executes at that minute's open as a
> marketable limit: taker cost under C-EX, the bid side under F3. Otherwise it fills in the first later minute with
> high ≥ R½ + τ.
>
> **Time stop.** The 72-hour time stop sells at the first live minute (same clock rule) at or after fill + 72 h.
>
> **Twins** apply the same ℓ rule from their entry minute.

**Consequential edits:**
- **§12.3 H1** uses the primary ℓ; the bot row is reported beside it.
- **K2** passes under both ℓ rules.
- **§12.5:** the power study is re-run with ℓ (with S18 of the statistics critique).
- **§15.2 step 4:** "...enter the limit sell as soon as you see the fill; the study's numbers assume you do so within
  an hour in the daytime, or at 7 am after a night fill."

### V4. Specify the F3 venue gate as measured

**should · §8.1 (F3 row; "How much F3 removes"), §8.2 (outages), §4.2 (index fetch), §9 (route-specific exits), §11.2
K8, §12.3 (H1 gate) · interpretability (the draft's haircut is half the measured one); false positive (a spot
fallback lets Binance-only prints pass the gate)**

**Evidence (2.6):**
- F3 removes 10.3% of F1 fills at s = 1% and 23.7% at s = 3%, against the draft's 5-8% and "a fifth".
- The seven largest fill days keep 96-100%.
- F3d (dwell) keeps 80.0%.
- 37 index day-files are missing at minute resolution, including ETH and LTC on 2020-03-12.
- The index klines count updates, not trades.
- USD conversion changes 10 of 1,247 fills.

**Replacement (§8.1, F3 row and the paragraph after the table):**
> **Series.** F3 uses only the USD-M index price.
>
> **Missing index.** Where the index minute is missing (no contract yet, or an archive gap), the fill is
> "F3-unverifiable". It is not an F3 fill, and the unverifiable share is reported by event; there is no fallback to
> Binance spot.
>
> **Index outages.** An index minute is an outage when it is missing or has fewer than 30 index updates (the klines'
> count field). Outages block F3 fills and F3 exits. Documented Robinhood outage windows ±1 h block exits as well as
> fills.
>
> **Fetch rule.** Index days are fetched where the 1d index low or the 1d spot low comes within 5% of L/(1 + s) or
> L.
>
> **Exit spread.** In the crash-spread rows (s = 2, 3, 5%), the exit spread within 24 h of the fill is s, not 0.95%.
>
> **How much F3 removes.** Measured on the P1 calendar, weekly life: 10.3% of F1 fills at s = 1%, 18.3% at 2%, 23.7%
> at 3%, 34.1% at 5%. The seven largest fill days keep 96-100% at s = 1%, so F3 mostly trims the smaller episodes;
> it is not a test of whether the big crashes were Binance-only. F3d (a whole index minute below L/1.01) keeps 80%.
>
> **H1 gate.** Δ > 0 under F3 (s = 1%), also reported under F3d and under F3 at s = 3%. If F3 and F3d disagree in
> sign, the verdict sentence says "only on brief index dips".
>
> **K8** reports, for every fill, F3 at s = 1% with the index converted to USD (hourly USDC/USDT proxy). It changed
> 10 of 1,247 fills here.

### V5. K5: allow gap-through fills at the limit price

**should · §11.2 K5 · false positive (if the engine is bent to pass K5, gap-through crash fills get a better price
than the limit); a stopped run**

**Evidence (2.4):**
- 17 P1 fill minutes (1.3%) lie wholly below L, 3 of them true gaps after a minute that closed above L.
- A resting bid would have traded at L. So L is correct and lies outside the minute's range.

**Replacement (§11.2, K5):**
> **K5 Fill audit.**
> - Every resting order fills at its limit price, in a minute with trades > 0 after its live time, whose low ≤
>   limit − τ (bids) or high ≥ limit + τ (sells).
> - A marketable order (already through its limit when it goes live) fills at that minute's open.
> - A fill price outside the minute's [low, high] is allowed only for a resting order in a minute that gapped through
>   it. Such fills are listed and counted.
> - Any other violation stops the run.

### V6. Place the bids when the data exist: one information set per source

**should · §6.1 (P0, σ30, d0), §6.2 (M6-M8), §7.1 (P1 placement), §13 (sensitivity rows), §15.1-15.2 · false
positive (the backtest uses fresher prices and open interest than a live user can); interpretability (the
instructions cannot be followed)**

**Evidence (2.2):**
- Spot files for day d appear at 01:36-03:12 UTC on d + 1. Futures metrics appear at 06:34-08:19, and index and mark
  klines at 07:36-12:59.
- 1.3% of P1 fills came in the first 3 hours of the weekly life and 2.3% in the first 12. Nearly all are on two
  market-wide Monday crashes (2025-02-03, 2024-08-05).

**Replacement (§7.1, the P1 schedule row, and §6.1):**
> **Placement.** Monday 03:30 UTC (Sunday 10:30 pm EST / 11:30 pm EDT).
>
> **Inputs.**
> - P0, σ30, ATR and every spot-based level use Binance spot data through Sunday (d0).
> - Futures-based inputs use data through Saturday (d0 − 1), the last day published by 03:30 UTC. These are M7's open
>   interest and mark prices, and HYPE's index.
>
> **Overlap.** The previous week's bids stay live until the new ones are placed.
>
> **Sensitivity.** Placement at Monday 13:30 UTC (US morning) with the same inputs.

**Consequential edits:**
- **§6.2, M7:** "...crossed by a later 1h mark-price low, up to the last mark-price bar published before t0".
- **§15.2:** "weekly, after 03:30 UTC on Monday (Sunday 10:30 pm EST / 11:30 pm EDT)".
- **The sheet** refuses to print a weekly sheet from spot data older than d0 unless `--price` is given.

### V7. Per-fill samples must not depend on the one-position rule

**should · §7.1 (last bullet), §12.3 (H2, H5), §12.5, §13 (D8) · interpretability (H2's power uses 1,244 fills; the
rule gives 887; D8 is undefined); a sample tilted to first fills**

**Evidence (2.9):** the drafted rule keeps 97% of P1 fills under the flip, 70% under a 90-day hold and 36% under a
365-day hold.

**Replacement (§7.1, last bullet):**
> Per-fill tests and descriptive estimands use every fill of the bid program. Each bid-week is an independent order
> with its own cash, whatever positions are open. The one-position-per-rung rule applies only to the accounts (D7).
> Every exit (flip, 90-day and other holds) is evaluated on the same fill set, so D8 is a paired comparison.

### V8. Say which fills a Robinhood user could have had

**should · §0 ("at fills the user could actually have obtained"), §12.6 ("You could run it on Robinhood"), §14 ·
interpretability; false positive for the practical claim**

**Evidence (2.10):** 36% of P1 fills are on coins Robinhood does not list today. Most of the rest came before their
coin was on Robinhood [U].

**Replacement:**
> §0: "It asks this at fills a resting bid on Binance spot could have obtained, with a Robinhood-route haircut (F3)
> and a subset of Robinhood-listed coins."
>
> §14 and every headline: add a row for P1 restricted to coins in Robinhood's 2026-11-18 catalog (hindsight,
> labelled), on F3.
>
> §12.6: "You could run it on Robinhood" also requires Δ > 0 on that row.

### V9. Delisting days, redenominations and data gaps

**should · §4.4 (Rebrands and swaps; Delistings and collapses; Segments), §12.3 (H5's knife rule) · false positive or
false negative in U-B (H5's population; H1's U-B gate): spurious −30% at redenominations, or ±99.9% artifacts if read
across them; a noisy valuation price**

**Evidence (2.11):**
- SUN (×0.001) and COCOS (×1,000) gaps sit inside U-B fill windows. BNX, DREP and BTCST have similar gaps. None is on
  the swap list.
- On the delisting day, the last trade differs from that day's VWAP by more than 10% for 23 of 133 dead U-B coins.
- 162 U-B fills reach the end of trading within 365 days.

**Replacement (§4.4):**
> **Redenominations.** A segment boundary across which the next open / last close lies within ±5% of 10^n (n ≠ 0) is
> joined at ratio 10^n, once confirmed from the exchange's announcement; it is not a delisting. The swap list adds
> SUN (2021-06), COCOS (2021-01), BNX (2023-02), DREP (2021-03), BTCST (2021-03), STRAX and VIDT [U: ratios to
> confirm].
>
> **Delisting valuation.** A position open when a coin stops trading is valued at the VWAP of its last full trading
> day (quote volume / volume) × (1 − 0.30). The last trade × (1 − 0.30) is a sensitivity, beside the 0% and 100%
> haircuts.
>
> **Relistings.** A gap followed by renewed trading at an unrelated price (FTT, 310 days) is a delisting at the gap's
> start; the relisting starts a new segment.
>
> **H5's knife rule** reads the 365th day's VWAP, not a single minute's price.

### V10. Make F1 + C-RH's Robinhood meaning explicit; feed the sheet from F3

**should · §8.1, §10, §15.1 · interpretability (the sheet prints a different bid from the one H1 tests)**

**Problem.**
- On Robinhood's default route the user never pays more than the limit. The spread decides when the order fills
  (ask ≤ limit), not what it costs (`mechanics.md` §1.2).
- A fill "at L plus 0.95%" (F1 + C-RH) is therefore the market-maker-route bid placed at about L × 1.0095, which
  triggers when the mid reaches about L.
- The sheet prints L, which triggers when the mid reaches L/1.01. That bid is about 1% (≈0.23σ) deeper.

**Replacement:**
> §8.1 adds: "F1 + C-RH corresponds to a Robinhood market-maker-route bid at L × (1 + c_b), triggered when the mid
> reaches about L. F3 corresponds to the bid the sheet prints (limit L, triggered at L/(1 + s))."
>
> §15.1: the fill odds, flip target and post-fill outcomes shown to the user come from F3 rows. F1 rows are labelled
> "Binance spot, Robinhood cost added".

### V11. The bad-print sensitivity must not read the next minute

**could · §4.4 (Bad prints), §13 (sensitivity rows) · false negative in that row (it drops the fills followed by an
instant snap-back, which selects on the outcome); a look-ahead inside a sensitivity**

**Evidence (2.7):**
- No P1 fill is an isolated print: none had one minute below L with less than $1k of seller volume.
- 14.1% of P1 fills had a single minute below L in the capacity window.

**Replacement (§4.4, Bad prints):**
> Bad prints are real trades and are kept in F1. The sensitivity drops F1 fills whose fill minute alone had less than
> $1k of seller-initiated notional below L, or whose index low in that minute stayed above L. Nothing after the fill
> minute is used.

### V12. Rebrand successors inherit listing age and rank

**could · §4.4 (Ticker reuse; Rebrands and swaps), §5.1 (Listing age) · false negative (coverage): 37 U-Q1
coin-months lost, all on coins Robinhood lists**

**Replacement (§4.4):**
> A rebrand or swap successor (the list above) inherits the predecessor's listing age and monthly ranks. A ticker
> reuse (a different asset, such as LUNA from 2022-05-31) restarts both.

### V13. Capacity: causal, and labelled by route

**could · §8.3, §11.2 (K4's capacity exemption; K6) · interpretability**

**Evidence (2.7):** capacity rarely binds at $10k and binds for 17-34% of fills at $100k. C₁ tracks aggTrades
(median ratio 0.98).

**Replacement (§8.3):**
> **Causal fills.** The filled quantity accumulates minute by minute from trades up to that minute; positions,
> exits and accounts use only what has filled so far. K4's capacity exemption is removed.
>
> **Labels.** Capacity is labelled "Binance spot book". On the market-maker route the market maker decides the fill
> size [U], so F3 rows show capacity only as context.

### V14. Route-specific advice; an honest F4 proxy

**could · §8.1 (F4), §13 (D9), §15.1 (round-number row), §15.2 (route text) · false positive in the F4 row;
interpretability of D9**

**Problem.**
- **F4 is not a Bitstamp proxy.** F4 uses Binance spot trade-through as a stand-in for Bitstamp's single, thinner
  book. Robinhood warns that exchange-routed orders may not fill when the price is available only elsewhere
  (`mechanics.md` §1.2).
- **D9's advice is a queue effect.** "Bid one tick above round numbers" helps on an order book. On the default route
  the order fills only when the mid is about 1% below the limit, so one tick does not matter.

**Replacement:**
> **F4** uses the index reaching L (s = 0), with C-EX costs, for coins eligible for exchange routing [U: eligibility
> list]. It is labelled "exchange route, composite-price proxy; Bitstamp depth unknown".
>
> **D9's round-number advice** appears on the sheet only for the exchange route.

### V15. Ticks and order sizes

**could · §6.1 (τ), §11.2 K7, §15.1 (limit price) · interpretability**

**Replacement:**
> **Binance's tick.** τ is inferred from the decimal strings of the last 7 days' 1m prices (the smallest step), not
> from a floating-point GCD.
>
> **Robinhood's tick.** The sheet recomputes δ after rounding to Robinhood's tick. When rounding moves the level by
> more than 0.05σ, it reads the fill odds at the rounded depth.
>
> **K7** also checks each sheet order against the saved catalog's quantity increment and its minimum and maximum
> order size (HYPE: 0.001 and 7,000), and splits orders above the maximum.

---

## 4. Summary of proposals

| # | severity | sections | change | bias if left |
|---|---|---|---|---|
| V1 | must | 11.2 (K1, K2) | K1b against a path oracle, with two negative checks | false negative (stops a correct run); false positive |
| V2 | must | 4.4, 7.1, 7.4, 11.2 (K4), 16 | causal segment and delisting handling; K4b truncation and gap test; rebuild the calendar | false positive |
| V3 | must | 9, 8.2, 11.1, 11.2, 12.3, 12.5, 15.1-15.2 | manual exit latency (clock rule) for fills, time stops and twins | either direction; interpretability |
| V4 | should | 8.1, 8.2, 4.2, 9, 11.2 (K8), 12.3 | F3 haircut as measured; no spot fallback; index outages; exit spreads; F3d beside the gate | interpretability; false positive |
| V5 | should | 11.2 (K5) | the audit accepts gap-through fills at the limit | false positive; stopped run |
| V6 | should | 6.1, 6.2, 7.1, 13, 15 | placement at 03:30 UTC Monday; futures inputs through d0 − 1 | false positive; interpretability |
| V7 | should | 7.1, 12.3, 12.5, 13 | per-fill samples not thinned by the one-position rule | interpretability |
| V8 | should | 0, 12.6, 14 | a Robinhood-listed row; wording of what was tested | interpretability; false positive |
| V9 | should | 4.4, 12.3 | redenominations joined; VWAP delisting value; the knife test on a daily VWAP | either direction |
| V10 | should | 8.1, 10, 15.1 | the sheet's numbers come from F3 rows | interpretability |
| V11 | could | 4.4, 13 | bad-print rule within the fill minute | false negative |
| V12 | could | 4.4, 5.1 | successors inherit age and rank | false negative (coverage) |
| V13 | could | 8.3, 11.2 | causal capacity; labelled by route | interpretability |
| V14 | could | 8.1, 13, 15 | F4 from the index; round-number advice only for the exchange route | false positive; interpretability |
| V15 | could | 6.1, 11.2 (K7), 15.1 | decimal tick inference; Robinhood rounding; order-size checks | interpretability |

---

## 5. Reproducing these checks

The scripts are in this session's scratchpad, in
`/tmp/claude-0/-home-user-moneyline-upgrade/5e565363-4044-518a-a642-8a4d3835a58f/scratchpad/critique_fid/`. They will
not survive the session; section 1 gives their method.

- **Running them.** Each runs with `python3 -I <script> <repo root>` and reads the draft's
  `../design_sim/fillcal7.parquet`.
- **Derived data.** Under `data/stinkbid/critique_fidelity/` (gitignored, about 211 MB).

| script | what it does |
|---|---|
| `fetch_idx1d.py` | USD-M 1d index and last-price klines for the U-Q1 coins (`um1d_q1.parquet`) |
| `f3_daily.py` | weekly F3 (s = 0-5%) and F5 survival of F1 fills; by rung, event and half |
| `fetch_m1_filldays.py` | 1m spot (fill day ±1) and 1m index (fill day, +1) for the 854 P1 fill coin-days; missing files in `m1_missing.csv` |
| `m1_checks.py` | hourly/minute consistency; C₁ capacity; s24 at minute resolution; F3 and F3d at minute resolution |
| `k6_mini.py` | C₁ against aggTrades capacity on the inventory's event days |
| `usdt_basis.py`, `usdt_basis_h1.py` | USDT/USD basis between placement and fill (the printed sign label in `usdt_basis_h1.py` is reversed; see 2.6) |
| `counts_misc.py` | one-position thinning; clock time of fills; the Robinhood set; fills before the last trade |
| `dropped_placements.py` | U-Q1 placements missing from the calendar, and why |
| `delist_lives.py` | lives of 7, 30 and 90 days containing a dead coin's last trade: dropped by the rule, and fills before the end |
| `extra_checks.py` | gap-through entries; F3 in USD; U-B delisting weeks; data gaps in windows; delisting-day data; rebrand successors; outage dates; index update counts |
| `sim_k1_latency.py`, `sim_latency2.py` | synthetic: K1b's known answer and exit latency |

The publication times in 2.2 come from S3 listings of the archive (`?prefix=...`), read through the same path-style
URL.

---

## Sources

**Repo:**
- [`design_draft.md`](design_draft.md), [`mechanics.md`](mechanics.md), [`evidence.md`](evidence.md),
  [`data_inventory.md`](data_inventory.md), [`critique_statistics.md`](critique_statistics.md)
- `analysis_2026/fetch_scalping_data.py` (S3 helpers), `analysis_2026/fetch_stinkbid_data.py`
- `analysis_2026/results_scalping/A/arh_pairs.csv` (Robinhood set, 2026-10-18)

**Data:**
- [Binance public data](https://github.com/binance/binance-public-data/): archive layout, checksums, timestamp units.
- The S3 bucket `https://s3-ap-northeast-1.amazonaws.com/data.binance.vision`: file publication times from listing
  `LastModified` [C].

**Robinhood mechanics** (as read and tagged in `mechanics.md`):
- [Crypto order routing](https://robinhood.com/us/en/support/articles/crypto-order-routing/) [A]
- [Buying and selling crypto](https://robinhood.com/us/en/support/articles/crypto-buying-and-selling/) [A]
- [Why hasn't my crypto order filled?](https://robinhood.com/us/en/support/articles/why-hasnt-my-cryptocurrency-order-filled) [A]

**Literature:**
- [Copeland and Galai 1983](https://cris.huji.ac.il/en/publications/information-effects-on-the-bidask-spread/): a
  resting quote as a free option [A, as tagged in `mechanics.md`].
- [Lo, MacKinlay and Zhang 2002](https://web.mit.edu/Alo/www/Papers/limit10.html): hypothetical limit-order
  executions are poor proxies for real ones [A, as tagged in `evidence.md`].
