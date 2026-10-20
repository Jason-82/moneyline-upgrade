"""Crypto universe (README section 10, SPEC section 13): every coin Robinhood offers, filtered and mapped to a vehicle.

`build_universe(cfg, now_utc, inbox_dir)` returns (assets, report). The assets have the config's asset shape: name =
the coin code, class crypto, signal Coinbase <CODE>-USD, vehicle the coin's US spot ETF when one is mapped and the
newest get_equity_tradability capture confirms it on the configured account, else the coin itself (direct crypto).
The report gives every coin considered its outcome and reason. The signals file stores both; `with_universe(cfg,
signals)` re-checks the stored assets against the config and adds them for the planner, the snapshot and reconcile.

Coins the sleeve holds are never dropped by a filter (they are kept "hold only": exits and trims, no new buys), so a
position never loses the asset that sells it. With the universe turned off, the coins of its last scan that the sleeve
still holds stay as hold-only assets until they exit.

Coins in allocation.favorites are scanned past the liquidity cut (min_dollar_volume_usd) and the max_assets cut, and do
not count against max_assets (it keeps the most liquid non-favorites); every other filter applies to them as to any
coin. The report says when a favorite was kept past a cut. A favorite that is also a ticker in universe.equity.symbols
means the stock (config.coin_favorites): that coin is not kept past a cut, so it cannot rename the stock TICKER-STOCK.
"""
from __future__ import annotations

import copy
import json
import urllib.error
from datetime import timedelta
from pathlib import Path

from agentic import calendar as cal
from agentic import data as feeds
from agentic import ledger
from agentic.config import (COIN_CODE, DEFAULT_EXCLUDE, STOCK_SUFFIX, coin_favorites, crypto_universe,
                            favorite_names, paths)
from agentic.snapshot import _pages, _rows, code_for, load_captures, pair_for

PAIRS_STALE_DAYS = 7              # warn when the newest get_currency_pairs capture is older
TRADABILITY_MAX_AGE_DAYS = 7      # an older get_equity_tradability capture confirms nothing
STAGE1_RETRY_HOURS = 12           # a stage-1 call tried this recently (even one that failed) is not asked first again
HOOK_LOG_TAIL = 1 << 20           # bytes of hook.log read for recent failures
DV_BARS = 30                      # median daily dollar volume over the last 30 closed bars
QUOTE_CHUNK = 20                  # get_equity_quotes omits closes above 20 symbols; keep both quote calls at 20
TRADABILITY_CHUNK = 10            # get_equity_tradability takes at most 10 symbols
SCAN_RETRIES, SCAN_TIMEOUT_S = 1, 10.0    # per Coinbase request of the scan (one retry, 10 s)
BREAKER_ERRORS = 2                # network errors in a row after which the scan stops requesting Coinbase
PEG_BARS, PEG_BAND = 90, 0.03     # a coin whose last 90 closes all stay within 3% of their median is pegged
COST_NOTE = ("direct crypto costs about 0.95% per side on Robinhood's default route (check preview_crypto_order); "
             "a spot ETF costs about its spread")
# report categories for the digest's one-line summary
CATEGORIES = ("stablecoin/wrapped", "excluded by config", "not tradable on Robinhood", "no Coinbase pair",
              "Coinbase data error", "stale Coinbase data", "too little history", "illiquid", "beyond max_assets")
REPORT_KEYS = ("coin", "outcome", "reason", "category", "vehicle", "dollar_volume_usd", "bars", "rank", "held",
               "hold_only", "favorite", "favorite_kept")


# ------------------------------------------------------------------ captures

def parse_pairs(rows) -> dict[str, dict]:
    """USD pairs of get_currency_pairs rows: {CODE: {symbol, tradability, display_only, halted, tradable}}."""
    out = {}
    for r in rows:
        if not isinstance(r, dict):
            continue
        sym = str(r.get("symbol") or "").upper().strip()
        ac = r.get("asset_currency") if isinstance(r.get("asset_currency"), dict) else {}
        qc = r.get("quote_currency") if isinstance(r.get("quote_currency"), dict) else {}
        code = str(ac.get("code") or (sym.split("-")[0] if sym else "")).upper().strip()
        quote = str(qc.get("code") or (sym.split("-")[1] if "-" in sym else "USD")).upper().strip()
        if quote != "USD" or not COIN_CODE.match(code):
            continue
        trad = str(r.get("tradability") or "").lower()
        out[code] = dict(symbol=pair_for(code), tradability=trad, display_only=bool(r.get("display_only")),
                         halted=bool(r.get("halted")), tradable=trad == "tradable" and not r.get("display_only"))
    return out


def pairs_capture(inbox_dir, now_utc=None, caps=None) -> dict | None:
    """The newest complete get_currency_pairs fetch (its first page and the cursor pages captured after it) with USD
    pairs: {file, captured_at, age_days, pages, complete, pairs, empty}. A newer fetch without any USD pairs (results
    null or []) is skipped and named in `empty`; if no fetch has any, the newest one with pairs {} (and `empty` its
    own file). None without a capture. Any age is used."""
    now = cal.as_utc(now_utc)
    caps = [c for c in (load_captures(inbox_dir) if caps is None else caps) if not c["error"]]
    first = None
    while True:
        pages, complete = _pages(caps, "get_currency_pairs")
        if not pages:
            return first
        start = pages[0]
        rows = [r for p in pages for r in _rows(p["data"], "results", "pairs")]
        res = dict(file=start["file"], captured_at=ledger.iso_z(start["at"]), pages=len(pages), complete=complete,
                   age_days=round((now - start["at"]).total_seconds() / 86400, 4), pairs=parse_pairs(rows),
                   empty=first["file"] if first else None)
        if res["pairs"]:
            return res
        first = first or dict(res, empty=start["file"])
        caps = [c for c in caps if c["at"] < start["at"]]          # the fetch before it


def _tradability_problem(r: dict) -> str | None:
    if r.get("tradeable") is not True:
        return "tradeable is not true"
    if str(r.get("state") or "").lower() != "active":
        return f"state is {r.get('state')!r}, not 'active'"
    types = [x for x in r.get("account_type_tradabilities") or [] if isinstance(x, dict)]
    if types and not any(str(x.get("account_type_tradability") or "").lower() == "tradable" for x in types):
        return "untradable for every account type"
    if "regular_hours" in (r.get("internal_halt_sessions") or []):
        return f"halted ({r.get('internal_halt_reason') or 'internal halt'})"
    return None


def etf_tradability(inbox_dir, cfg: dict, now_utc=None, caps=None) -> tuple[dict, list[str]]:
    """{TICKER: {ok, why, fractional, captured_at, file}} from get_equity_tradability captures of the configured
    account, the newest per ticker and at most TRADABILITY_MAX_AGE_DAYS old; plus warnings."""
    now = cal.as_utc(now_utc)
    caps = load_captures(inbox_dir) if caps is None else caps
    acct = str((cfg.get("account") or {}).get("account_number") or "").strip()
    out: dict[str, dict] = {}
    warnings: list[str] = []
    for c in caps:                                   # oldest first: the newest capture per ticker wins
        if c["short"] != "get_equity_tradability" or c["error"]:
            continue
        if not acct or acct.upper().startswith("FILL-IN") or \
                str(c["input"].get("account_number") or "").strip() != acct:
            warnings.append(f"get_equity_tradability capture {c['file']} is not for the configured account; ignored")
            continue
        if (now - c["at"]) > timedelta(days=TRADABILITY_MAX_AGE_DAYS):
            continue
        at = ledger.iso_z(c["at"])
        data = c["data"] if isinstance(c["data"], dict) else {"results": c["data"]}
        for r in _rows(data, "results"):
            sym = str(r.get("symbol") or "").upper().strip()
            if sym:
                why = _tradability_problem(r)
                out[sym] = dict(ok=why is None, why=why, captured_at=at, file=c["file"],
                                fractional=str(r.get("fractional_tradability") or "").lower() == "tradable")
        for sym in data.get("not_found") or []:
            out[str(sym).upper().strip()] = dict(ok=False, why="not found on Robinhood", fractional=False,
                                                 captured_at=at, file=c["file"])
    return out, warnings


def recent_attempts(inbox_dir, short: str, now_utc=None, *, base=None,
                    hours: float = STAGE1_RETRY_HOURS) -> tuple[list[dict], bool]:
    """(the `short` captures of the last `hours`, whatever their result: a tool error or a too-large notice too; whether
    a `short` call failed without a capture in that time: a PostToolUseFailure line in hook.log). Fetch-list's stage 1
    asks a call first only while it was not tried, so a failing call never holds up the reads that exits need (the
    normal list asks it again)."""
    now = cal.as_utc(now_utc)
    caps = [c for c in load_captures(inbox_dir, f"*_{short}.json")
            if c["short"] == short and now - c["at"] <= timedelta(hours=hours)]
    failed = False
    try:
        with open(paths(base)["hook_log"], "rb") as fh:          # the tail: the last hours are at the end
            size = fh.seek(0, 2)
            fh.seek(max(0, size - HOOK_LOG_TAIL))
            lines = fh.read().decode("utf-8", "replace").splitlines()[1 if size > HOOK_LOG_TAIL else 0:]
    except OSError:
        lines = []
    for line in reversed(lines):
        try:
            e = json.loads(line)
            ts = ledger.parse_ts(e.get("ts"))
        except (ValueError, AttributeError, RecursionError):     # RecursionError: a damaged line of nested brackets
            continue
        if ts is not None and now - ts > timedelta(hours=hours):
            break
        if e.get("hook") == "post" and e.get("decision") == "failure" and str(e.get("tool")).endswith("__" + short):
            failed = True
            break
    return caps, failed


def sleeve_vehicles(base=None) -> dict[str, set]:
    """Vehicles the sleeve may hold: positive quantities in the last reconciled sleeve, plus every vehicle this system
    placed a buy for since that baseline (it may have filled since). {"equity": {SYMBOL}, "crypto": {CODE}}."""
    out: dict[str, set] = {"equity": set(), "crypto": set()}
    ref = ledger.read_json(paths(base)["positions_ref"], None)
    as_of = None
    if isinstance(ref, dict):
        for kind in out:
            for k, q in ((ref.get("sleeve") or {}).get(kind) or {}).items():
                if (ledger.num(q) or 0.0) > 0:
                    out[kind].add(code_for(k) if kind == "crypto" else str(k).upper())
        as_of = ledger.parse_ts(ref.get("as_of"))
    for p in ledger.journal_index(ledger.read_journal(base))["places"]:
        if p["side"] == "buy" and p["symbol"] and (as_of is None or p["ts"] is None
                                                   or p["ts"] >= as_of - timedelta(days=1)):
            out[p["kind"]].add(code_for(p["symbol"]) if p["kind"] == "crypto" else p["symbol"])
    return out


def last_scan_coins(base=None) -> set[str]:
    """Coin codes of the universe assets in the newest signals file that has a universe section."""
    for f in sorted(paths(base)["signals"].glob("signals_*.json"), reverse=True):
        try:
            uni = json.loads(f.read_text(encoding="utf-8")).get("universe")
        except (OSError, ValueError, AttributeError):
            continue
        if isinstance(uni, dict):
            return {str(a.get("name") or "").upper() for a in uni.get("assets") or [] if isinstance(a, dict)}
    return set()


def captured_holdings(inbox_dir, caps=None) -> dict[str, set]:
    """Vehicles with a positive quantity in the newest get_equity_positions / get_crypto_positions captures."""
    from agentic.snapshot import parse_crypto_positions, parse_equity_positions
    caps = load_captures(inbox_dir) if caps is None else caps
    out: dict[str, set] = {"equity": set(), "crypto": set()}
    for short, kind, parse in (("get_equity_positions", "equity", parse_equity_positions),
                               ("get_crypto_positions", "crypto", parse_crypto_positions)):
        pages, _ = _pages([c for c in caps if not c["error"]], short)
        for p in pages:
            out[kind] |= {k for k, v in parse(p["data"]).items() if (v.get("qty") or 0) > 0}
    return out


# ------------------------------------------------------------------ the builder

def _claims(cfg: dict, u: dict) -> dict[str, str]:
    """Coins an explicit asset covers, {CODE: why}: an asset with the coin's name (enabled or not: a disabled one is
    how a coin is kept out), or an enabled one trading the coin, its mapped ETF, or on its Coinbase signal."""
    out: dict[str, str] = {}
    etf_coin = {etf: coin for coin, etf in u["etf_map"].items()}
    for a in cfg.get("assets", []):
        name = str(a.get("name") or "")
        state = "enabled" if a.get("enabled") else "disabled"
        if COIN_CODE.match(name.upper()):
            why = f"explicit asset {name} ({state}) in config.assets takes precedence"
            if a.get("class") != "crypto":
                why += f" (a {a.get('class')} asset with the coin's name: rename it to let the universe trade the coin)"
            out.setdefault(name.upper(), why)
        if not a.get("enabled"):
            continue
        v, s = a.get("vehicle") or {}, a.get("signal") or {}
        vs = str(v.get("symbol") or "").upper()
        coins = []
        if v.get("type") == "crypto":
            coins.append(code_for(vs))
        elif vs in etf_coin:
            coins.append(etf_coin[vs])
        if s.get("feed") == "coinbase" and str(s.get("symbol") or "").upper().endswith("-USD"):
            coins.append(str(s["symbol"]).upper()[:-4])
        for coin in coins:
            out.setdefault(coin, f"explicit asset {name} trades it ({v.get('type')} {vs})")
    return out


def _start(cfg: dict, u: dict, now) -> object:
    probe = {"class": "crypto", "min_bars": u["min_history_bars"], "signal": {"feed": "coinbase"}}
    return now.date() - timedelta(days=feeds.history_days(probe, cfg))


def _asset(e: dict, u: dict) -> dict:
    code = e["coin"]
    a = {"name": code, "class": "crypto", "enabled": e["outcome"] in ("etf", "direct"), "alloc_frac": 0.0,
         "mode": u["mode"], "signal": {"source": "computed", "feed": "coinbase", "symbol": f"{code}-USD"},
         "vehicle": dict(e["vehicle"]), "min_bars": max(30, e["bars"] or 0) if e.get("young") else
         u["min_history_bars"],
         "universe": {k: e.get(k) for k in ("outcome", "reason", "dollar_volume_usd", "rank", "held", "hold_only")}}
    if u["entry"]:
        a["entry"] = dict(u["entry"])
    return a


def liquidity_cut_note(dv, min_dv: float) -> str:
    """Why a favorite was kept past the liquidity cut (the report's `favorite_kept`)."""
    return f"below the liquidity cut ${dv or 0:,.0f}/day, need ${min_dv:,.0f}"


def cut_max_assets(survivors: list[dict], max_assets: int, drop) -> None:
    """Rank the survivors (sorted by dollar volume, most liquid first) and drop the non-favorites beyond max_assets.
    Favorites do not count against max_assets: it keeps the most liquid non-favorites. A favorite that would have been
    beyond it (as a non-favorite at its place) is kept, and `favorite_kept` says so. A hold-only non-favorite is never
    dropped but still counts, as before."""
    nfav = sum(1 for e in survivors if e.get("favorite"))
    n = 0                                            # non-favorites so far
    for k, e in enumerate(survivors, 1):
        e["rank"] = k
        if e.get("favorite"):
            if n + 1 > max_assets and not e["hold_only"]:
                note = f"beyond max_assets {max_assets} (rank {k} by dollar volume): favorites do not count against it"
                e["favorite_kept"] = f"{e['favorite_kept']}; {note}" if e.get("favorite_kept") else note
            continue
        n += 1
        if n > max_assets and not e["hold_only"]:
            drop(e, f"beyond max_assets {max_assets} (rank {n} of {len(survivors) - nfav} by dollar volume"
                    + (f", not counting {nfav} favorite{'s' if nfav > 1 else ''}" if nfav else "") + ")",
                 "beyond max_assets")


def favorite_note(e: dict) -> None:
    """Append the favorite's kept-past-a-cut note to an included entry's reason."""
    if e.get("favorite_kept"):
        e["reason"] += f"; included (favorite; {e['favorite_kept']})"


def _pegged(bars) -> bool:
    """The last PEG_BARS closes all stay within PEG_BAND of their median (a stablecoin or a pegged token)."""
    c = bars["close"].iloc[-PEG_BARS:]
    return len(c) >= PEG_BARS and float((c / c.median() - 1).abs().max()) <= PEG_BAND


def build_universe(cfg: dict, now_utc=None, inbox_dir=None, fetch=None, *, products=None, held=None,
                   base=None) -> tuple[list[dict], dict]:
    """(assets, report) for this run (module docstring). `fetch(product, start, now)` returns closed daily bars
    (default: the Coinbase cache); `products(now)` the Coinbase product list (default: cached daily); `held` the
    sleeve's vehicles (default: sleeve_vehicles). Never raises for data problems: they become outcomes. After
    BREAKER_ERRORS network errors in a row no further Coinbase request is made (report coinbase_down): the remaining
    coins are scanned from current cached bars only."""
    now = cal.as_utc(now_utc)
    u = crypto_universe(cfg)
    report = dict(enabled=u["enabled"], source=u["source"], generated_at=ledger.iso_z(now), pairs=None,
                  products=None, tradability=None, coinbase_down=None, warnings=[], coins=[], counts={})
    held = sleeve_vehicles(base) if held is None else held
    etf_coin = {etf: coin for coin, etf in u["etf_map"].items()}
    claims = _claims(cfg, u)
    fav = coin_favorites(cfg)                        # a name that is also a stock universe ticker means the stock
    stock_fav = favorite_names(cfg) - fav
    off = not u["enabled"]
    if off:                                          # turned off: its last scan's coins the sleeve still holds
        keep = sorted(c for c in last_scan_coins(base) if c not in claims and
                      (c in held["crypto"] or u["etf_map"].get(c) in held["equity"]))
        if not keep:
            return [], report
    warn = report["warnings"].append
    inbox = Path(inbox_dir) if inbox_dir is not None else paths(base)["inbox"]
    caps = load_captures(inbox)
    if fetch is None:
        def fetch(product, start, now_):
            return feeds.coinbase_daily_cached(product, start, now_, base=base, issues=report["warnings"],
                                               retries=SCAN_RETRIES, timeout=SCAN_TIMEOUT_S)
    products = products or (lambda now_: feeds.coinbase_products(now_, base=base, retries=SCAN_RETRIES,
                                                                 timeout=SCAN_TIMEOUT_S))
    exp = cal.last_closed_crypto_bar(now)
    start = _start(cfg, u, now)

    pc = None if off else pairs_capture(inbox, now, caps)
    rh = pc["pairs"] if pc and pc["pairs"] else None
    if pc and pc["empty"]:
        warn(f"get_currency_pairs capture {pc['empty']} has no USD pairs: "
             + (f"the earlier capture {pc['file']} is used" if rh else
                "only universe.crypto.symbols (and held coins) are scanned"))
    if rh:
        report["pairs"] = {k: pc[k] for k in ("file", "captured_at", "age_days", "pages", "complete")}
        if pc["age_days"] > PAIRS_STALE_DAYS:
            warn(f"the newest get_currency_pairs capture is {pc['age_days']:.0f} days old: run /moneyline (its "
                 "fetch-list captures the pair list)")
        if not pc["complete"]:
            warn("get_currency_pairs: more pages exist (next cursor) but were not captured: coins may be missing")
    elif pc is None and not off and u["source"] == "robinhood":
        warn("no get_currency_pairs capture in the inbox: only universe.crypto.symbols (and held coins) are scanned; "
             "/moneyline's fetch-list captures the pair list")

    coins: dict[str, dict] = {}

    def add(code, src):
        coins.setdefault(code, dict(coin=code, source=src, outcome=None, reason=None, category=None, vehicle=None,
                                    dollar_volume_usd=None, bars=None, rank=None, held=False, hold_only=None,
                                    favorite=code in fav, favorite_kept=None))
    if off:
        for code in keep:
            add(code, "held")
            coins[code]["hold_only"] = "universe.crypto is off: held, so kept for exits only"
    else:
        if u["source"] == "robinhood" and rh:
            for code in sorted(rh):
                add(code, "robinhood")
        for code in u["symbols"]:
            add(code, "symbols")
            coins[code]["source"] = "symbols"        # listed on purpose: the vehicle choice handles Robinhood
        for code in sorted(held["crypto"]):
            add(code, "held")
        for sym in sorted(held["equity"]):
            if sym in etf_coin:
                add(etf_coin[sym], "held")

    exclude = set(u["exclude"])
    prods = products(now) or {}
    plist = prods.get("products")
    report["products"] = dict(fetched_at=prods.get("fetched_at"), count=len(plist or {}), error=prods.get("error"))
    if prods.get("error"):
        warn(prods["error"] + ("" if plist is not None else ": Coinbase availability not checked"))
    online = None if plist is None else {k for k, p in plist.items() if p.get("online")}
    min_bars, min_dv = u["min_history_bars"], u["min_dollar_volume_usd"]
    fails = 0                                        # network errors in a row (the circuit breaker)

    def out(e, outcome, reason, category=None):
        e.update(outcome=outcome, reason=reason, category=category)

    def drop(e, reason, category):
        """Exclude, or keep a held coin hold-only (its position must keep the asset that sells it)."""
        if e["held"]:
            e["hold_only"] = e["hold_only"] or f"{reason}; held, so kept for exits only"
            return False
        out(e, "excluded", reason, category)
        return True

    survivors = []
    for code, e in coins.items():
        e["held"] = code in held["crypto"] or u["etf_map"].get(code) in held["equity"]
        e["rh_tradable"] = None if rh is None else bool(rh.get(code) and rh[code]["tradable"])
        if code in claims:
            out(e, "explicit", claims[code])
            continue
        if code in exclude:
            stable = code in DEFAULT_EXCLUDE
            if drop(e, "stablecoin or wrapped token (universe.crypto.exclude)" if stable else
                    "in universe.crypto.exclude", "stablecoin/wrapped" if stable else "excluded by config"):
                continue
        if e["source"] == "robinhood" and e["rh_tradable"] is False:
            p = rh[code]
            if drop(e, f"not tradable on Robinhood (tradability {p['tradability'] or '?'}"
                       f"{', display only' if p['display_only'] else ''})", "not tradable on Robinhood"):
                continue
        product = f"{code}-USD"
        if online is not None and product not in online:
            why = "Coinbase pair is not online" if product in plist else "no Coinbase pair"
            if drop(e, f"{why} {product}", "no Coinbase pair"):
                continue
        try:
            if report["coinbase_down"]:              # no more requests: current cached bars or nothing
                bars = feeds.coinbase_daily_cached(product, start, now, base=base, offline=True)
                if not len(bars) or bars.index[-1] < feeds._day(exp):
                    raise feeds.DataError("no current cached bars")
            else:
                bars = fetch(product, start, now)
            bars = bars[bars.index <= feeds._day(exp)]
            fails = 0
        except Exception as exc:                     # one coin's data must not stop the scan
            if report["coinbase_down"]:
                drop(e, f"Coinbase unreachable: not scanned ({type(exc).__name__}: {str(exc)[:120]})",
                     "Coinbase data error")
            elif isinstance(exc, urllib.error.HTTPError) and exc.code == 404:
                fails = 0
                drop(e, f"no Coinbase pair {product}", "no Coinbase pair")
            else:
                drop(e, f"Coinbase data error ({type(exc).__name__}: {str(exc)[:120]})", "Coinbase data error")
                fails = fails + 1 if isinstance(exc, OSError) else 0       # URLError, timeouts, connection resets
                if fails >= BREAKER_ERRORS:
                    report["coinbase_down"] = f"{fails} Coinbase requests in a row failed"
                    warn(f"Coinbase unreachable ({report['coinbase_down']}): no further requests this run; the "
                         "remaining coins are scanned from current cached bars only")
            if not e["held"]:
                continue
            survivors.append(e)
            continue
        dv = feeds.median_dollar_volume(bars, DV_BARS)
        e.update(bars=int(len(bars)), dollar_volume_usd=None if dv is None else round(dv, 2))
        last = bars.index[-1].date() if len(bars) else None
        if last != exp:
            if drop(e, f"stale Coinbase data (last bar {last or 'none'}, expected {exp})", "stale Coinbase data"):
                continue
        elif len(bars) < min_bars:
            if drop(e, f"too little history ({len(bars)} bars, need {min_bars})", "too little history"):
                continue
            e["young"] = True                        # held: its exit signal runs on the bars it has (see _asset)
        elif _pegged(bars):
            if drop(e, f"stablecoin or pegged token (its last {PEG_BARS} closes stay within {PEG_BAND:.0%} of their "
                       "median)", "stablecoin/wrapped"):
                continue
        elif dv is None or dv < min_dv:
            if e["favorite"] and not e["hold_only"]:     # scanned past the liquidity cut; every other filter applies
                e["favorite_kept"] = liquidity_cut_note(dv, min_dv)
            elif drop(e, f"illiquid (median ${dv or 0:,.0f}/day over the last {DV_BARS} bars, need ${min_dv:,.0f})",
                      "illiquid"):
                continue
        survivors.append(e)
    survivors.sort(key=lambda e: (-(e["dollar_volume_usd"] or 0.0), e["coin"]))
    cut_max_assets(survivors, u["max_assets"], drop)
    for e in coins.values():                         # a favorite meant for the stock of the same name
        code = e["coin"]
        if code in stock_fav and e["outcome"] == "excluded" and e["category"] in ("illiquid", "beyond max_assets"):
            e["reason"] += (f"; not kept as a favorite: {code} is also a ticker in universe.equity.symbols, so the "
                            f"favorite means the stock (list {code}{STOCK_SUFFIX} to favor the stock in every case)")
    kept = [e for e in survivors if e["outcome"] is None]

    tr, trw = etf_tradability(inbox, cfg, now, caps)
    report["warnings"] += trw
    report["tradability"] = {sym: {k: t[k] for k in ("ok", "why", "fractional", "captured_at")}
                             for sym, t in tr.items() if sym in etf_coin}
    for e in kept:
        _vehicle(e, u, held, tr)
        favorite_note(e)
    assets = [_asset(e, u) for e in kept]
    order = {"etf": 0, "direct": 1, "watch": 2, "explicit": 3, "excluded": 4}
    report["coins"] = [{k: e[k] for k in REPORT_KEYS}
                       for e in sorted(coins.values(), key=lambda e: (order[e["outcome"]], e["rank"] or 10**6,
                                                                      -(e["dollar_volume_usd"] or 0), e["coin"]))]
    counts: dict[str, int] = {}
    for e in coins.values():
        key = e["outcome"] if e["outcome"] != "excluded" else f"excluded: {e['category']}"
        counts[key] = counts.get(key, 0) + 1
    report["counts"] = counts
    if (cfg.get("allocation") or {}).get("method") != "slots" and any(a["enabled"] for a in assets):
        warn("allocation.method is fixed: universe coins have alloc_frac 0, so they are never bought; a held one is "
             "kept until its signal turns red (or FLATTEN), then sold; use allocation.method slots (README section 9)")
    return assets, report


def _vehicle(e: dict, u: dict, held: dict, tr: dict) -> None:
    """Choose the vehicle of an included coin and set its outcome (etf / direct / watch)."""
    code = e["coin"]
    mapped = u["etf_map"].get(code)
    etf = mapped if u["prefer_etf"] else None
    direct = {"type": "crypto", "symbol": code}
    if code in held["crypto"]:                       # manage a direct holding directly until it exits
        e["vehicle"] = direct
        if etf:
            e["hold_only"] = e["hold_only"] or (f"the sleeve holds {code} directly while the ETF {etf} is "
                                                "preferred: exits and trims only (new buys go through the ETF)")
        elif not u["direct_crypto"]:
            e["hold_only"] = e["hold_only"] or "direct_crypto is false: the direct holding is kept for exits only"
        e.update(outcome="direct", reason="held directly by the sleeve")
    elif mapped and mapped in held["equity"]:        # manage an ETF holding through it, confirmed or not
        t = tr.get(mapped) or {}
        e["vehicle"] = {"type": "equity", "symbol": mapped, "fractional": t.get("fractional", True)}
        if not etf:
            e["hold_only"] = e["hold_only"] or f"prefer_etf is false: the {mapped} holding is kept for exits only"
        if not t.get("ok"):                          # sells only until a capture confirms it again
            why = t.get("why") or f"no get_equity_tradability capture in the last {TRADABILITY_MAX_AGE_DAYS} days"
            e["hold_only"] = e["hold_only"] or f"{mapped} not confirmed tradable ({why}): exits only"
        e.update(outcome="etf", reason=f"held through {mapped} by the sleeve")
    elif etf:
        t = tr.get(etf)
        if t and t["ok"]:
            e["vehicle"] = {"type": "equity", "symbol": etf, "fractional": bool(t["fractional"])}
            e.update(outcome="etf", reason=f"spot ETF {etf}, tradable on the account ({t['captured_at']})"
                     + ("" if t["fractional"] else "; whole shares only"))
        else:
            e["vehicle"] = {"type": "equity", "symbol": etf, "fractional": True}
            why = t["why"] if t else (f"no get_equity_tradability capture for {etf} in the last "
                                      f"{TRADABILITY_MAX_AGE_DAYS} days")
            e.update(outcome="watch", reason=f"ETF {etf} not confirmed tradable ({why}): signal only this run, never "
                                             "switched to direct crypto")
    elif not u["direct_crypto"]:
        e.update(vehicle=direct, outcome="watch", reason="direct_crypto is false: watched, not traded")
    elif e.get("rh_tradable") is False:
        e.update(vehicle=direct, outcome="watch", reason=f"no tradable Robinhood pair {code}-USD: watched, not traded")
    else:
        e.update(vehicle=direct, outcome="direct", reason=f"direct crypto {code}-USD (no spot ETF mapped)")
    if e["hold_only"]:
        e["reason"] += f"; hold only: {e['hold_only']}"


# ------------------------------------------------------------------ for the planner, snapshot and fetch-list

def with_universe(cfg: dict, signals: dict | None) -> tuple[dict, list[str]]:
    """The config plus the universe assets the signals file was computed with, each re-checked against this config:
    its name is a coin code no explicit asset covers, its signal is Coinbase <CODE>-USD, and its vehicle is the coin
    itself or the coin's etf_map ETF (as the config allows; a watch-only or hold-only asset either way, since it is
    never bought). With the universe off only hold-only assets are kept. Returns (config, warnings about ignored
    assets)."""
    gen = ((signals or {}).get("universe") or {}).get("assets") or []
    if not gen:
        return cfg, []
    u = crypto_universe(cfg)
    out, warnings, off = copy.deepcopy(cfg), [], 0
    claims, names = _claims(cfg, u), {str(a.get("name")) for a in cfg.get("assets", [])}
    for a in gen:
        code = str((a or {}).get("name") or "").upper()
        v = (a or {}).get("vehicle") or {}
        vt, vs = v.get("type"), str(v.get("symbol") or "").upper()
        hold_only = bool(((a or {}).get("universe") or {}).get("hold_only"))
        never_bought = hold_only or (a or {}).get("enabled") is not True
        if not u["enabled"] and not hold_only:
            off += 1
            continue
        problem = None
        if not COIN_CODE.match(code) or a.get("class") != "crypto" or a.get("name") != code:
            problem = "not a coin code"
        elif code in claims or code in names:
            problem = "an explicit asset covers it"
        elif (a.get("signal") or {}).get("feed") != "coinbase" or \
                str((a.get("signal") or {}).get("symbol") or "").upper() != f"{code}-USD":
            problem = "signal is not Coinbase " + f"{code}-USD"
        elif not ((vt == "crypto" and vs == code and (u["direct_crypto"] or never_bought)) or
                  (vt == "equity" and vs == u["etf_map"].get(code) and (u["prefer_etf"] or never_bought))):
            problem = f"vehicle {vt} {vs} is not one the universe settings allow"
        if problem:
            warnings.append(f"universe asset {code or '?'} in the signals file does not match the config ({problem}): "
                            "ignored; re-run signals")
            continue
        b = {"name": code, "class": "crypto", "enabled": a.get("enabled") is True, "alloc_frac": 0.0,
             "mode": u["mode"], "signal": {"source": "computed", "feed": "coinbase", "symbol": f"{code}-USD"},
             "vehicle": {"type": vt, "symbol": vs, "fractional": v.get("fractional") is True},
             "min_bars": u["min_history_bars"], "universe": dict(a.get("universe") or {})}
        if u["entry"]:
            b["entry"] = dict(u["entry"])
        out["assets"].append(b)
        names.add(code)
    if off:
        warnings.append(f"{off} universe assets in the signals file are ignored: universe.crypto is off (only the "
                        "coins the sleeve holds are kept, for exits); re-run signals")
    return out, warnings


def stage1_etfs(cfg: dict, now_utc=None, inbox_dir=None, *, base=None) -> list[str] | None:
    """The first run of the crypto universe (source robinhood, no get_currency_pairs capture with data yet, and none
    tried in the last STAGE1_RETRY_HOURS): the mapped ETFs whose tradability fetch-list checks with the pair list; None
    when no stage 1 is needed."""
    now = cal.as_utc(now_utc)
    inbox = Path(inbox_dir) if inbox_dir is not None else paths(base)["inbox"]
    u = crypto_universe(cfg)
    if not (u["enabled"] and u["source"] == "robinhood" and pairs_capture(inbox, now) is None
            and not any(recent_attempts(inbox, "get_currency_pairs", now, base=base))):
        return None
    claims = _claims(cfg, u)
    return sorted({etf for coin, etf in u["etf_map"].items() if coin not in u["exclude"] and coin not in claims})


def fetch_needs(cfg: dict, now_utc=None, inbox_dir=None, *, base=None, build=None) -> dict:
    """What fetch-list adds for the universe: the etf_map tickers of the included coins (get_equity_tradability, to
    choose vehicles) and quotes for every held universe vehicle and every universe coin that is green and
    entry-eligible on today's crypto signals (computed here from the Coinbase cache): its ETF when one is mapped,
    else its pair. {stage1, tradability, equity_quotes, crypto_quotes, candidates, crypto_vehicles, report}
    (crypto_vehicles: an enabled universe asset trades a coin, so crypto positions and orders are needed). Without
    any get_currency_pairs capture (source robinhood) it is stage 1: the pair list and every mapped ETF's
    tradability first, then fetch-list again. With the universe off: the held coins of its last scan only."""
    from agentic import entry
    from agentic.signals import asset_signal
    now = cal.as_utc(now_utc)
    inbox = Path(inbox_dir) if inbox_dir is not None else paths(base)["inbox"]
    u = crypto_universe(cfg)
    etfs = stage1_etfs(cfg, now, inbox, base=base)
    if etfs is not None:                             # first run: the coin list first, then fetch-list again
        return dict(stage1=True, tradability=etfs, equity_quotes=[], crypto_quotes=[], candidates=[],
                    crypto_vehicles=False, report=None)
    assets, report = (build or build_universe)(cfg, now, inbox, base=base)
    included = [c for c in report["coins"] if c["outcome"] in ("etf", "direct", "watch")]
    tradability = sorted({u["etf_map"][c["coin"]] for c in included if c["coin"] in u["etf_map"]})
    held, caught = sleeve_vehicles(base), captured_holdings(inbox)
    held = {k: held[k] | caught[k] for k in held}
    recorded = entry.recorded_start(base) or ""
    offline = bool(report.get("coinbase_down"))
    eq, cr, cands = set(), set(), []
    for a in assets:
        v = a["vehicle"]
        is_held = (v["symbol"] in held["crypto"]) if v["type"] == "crypto" else (v["symbol"] in held["equity"])
        known_bad = (report.get("tradability") or {}).get(v["symbol"], {}).get("ok") is False
        if not a["enabled"] and not is_held and (v["type"] == "crypto" or known_bad):
            continue                                 # watched, not traded today: no quote needed
        s = asset_signal(a, cfg, now, inbox, recorded, offline=offline)
        if not is_held and (s["errors"] or not (s.get("target_frac") or 0) > 0 or not (s.get("entry_frac") or 0) > 0):
            continue
        cands.append(a["name"])
        (cr.add(pair_for(v["symbol"])) if v["type"] == "crypto" else eq.add(v["symbol"]))
    return dict(stage1=False, tradability=tradability, equity_quotes=sorted(eq), crypto_quotes=sorted(cr),
                candidates=cands, report=report, assets=assets,
                crypto_vehicles=any(a["enabled"] and a["vehicle"]["type"] == "crypto" for a in assets))


def chunks(xs: list, n: int) -> list[list]:
    return [xs[i:i + n] for i in range(0, len(xs), n)]


def favorites_kept(entries) -> str:
    """The summary line's note on included favorites kept past the liquidity or max_assets cut ("" without any)."""
    n = sum(1 for e in entries if e.get("favorite_kept") and e.get("outcome") not in ("explicit", "excluded"))
    return f", incl. {n} favorite{'s' if n > 1 else ''} kept past the liquidity or max_assets cut" if n else ""


def summary_lines(report: dict | None, full: bool = False) -> list[str]:
    """The digest's universe section: one summary line, the cost note, watch-only and hold-only coins and favorites
    kept past a cut; every coin's outcome with `full`."""
    if not report or not (report.get("enabled") or report.get("coins")):
        return []
    coins = report.get("coins") or []
    c = report.get("counts") or {}
    pairs = report.get("pairs")
    src = ("off: held coins only, kept for exits" if not report.get("enabled") else
           (f"Robinhood pairs captured {pairs['captured_at']}" if pairs else "no Robinhood pair list")
           if report.get("source") == "robinhood" else "universe.crypto.symbols")
    inc = sum(c.get(k, 0) for k in ("etf", "direct", "watch"))
    exc = ", ".join(f"{c[f'excluded: {k}']} {k}" for k in CATEGORIES if c.get(f"excluded: {k}"))
    lines = [f"UNIVERSE crypto ({src}): {len(coins)} coins considered, {inc} scanned ({c.get('etf', 0)} via ETF, "
             f"{c.get('direct', 0)} direct, {c.get('watch', 0)} watch-only)" + favorites_kept(coins)
             + (f", {c['explicit']} covered by explicit assets" if c.get("explicit") else "")
             + (f"; excluded: {exc}" if exc else "")]
    if c.get("direct"):
        lines.append(f"    cost: {COST_NOTE}")
    for w in report.get("warnings") or []:
        lines.append(f"    WARNING: {w}")
    if full:
        for e in coins:
            vs = (e.get("vehicle") or {}).get("symbol") or "-"
            dv = "-" if e.get("dollar_volume_usd") is None else f"${e['dollar_volume_usd'] / 1e6:,.1f}M"
            lines.append(f"    {e['coin']:<8}{e['outcome']:<9}{vs:<7}{dv:>10}  {e['reason']}")
        return lines
    for e in coins:
        if e["outcome"] == "watch" or e.get("hold_only") or (e.get("favorite_kept") and e["outcome"] != "excluded"):
            lines.append(f"    {e['coin']}: {e['reason']}")
    return lines
