"""Stock universe (README section 13, SPEC section 14): the user's own ticker list (universe.equity.symbols), filtered
and traded as stocks; plus the Robinhood history requests fetch-list makes and the yfinance cross-check against
Robinhood.

`build_equity_universe(cfg, now_utc, inbox_dir)` returns (assets, report) like universe.build_universe: name = the
ticker (TICKER-STOCK when the crypto universe has a coin with that code), class equity, signal = universe.equity.feed
on the ticker, vehicle the ticker itself, fractional when the newest get_equity_tradability capture says so, else
whole shares. The signals file stores them under `universe_equity`; `with_equity_universe(cfg, signals)` re-checks them
for the planner, the snapshot and reconcile. Tickers the sleeve holds are never dropped (hold only: exits, no buys).
"""
from __future__ import annotations

import copy
import json
import math
from datetime import timedelta
from pathlib import Path

import pandas as pd

from agentic import calendar as cal
from agentic import data as feeds
from agentic import ledger
from agentic import universe as cu
from agentic.config import TICKER, crosscheck_applies, equity_universe, paths
from agentic.snapshot import load_captures, parse_equity_quotes

STOCK_SUFFIX = "-STOCK"               # a ticker that equals a crypto universe coin's code
RH_MAX_SYMBOLS = 10                   # get_equity_historicals takes at most 10 symbols
RH_CHARS_PER_BAR = 200                # one daily bar in a get_equity_historicals result (2y SPY: ~85k chars, ~500 bars)
RH_MAX_RESULT_CHARS = 40_000          # Claude Code saves a text result over 50,000 characters to a file (no data)
RH_MAX_BARS_PER_CALL = RH_MAX_RESULT_CHARS // RH_CHARS_PER_BAR    # 200: incremental calls, symbols x expected bars
RH_BACKFILL_SESSIONS = 120            # backfill windows: at most ~120 sessions, one symbol per call
RH_MIN_SPLIT_SESSIONS = 10            # a too-large one-symbol window is halved down to about this
CROSSCHECK_TOL = 0.005                # yfinance close vs Robinhood's raw previous_close
CATEGORIES = ("excluded by config", "covered by the crypto universe", "not found on Robinhood",
              "not tradable on Robinhood", "data error", "stale data", "illiquid", "beyond max_assets",
              "name collision")


def _claims(cfg: dict) -> dict[str, str]:
    """Tickers an explicit asset covers, {TICKER: why}: an asset named like the ticker (enabled or not: a disabled one
    keeps the ticker out), or an enabled one trading it."""
    out: dict[str, str] = {}
    for a in cfg.get("assets", []):
        if isinstance(a.get("universe"), dict):          # generated (an effective config)
            continue
        name = str(a.get("name") or "")
        if TICKER.match(name.upper()):
            why = f"explicit asset {name} ({'enabled' if a.get('enabled') else 'disabled'}) in config.assets takes " \
                  "precedence"
            if a.get("class") != "equity":
                why += (f" (a {a.get('class')} asset with the ticker's name: rename it, e.g. {name.upper()}-COIN, to "
                        "let the universe trade the stock)")
            out.setdefault(name.upper(), why)
        v = a.get("vehicle") or {}
        if a.get("enabled") and v.get("type") == "equity" and v.get("symbol"):
            out.setdefault(str(v["symbol"]).upper(), f"explicit asset {name} trades it")
    return out


def last_scan_tickers(base=None) -> set[str]:
    """Tickers of the stock universe assets in the newest signals file that has a universe_equity section."""
    for f in sorted(paths(base)["signals"].glob("signals_*.json"), reverse=True):
        try:
            uni = json.loads(f.read_text(encoding="utf-8")).get("universe_equity")
        except (OSError, ValueError, AttributeError):
            continue
        if isinstance(uni, dict):
            return {str((a.get("vehicle") or {}).get("symbol") or "").upper()
                    for a in uni.get("assets") or [] if isinstance(a, dict)} - {""}
    return set()


def _start(cfg: dict, u: dict, now):
    probe = {"class": "equity", "min_bars": u["min_history_bars"], "signal": {"feed": u["feed"]}}
    return now.date() - timedelta(days=feeds.history_days(probe, cfg))


def _static(cfg: dict, now, inbox: Path, held: dict, base=None, crypto_assets=()):
    """The candidates and the filters that need no bars: (u, entries, survivors, tradability, report), or None when
    the universe is off and holds nothing."""
    u = equity_universe(cfg)
    report = dict(enabled=u["enabled"], feed=u["feed"], generated_at=ledger.iso_z(now), tradability=None,
                  data_down=None, warnings=[], tickers=[], counts={})
    held_eq = {str(x).upper() for x in held.get("equity") or ()}
    last = last_scan_tickers(base)
    if not u["enabled"] and not (last & held_eq):
        return None
    tr, trw = cu.etf_tradability(inbox, cfg, now)
    report["warnings"] += trw
    claims = _claims(cfg)
    crypto_veh = {str((a.get("vehicle") or {}).get("symbol") or "").upper(): a["name"] for a in crypto_assets
                  if (a.get("vehicle") or {}).get("type") == "equity"}
    ents: dict[str, dict] = {}

    def add(t, src):
        ents.setdefault(t, dict(ticker=t, name=t, source=src, outcome=None, reason=None, category=None, vehicle=None,
                                dollar_volume_usd=None, bars=None, rank=None, held=t in held_eq, hold_only=None))
    if u["enabled"]:
        for t in u["symbols"]:
            add(t, "symbols")
    for t in sorted(last & held_eq):
        add(t, "held")
    pending = []
    for t, e in ents.items():
        if not u["enabled"]:
            e["hold_only"] = "universe.equity is off: held, so kept for exits only"
        elif e["source"] == "held":
            e["hold_only"] = "no longer in universe.equity.symbols: held, so kept for exits only"
        if t in claims:
            e.update(outcome="explicit", reason=claims[t])
            continue
        if t in crypto_veh:
            e.update(outcome="excluded", reason=f"the crypto universe trades {t} for {crypto_veh[t]}",
                     category="covered by the crypto universe")
            continue
        if t in u["exclude"] and _drop(e, "in universe.equity.exclude", "excluded by config"):
            continue
        tt = tr.get(t)
        if tt and not tt["ok"]:
            nf = tt["why"] == "not found on Robinhood"
            why = ("not found on Robinhood (get_equity_tradability not_found): check the ticker" if nf else
                   f"not tradable on Robinhood ({tt['why']})")
            if _drop(e, why, "not found on Robinhood" if nf else "not tradable on Robinhood"):
                continue
        pending.append(e)
    return u, ents, pending, tr, report


def _drop(e: dict, reason: str, category: str) -> bool:
    """Exclude, or keep a held ticker hold only (its position must keep the asset that sells it)."""
    if e["held"]:
        e["hold_only"] = e["hold_only"] or f"{reason}; held, so kept for exits only"
        return False
    e.update(outcome="excluded", reason=reason, category=category)
    return True


def _fetcher(u: dict, inbox: Path, base, report: dict):
    """Bars for many tickers at once: {SYM: DataFrame | Exception}."""
    def fetch(syms, start, now):
        if u["feed"] == "yfinance":
            r = feeds.yfinance_daily_cached(syms, start, now, base=base, issues=report["warnings"])
            report["data_down"] = r["down"]
            return {**{s: feeds.DataError(m) for s, m in r["errors"].items()}, **r["bars"]}
        got = feeds.load_robinhood_bars(inbox, syms, now, [], cache_dir=feeds.robinhood_cache_dir(base))
        return {s: got[s] if s in got else feeds.DataError(f"no Robinhood daily bars for {s}: run fetch-list")
                for s in syms}
    return fetch


def build_equity_universe(cfg: dict, now_utc=None, inbox_dir=None, *, fetch=None, held=None, base=None,
                          crypto_assets=()) -> tuple[list[dict], dict]:
    """(assets, report) for this run (module docstring). `fetch(symbols, start, now)` returns {SYM: bars or an
    exception} (default: the universe's feed, batched: yfinance_daily_cached or the Robinhood cache); `held` the
    sleeve's vehicles (default: universe.sleeve_vehicles); `crypto_assets` this run's crypto universe assets (their
    ETFs are not traded as stocks too, and their names are taken). Never raises for data problems."""
    now = cal.as_utc(now_utc)
    inbox = Path(inbox_dir) if inbox_dir is not None else paths(base)["inbox"]
    held = cu.sleeve_vehicles(base) if held is None else held
    st = _static(cfg, now, inbox, held, base, crypto_assets)
    if st is None:
        u = equity_universe(cfg)
        return [], dict(enabled=False, feed=u["feed"], generated_at=ledger.iso_z(now), tradability=None,
                        data_down=None, warnings=[], tickers=[], counts={})
    u, ents, pending, tr, report = st
    exp = cal.last_closed_equity_session(now)
    min_bars, min_dv = u["min_history_bars"], u["min_dollar_volume_usd"]
    syms = [e["ticker"] for e in pending]
    got = (fetch or _fetcher(u, inbox, base, report))(syms, _start(cfg, u, now), now) if syms else {}
    survivors = []
    for e in pending:
        bars = got.get(e["ticker"])
        if bars is None or isinstance(bars, Exception):
            why = str(bars) if isinstance(bars, Exception) else "no bars"
            if not _drop(e, f"data error ({why[:160]})", "data error"):
                survivors.append(e)
            continue
        bars = bars[bars.index <= pd.Timestamp(exp)]
        dv = feeds.median_dollar_volume(bars, cu.DV_BARS)
        e.update(bars=int(len(bars)), dollar_volume_usd=None if dv is None else round(dv, 2))
        last = bars.index[-1].date() if len(bars) else None
        if last != exp:
            if _drop(e, f"stale data (last bar {last or 'none'}, expected {exp})", "stale data"):
                continue
        elif dv is None or dv < min_dv:
            if _drop(e, f"illiquid (median ${dv or 0:,.0f}/day over the last {cu.DV_BARS} bars, need ${min_dv:,.0f})",
                     "illiquid"):
                continue
        if last == exp and len(bars) < min_bars:
            e["young"] = f"too little history ({len(bars)} bars, need {min_bars}): watch-only until it has enough"
        survivors.append(e)
    survivors.sort(key=lambda e: (-(e["dollar_volume_usd"] or 0.0), e["ticker"]))
    for k, e in enumerate(survivors, 1):
        e["rank"] = k
        if k > u["max_assets"] and not e["hold_only"]:
            _drop(e, f"beyond max_assets {u['max_assets']} (rank {k} of {len(survivors)} by dollar volume)",
                  "beyond max_assets")
    taken = {a["name"] for a in crypto_assets} | {str(a.get("name")) for a in cfg.get("assets", [])}
    kept = []
    for e in survivors:
        if e["outcome"] is not None:
            continue
        _vehicle(e, tr)
        if e["ticker"] in taken:
            name = e["ticker"] + STOCK_SUFFIX
            if name in taken:
                e.update(outcome="excluded", category="name collision", reason=(
                    f"the names {e['ticker']} and {name} are both taken (a coin and an explicit asset): rename the "
                    "explicit asset"))
                continue
            e["name"] = name
            e["reason"] += f"; named {name}: the crypto universe has the coin {e['ticker']}"
        kept.append(e)
    assets = [_asset(e, u) for e in kept]
    order = {"stock": 0, "watch": 1, "explicit": 2, "excluded": 3}
    report["tickers"] = [{k: e.get(k) for k in ("ticker", "name", "outcome", "reason", "category", "vehicle",
                                                "dollar_volume_usd", "bars", "rank", "held", "hold_only")}
                         for e in sorted(ents.values(), key=lambda e: (order.get(e["outcome"], 9), e["rank"] or 10**6,
                                                                       -(e["dollar_volume_usd"] or 0), e["ticker"]))]
    counts: dict[str, int] = {}
    for e in ents.values():
        key = e["outcome"] if e["outcome"] != "excluded" else f"excluded: {e['category']}"
        counts[key] = counts.get(key, 0) + 1
    report["counts"] = counts
    stamps = [tr[t]["captured_at"] for t in ents if t in tr]
    report["tradability"] = dict(captured_at=max(stamps) if stamps else None,
                                 confirmed=sum(1 for t in ents if (tr.get(t) or {}).get("ok")),
                                 fractional=sum(1 for e in kept if e["outcome"] == "stock"
                                                and e["vehicle"]["fractional"]))
    if report["data_down"]:
        report["warnings"].append(f"{report['data_down']}: tickers without current cached bars were not scanned")
    if (cfg.get("allocation") or {}).get("method") != "slots" and any(a["enabled"] for a in assets):
        report["warnings"].append("allocation.method is fixed: universe stocks have alloc_frac 0, so they are never "
                                  "bought; a held one is kept until its signal turns red (or FLATTEN), then sold; use "
                                  "allocation.method slots (README section 9)")
    return assets, report


def _vehicle(e: dict, tr: dict) -> None:
    """The vehicle (the ticker; fractional per the newest tradability capture) and the outcome (stock / watch)."""
    t = e["ticker"]
    tt = tr.get(t)
    frac = bool(tt and tt["ok"] and tt["fractional"])
    e["vehicle"] = {"type": "equity", "symbol": t, "fractional": frac}
    if e["held"]:
        if not (tt and tt["ok"]):
            why = tt["why"] if tt else \
                f"no get_equity_tradability capture in the last {cu.TRADABILITY_MAX_AGE_DAYS} days"
            e["hold_only"] = e["hold_only"] or f"{t} not confirmed tradable ({why}): exits only"
        if e.get("young"):                         # its exit signal runs on the bars it has (see _asset)
            e["hold_only"] = e["hold_only"] or f"{e['young'].split(':')[0]}; held, so kept for exits only"
        e.update(outcome="stock", reason="held by the sleeve")
    elif not tt:
        e.update(outcome="watch", reason=f"no get_equity_tradability capture for {t} in the last "
                                         f"{cu.TRADABILITY_MAX_AGE_DAYS} days: watch-only this run")
    elif e.get("young"):
        e.update(outcome="watch", reason=e["young"])
    else:
        e.update(outcome="stock", reason=f"tradable on the account ({tt['captured_at']}), "
                                         + ("fractional shares" if frac else "whole shares only"))
    if e["hold_only"]:
        e["reason"] += f"; hold only: {e['hold_only']}"


def _asset(e: dict, u: dict) -> dict:
    young = e.get("young") and (e["outcome"] == "watch" or e["held"])  # never bought: its signal on the bars it has
    a = {"name": e["name"], "class": "equity", "enabled": e["outcome"] == "stock", "alloc_frac": 0.0,
         "mode": u["mode"], "signal": {"source": "computed", "feed": u["feed"], "symbol": e["ticker"]},
         "vehicle": dict(e["vehicle"]), "min_bars": max(30, e["bars"] or 0) if young else u["min_history_bars"],
         "universe": {"kind": "equity", **{k: e.get(k) for k in ("outcome", "reason", "dollar_volume_usd", "rank",
                                                                 "held", "hold_only")}}}
    if u["entry"]:
        a["entry"] = dict(u["entry"])
    return a


# ------------------------------------------------------------------ for the planner, snapshot and fetch-list

def with_equity_universe(cfg: dict, signals: dict | None) -> tuple[dict, list[str]]:
    """The config plus the stock universe assets of the signals file, each re-checked against this config: its
    vehicle is the ticker, its name the ticker (or TICKER-STOCK) and unique, no explicit asset covers it, and its signal
    is universe.equity.feed on the ticker (either feed for a watch-only or hold-only one, which is never bought). With
    the universe off only hold-only assets are kept. Returns (config, warnings about ignored assets)."""
    gen = ((signals or {}).get("universe_equity") or {}).get("assets") or []
    if not gen:
        return cfg, []
    u = equity_universe(cfg)
    out, warnings, off = copy.deepcopy(cfg), [], 0
    claims, names = _claims(cfg), {str(a.get("name")) for a in cfg.get("assets", [])}
    for a in gen:
        a = a if isinstance(a, dict) else {}
        v, s = a.get("vehicle") or {}, a.get("signal") or {}
        t, name = str(v.get("symbol") or "").upper(), str(a.get("name") or "")
        hold_only = bool((a.get("universe") or {}).get("hold_only"))
        never_bought = hold_only or a.get("enabled") is not True
        if not u["enabled"] and not hold_only:
            off += 1
            continue
        problem = None
        if not TICKER.match(t) or a.get("class") != "equity" or v.get("type") != "equity" or \
                name not in (t, t + STOCK_SUFFIX):
            problem = "not a stock of the universe"
        elif t in claims or name in names:
            problem = "an explicit asset covers it, or its name is taken"
        elif str(s.get("symbol") or "").upper() != t or (s.get("feed") != u["feed"] and not never_bought):
            problem = f"signal is not {u['feed']} {t}"
        if problem:
            warnings.append(f"universe stock {name or t or '?'} in the signals file does not match the config "
                            f"({problem}): ignored; re-run signals")
            continue
        b = {"name": name, "class": "equity", "enabled": a.get("enabled") is True, "alloc_frac": 0.0,
             "mode": u["mode"], "signal": {"source": "computed", "feed": s.get("feed"), "symbol": t},
             "vehicle": {"type": "equity", "symbol": t, "fractional": v.get("fractional") is True},
             "min_bars": u["min_history_bars"], "universe": dict(a.get("universe") or {})}
        if u["entry"]:
            b["entry"] = dict(u["entry"])
        out["assets"].append(b)
        names.add(name)
    if off:
        warnings.append(f"{off} universe stocks in the signals file are ignored: universe.equity is off (only the "
                        "tickers the sleeve holds are kept, for exits); re-run signals")
    return out, warnings


def tradability_stage1(cfg: dict, now_utc=None, inbox_dir=None, *, base=None) -> list[str]:
    """Universe tickers without a get_equity_tradability capture of the configured account in the last 7 days (the
    first run, or tickers just added) and not tried in the last STAGE1_RETRY_HOURS (a call that failed is asked again
    by the normal list, and those tickers are watch-only meanwhile): fetch-list asks for these first, then for
    fetch-list again."""
    u = equity_universe(cfg)
    if not u["enabled"]:
        return []
    now = cal.as_utc(now_utc)
    inbox = Path(inbox_dir) if inbox_dir is not None else paths(base)["inbox"]
    st = _static(cfg, now, inbox, cu.sleeve_vehicles(base), base)
    if st is None:
        return []
    _, ents, _, tr, _ = st
    caps, failed = cu.recent_attempts(inbox, "get_equity_tradability", now, base=base)
    if failed:                                     # a call failed without a capture: which tickers is unknown
        return []
    acct = str((cfg.get("account") or {}).get("account_number") or "").strip()
    tried = {str(x).upper().strip() for c in caps if str(c["input"].get("account_number") or "").strip() == acct
             for x in c["input"].get("symbols") or [] if isinstance(x, str)}
    return [t for t in _ask(ents) if t not in tr and t not in tried]


def _ask(ents: dict) -> list[str]:
    """Tickers fetch-list checks with get_equity_tradability: every candidate an explicit asset, the crypto universe
    or universe.equity.exclude does not take out."""
    return sorted(t for t, e in ents.items() if e["outcome"] != "explicit" and e["category"] not in
                  ("covered by the crypto universe", "excluded by config"))


def fetch_needs(cfg: dict, now_utc=None, inbox_dir=None, *, base=None, build=None, crypto_assets=()) -> dict:
    """What fetch-list adds for the stock universe: {tradability, historicals {SYM: start date}, equity_quotes,
    candidates, report, scanned}. Quotes for every held universe stock and every one that is green and entry-eligible
    on today's signals (yfinance: computed here from the batched download); with the robinhood feed the bars come
    with this fetch, so every tradable or held ticker gets a quote."""
    from agentic import entry
    from agentic.signals import asset_signal
    empty = dict(tradability=[], historicals={}, equity_quotes=[], candidates=[], report=None, scanned=0)
    now = cal.as_utc(now_utc)
    inbox = Path(inbox_dir) if inbox_dir is not None else paths(base)["inbox"]
    held, caught = cu.sleeve_vehicles(base), cu.captured_holdings(inbox)
    held = {k: held[k] | caught[k] for k in held}
    st = _static(cfg, now, inbox, held, base, crypto_assets)
    if st is None:
        return empty
    u, ents, pending, tr, _ = st
    out = dict(empty, tradability=_ask(ents))
    if u["feed"] == "robinhood":
        start = _start(cfg, u, now)
        quotes = [e["ticker"] for e in pending if e["held"] or (tr.get(e["ticker"]) or {}).get("ok")]
        return dict(out, historicals={e["ticker"]: start for e in pending}, equity_quotes=sorted(quotes),
                    candidates=quotes, scanned=len(pending))
    assets, report = (build or build_equity_universe)(cfg, now, inbox, base=base, held=held,
                                                      crypto_assets=crypto_assets)
    recorded = entry.recorded_start(base) or ""
    eq, cands = set(), []
    for a in assets:
        vs = a["vehicle"]["symbol"]
        is_held = vs in held["equity"]
        if not a["enabled"] and not is_held:
            continue
        s = asset_signal(a, cfg, now, inbox, recorded, offline={"yfinance"})
        if not is_held and (s["errors"] or a["universe"].get("hold_only") or not (s.get("target_frac") or 0) > 0
                            or not (s.get("entry_frac") or 0) > 0):
            continue
        cands.append(a["name"])
        eq.add(vs)
    return dict(out, equity_quotes=sorted(eq), candidates=cands, report=report,
                scanned=sum(1 for a in assets))


def history_calls(starts: dict, now_utc=None, base=None, inbox_dir=None) -> list[dict]:
    """get_equity_historicals calls for the bars the Robinhood cache lacks, {SYM: start date} -> [{tool, params, why}].
    A symbol whose cache ends before the last closed session gets an incremental call from OVERLAP_SESSIONS sessions
    before its last cached bar (the overlap catches a split), grouped up to 10 symbols while symbols x expected bars
    stays within RH_MAX_BARS_PER_CALL (about RH_MAX_RESULT_CHARS characters); a symbol without cached history (or
    after a split, or with a hole) gets a backfill in windows of at most RH_BACKFILL_SESSIONS sessions, one symbol per
    call, the first one again from OVERLAP_SESSIONS sessions before the cached bars it joins. Each result stays well
    under Claude Code's 50,000-character limit. Captures in the inbox are merged into the cache first, so a window that
    came back without data is asked for again and nothing else is; one that came back too large is asked in smaller
    calls (one symbol each, then halves of its window)."""
    now = cal.as_utc(now_utc)
    exp = cal.last_closed_equity_session(now)
    if not starts:
        return []
    inbox = Path(inbox_dir) if inbox_dir is not None else paths(base)["inbox"]
    if inbox.is_dir():
        feeds.load_robinhood_bars(inbox, list(starts), now, [], cache_dir=feeds.robinhood_cache_dir(base))
    cov = feeds.robinhood_coverage(list(starts), base)
    inc, back = [], []
    for sym in sorted(starts):
        sessions = cal.trading_days(starts[sym], exp)
        ranges = cov.get(sym.upper()) or []
        missing = [d for d in sessions if not any(r[0] <= d.isoformat() <= r[1] for r in ranges)]
        runs: list[list] = []
        idx = {d: i for i, d in enumerate(sessions)}
        for d in missing:
            if runs and idx[d] == idx[runs[-1][-1]] + 1:
                runs[-1].append(d)
            else:
                runs.append([d])
        for run in runs:
            frm = run[0]
            joins = bool(ranges) and run[0] != sessions[0]      # cached bars right before it: overlap them
            if joins:
                for _ in range(feeds.OVERLAP_SESSIONS + 1):
                    frm = cal.previous_trading_day(frm)
            if joins and run[-1] == exp and len(run) <= RH_BACKFILL_SESSIONS:
                inc.append((frm, sym.upper(), len(cal.trading_days(frm, exp))))
            else:
                back.append((sym.upper(), run, frm))
    reqs, groups = [], []
    for frm, sym, n in sorted(inc):
        g = groups[-1] if groups else None
        if g and len(g["syms"]) < RH_MAX_SYMBOLS and (len(g["syms"]) + 1) * g["n"] <= RH_MAX_BARS_PER_CALL:
            g["syms"].append(sym)
        else:
            groups.append(dict(frm=frm, n=n, syms=[sym]))
    for g in groups:
        reqs.append((g["syms"], g["frm"], None, f"daily split-adjusted bars since the cached ones (a "
                                                  f"{feeds.OVERLAP_SESSIONS}-session overlap catches a split)"))
    for sym, run, frm in back:
        n = math.ceil(len(run) / RH_BACKFILL_SESSIONS)
        size = math.ceil(len(run) / n)
        chunks = [run[i:i + size] for i in range(0, len(run), size)]
        for k, ch in enumerate(chunks):
            end = None if k == len(chunks) - 1 and run[-1] == exp else cal.next_trading_day(ch[-1])
            reqs.append(([sym], frm if k == 0 else ch[0], end,
                         f"daily split-adjusted bars for {sym}: backfill window {k + 1}/{len(chunks)} (one symbol per "
                         "call keeps each result small)"))
    big = feeds.robinhood_too_large(inbox)
    calls = []
    while reqs:
        syms, frm, end, why = reqs.pop(0)
        if _at_least(big, syms, frm, end):
            days = cal.trading_days(frm, cal.previous_trading_day(end) if end else exp)
            again = "it came back too large for Claude Code last time"
            if len(syms) > 1:
                reqs[:0] = [([s], frm, end, f"daily split-adjusted bars for {s}, one symbol per call: {again}")
                            for s in syms]
                continue
            if len(days) >= 2 * RH_MIN_SPLIT_SESSIONS:
                mid = days[len(days) // 2]
                reqs[:0] = [(syms, frm, mid, f"daily split-adjusted bars for {syms[0]}, first half of a window: "
                                             f"{again}"),
                            (syms, mid, end, f"daily split-adjusted bars for {syms[0]}, second half of a window: "
                                             f"{again}")]
                continue
        calls.append(dict(tool="get_equity_historicals", params=_hist_params(syms, frm, end), why=why))
    return calls


def _at_least(big: set, syms, frm, end) -> bool:
    """Is this request at least as large as one that came back too large (its symbols and its whole window)?"""
    k = feeds.history_key(syms, frm.isoformat(), end.isoformat() if end else None)
    return any(b[0] and set(b[0]) <= set(k[0]) and b[1] and k[1] <= b[1]
               and (k[2] is None or (b[2] is not None and k[2] >= b[2])) for b in big)


def _hist_params(syms: list[str], start, end=None) -> dict:
    p = {"symbols": list(syms), "start_time": f"{start.isoformat()}T00:00:00Z"}
    if end is not None:
        p["end_time"] = f"{end.isoformat()}T00:00:00Z"
    p.update(interval="day", bounds="regular", adjustment_type="split")
    return p


# ------------------------------------------------------------------ cross-check

def crosscheck_problem(sym: str, quote: dict | None, bars: pd.DataFrame | None) -> str | None:
    """Why the cached yfinance close does not confirm Robinhood's raw previous_close on previous_close_date (within
    CROSSCHECK_TOL; split-adjusted bars equal raw prices on the latest bars unless a split came after them), or None."""
    if not quote:
        return f"no get_equity_quotes capture for {sym}"
    d, pc = quote.get("previous_close_date"), ledger.num(quote.get("previous_close"))
    if not d or not pc or pc <= 0:
        return f"the Robinhood quote for {sym} has no previous_close / previous_close_date"
    if bars is None or not len(bars):
        return f"no cached yfinance bars for {sym}"
    t = pd.Timestamp(str(d)[:10])
    if t not in bars.index:
        return f"no cached yfinance bar for {sym} on {str(d)[:10]} (Robinhood's previous_close_date; last cached bar " \
               f"{bars.index[-1].date()})"
    c = float(bars.loc[t, "close"])
    diff = c / pc - 1
    if abs(diff) > CROSSCHECK_TOL:
        return (f"yfinance close {c:.4f} for {sym} on {str(d)[:10]} differs from Robinhood's previous_close {pc:.4f} "
                f"by {diff:+.2%} (more than {CROSSCHECK_TOL:.1%}: a split or bad data)")
    return None


def _cached(sym: str, base=None):
    f = feeds.yfinance_cache_dir(base) / f"{sym.upper()}.csv"
    return feeds.read_bar_cache(f) if f.exists() else None


def cross_check(cfg: dict, snap: dict, base=None) -> dict[str, str | None]:
    """{asset name: problem or None} for every enabled asset config.crosscheck_applies to, from the snapshot's quotes
    and the yfinance cache. The planner blocks buys (never exits) of an asset with a problem or without an entry."""
    out = {}
    for a in cfg.get("assets", []):
        if a.get("enabled") and crosscheck_applies(a):
            sym = str(a["vehicle"]["symbol"]).upper()
            out[a["name"]] = crosscheck_problem(sym, (snap.get("quotes") or {}).get(sym), _cached(sym, base))
    return out


def latest_equity_quotes(inbox) -> dict[str, dict]:
    """The newest captured equity quote per symbol, any age (the cross-check compares by date)."""
    out: dict[str, dict] = {}
    for c in load_captures(inbox):
        if c["short"] == "get_equity_quotes" and not c["error"]:
            out.update(parse_equity_quotes(c["data"], c["at"]))
    return out


def signal_crosscheck(rec: dict, asset: dict, quotes: dict, base=None) -> None:
    """The digest's view of the cross-check (the plan checks again with the fresh quotes): rec["crosscheck"] is "ok",
    the problem, or why it was not checked; a problem is also a warning. A quote whose previous_close_date is before
    the last cached bar is not compared (a split since that date re-adjusts the bars, never Robinhood's raw close)."""
    sym = str(asset["vehicle"]["symbol"]).upper()
    q = quotes.get(sym)
    if q is None:
        rec["crosscheck"] = "not checked yet (no get_equity_quotes capture): the plan checks it"
        return
    bars = _cached(sym, base)
    pcd = str(q.get("previous_close_date") or "")[:10]
    if pcd and bars is not None and len(bars) and pcd < bars.index[-1].date().isoformat():
        rec["crosscheck"] = (f"not checked (the newest quote's previous_close_date {pcd} is before the last bar "
                             f"{bars.index[-1].date()}): the plan checks it with a fresh quote")
        return
    prob = crosscheck_problem(sym, q, bars)
    rec["crosscheck"] = prob or "ok"
    if prob:
        rec["warnings"].append(f"cross-check vs Robinhood: {prob}; the plan blocks buys (exits allowed)")


# ------------------------------------------------------------------ digest

def summary_lines(report: dict | None, full: bool = False) -> list[str]:
    """The digest's stock universe section: one summary line, warnings, watch-only and hold-only tickers; every
    ticker's outcome with `full`."""
    if not report or not (report.get("enabled") or report.get("tickers")):
        return []
    ts = report.get("tickers") or []
    c = report.get("counts") or {}
    tr = report.get("tradability") or {}
    src = (f"feed {report.get('feed')}" + (", off: held tickers only, kept for exits" if not report.get("enabled")
                                           else "")
           + (f", tradability captured {tr['captured_at']}" if tr.get("captured_at") else ", no tradability capture"))
    stock, watch = c.get("stock", 0), c.get("watch", 0)
    exc = ", ".join(f"{c[f'excluded: {k}']} {k}" for k in CATEGORIES if c.get(f"excluded: {k}"))
    frac = tr.get("fractional") or 0
    lines = [f"UNIVERSE stocks ({src}): {len(ts)} tickers considered, {stock + watch} scanned ({stock} tradable: "
             f"{frac} fractional, {stock - min(frac, stock)} whole shares only; {watch} watch-only)"
             + (f", {c['explicit']} covered by explicit assets" if c.get("explicit") else "")
             + (f"; excluded: {exc}" if exc else "")]
    for w in report.get("warnings") or []:
        lines.append(f"    WARNING: {w}")
    if full:
        for e in ts:
            dv = "-" if e.get("dollar_volume_usd") is None else f"${e['dollar_volume_usd'] / 1e6:,.1f}M"
            lines.append(f"    {e['name']:<12}{e['outcome']:<9}{dv:>10}  {e['reason']}")
        return lines
    for e in ts:
        if e["outcome"] == "watch" or e.get("hold_only") or e.get("category") in ("not found on Robinhood",
                                                                                  "name collision"):
            lines.append(f"    {e['name']}: {e['reason']}")
    return lines
