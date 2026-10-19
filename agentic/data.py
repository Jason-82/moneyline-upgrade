"""Bar feeds for the signal job and the data checks that gate it.

Every feed returns a DataFrame indexed by naive, normalised dates (name 'date') with float open/high/low/close
(volume optional), ascending, one row per bar, closed bars only. Prices must be split-adjusted, not
dividend-adjusted (see analysis_2026/moneyline_ref.py).
"""
from __future__ import annotations

import glob as _glob
import json
import math
import os
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from agentic import calendar as cal
from agentic.config import DEFAULT_LIMITS, REPO, paths
from analysis_2026.moneyline_ref import atr, true_range
from screener.data import normalise

COINBASE_CANDLES = "https://api.exchange.coinbase.com/products/{product}/candles"
COINBASE_PRODUCTS = "https://api.exchange.coinbase.com/products"
USER_AGENT = "moneyline-agentic/1.0"
COINBASE_PAGE = 300
RETRIES = 3
BACKOFF_S = 1.0
TIMEOUT_S = 30.0
MAX_REQUESTS_PER_S = 5.0          # Coinbase's public limit is higher; stay polite
SETTLE = pd.Timedelta(minutes=5)  # a bar is cached once it closed at least this long before the fetch
OHLC = ["open", "high", "low", "close"]
SPLIT_RATIOS = (1 / 2, 1 / 3, 1 / 4, 1 / 5, 1 / 10, 2, 3, 4, 5, 10)


class DataError(ValueError):
    pass


def _day(x) -> pd.Timestamp:
    """Naive UTC midnight for a date / datetime / string."""
    t = pd.Timestamp(x)
    if t.tzinfo is not None:
        t = t.tz_convert("UTC").tz_localize(None)
    return t.normalize()


def _empty() -> pd.DataFrame:
    return pd.DataFrame(columns=OHLC, dtype=float, index=pd.DatetimeIndex([], name="date"))


# ------------------------------------------------------------------ Coinbase

def _get_json(url: str, opener, sleep, retries: int = RETRIES, timeout: float = TIMEOUT_S):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    for k in range(retries + 1):
        try:
            with opener(req, timeout=timeout) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if k == retries or not (e.code == 429 or 500 <= e.code < 600):
                raise
        except (urllib.error.URLError, TimeoutError):
            if k == retries:
                raise
        sleep(BACKOFF_S * 2 ** k)


class Pacer:
    """At most `rate` requests per second: call it before each request. `clock` / `sleep` default to time.monotonic
    and time.sleep (looked up at call time, so tests can patch them)."""

    def __init__(self, rate: float = MAX_REQUESTS_PER_S, clock=None, sleep=None):
        self.interval, self.clock, self.sleep, self.last = 1.0 / rate, clock, sleep, None

    def __call__(self) -> None:
        now = (self.clock or time.monotonic)()
        wait = 0.0 if self.last is None else self.last + self.interval - now
        if wait > 0:
            (self.sleep or time.sleep)(wait)
        self.last = now + max(wait, 0.0)


PACER = Pacer()                   # shared by every cached Coinbase request of this process


def fetch_coinbase_daily(product: str, start, end=None, opener=None, *, now_utc=None, sleep=time.sleep,
                         pace=None, retries: int = RETRIES, timeout: float = TIMEOUT_S) -> pd.DataFrame:
    """Daily candles (labelled by the 00:00 UTC open) from Coinbase Exchange's public API, paginated backwards in
    300-candle pages. The forming bar (date >= today UTC) is dropped. `opener` defaults to urllib.request.urlopen;
    `pace` (a Pacer) is called before each page; `retries` / `timeout` per request."""
    opener = opener or urllib.request.urlopen
    today = _day(cal.as_utc(now_utc))
    lo = _day(start)
    hi = min(_day(end) if end is not None else today, today)
    rows: list = []
    e = hi
    while e >= lo:
        s = max(lo, e - pd.Timedelta(days=COINBASE_PAGE - 1))   # <= 300 candles even with both ends inclusive
        q = urllib.parse.urlencode({"granularity": 86400, "start": s.strftime("%Y-%m-%dT%H:%M:%SZ"),
                                    "end": e.strftime("%Y-%m-%dT%H:%M:%SZ")})
        if pace is not None:
            pace()
        page = _get_json(f"{COINBASE_CANDLES.format(product=product)}?{q}", opener, sleep, retries, timeout)
        if not isinstance(page, list):
            raise DataError(f"coinbase {product}: unexpected response {str(page)[:200]}")
        if not page:
            break                                  # before the product's listing date
        rows.extend(page)
        if s <= lo:
            break
        e = s                                      # one candle of overlap, in case `end` is exclusive
    if not rows:
        return _empty()
    a = np.asarray([r[:6] for r in rows], dtype=float)
    df = pd.DataFrame({"open": a[:, 3], "high": a[:, 2], "low": a[:, 1], "close": a[:, 4], "volume": a[:, 5]},
                      index=pd.to_datetime(a[:, 0].astype("int64"), unit="s").normalize())
    df.index.name = "date"
    df = df[~df.index.duplicated(keep="first")].sort_index()
    return df[(df.index >= lo) & (df.index <= hi) & (df.index < today)]


# ------------------------------------------------------------------ Coinbase cache

def coinbase_cache_dir(base=None) -> Path:
    return paths(base)["cache"] / "coinbase"


def _write_atomic(f: Path, text: str) -> None:
    """A unique temp file in the same folder, then replace (retried on Windows), UTF-8 with '\n' line endings."""
    from agentic.ledger import replace_file
    f.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=f.parent, prefix=f".{f.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        replace_file(tmp, f)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _read_meta(d: Path) -> dict:
    try:
        m = json.loads((d / "meta.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return m if isinstance(m, dict) else {}


def read_coinbase_cache(f) -> pd.DataFrame | None:
    """Cached closed daily bars (date, open, high, low, close, volume), or None when the file is missing, unreadable
    or corrupt: NaN or non-positive prices, duplicate or unsorted dates."""
    try:
        raw = pd.read_csv(f, float_precision="round_trip")      # the floats exactly as fetched
        df = pd.DataFrame({c: pd.to_numeric(raw[c], errors="coerce") for c in OHLC + ["volume"]})
        df.index = pd.DatetimeIndex(pd.to_datetime(raw["date"], format="%Y-%m-%d", errors="raise"), name="date")
    except (OSError, ValueError, KeyError, pd.errors.ParserError):
        return None
    if df.empty or df[OHLC].isna().any().any() or (df[OHLC] <= 0).any().any() or df["volume"].isna().any() \
            or df.index.has_duplicates or not df.index.is_monotonic_increasing:
        return None
    return df.astype(float)


def missing_days(idx: pd.DatetimeIndex) -> int:
    """Calendar days absent between the first and the last bar."""
    return 0 if len(idx) < 2 else int((idx[-1] - idx[0]).days + 1 - len(idx))


def gap_dates(idx: pd.DatetimeIndex) -> list[str]:
    """The absent calendar days between the first and the last bar, as YYYY-MM-DD."""
    if len(idx) < 2:
        return []
    return [d.date().isoformat() for d in pd.date_range(idx[0], idx[-1], freq="D").difference(idx)]


def coinbase_daily_cached(product: str, start, now_utc=None, opener=None, *, base=None, pace=None,
                          sleep=time.sleep, issues: list | None = None, retries: int = RETRIES,
                          timeout: float = TIMEOUT_S, offline: bool = False) -> pd.DataFrame:
    """fetch_coinbase_daily through the cache <state>/cache/coinbase/<PRODUCT>.csv: only bars after the last cached
    closed bar are fetched (none when it is the last closed bar), and older history only when an earlier start is
    asked for than ever before. A corrupt cache is fetched again in full, and so is one with missing days (once per
    UTC day), unless those days were missing from Coinbase's own history at the last full fetch (Coinbase skips days
    without trades; meta.json keeps them). A bar is cached once it closed SETTLE before the fetch. `pace` defaults to
    the shared PACER (at most 5 requests per second). `offline`: no request at all, the cached bars as they are
    (DataError without a readable cache), for a run that already found Coinbase unreachable."""
    now = cal.as_utc(now_utc)
    pace = PACER if pace is None else pace
    note = issues.append if issues is not None else (lambda _m: None)
    d = coinbase_cache_dir(base)
    f = d / f"{product.upper()}.csv"
    meta = _read_meta(d)
    m = dict(meta.get(product.upper()) or {})
    today, lo = _day(now), _day(start)
    last_closed = today - pd.Timedelta(days=1)

    def get(s, e=None):
        return fetch_coinbase_daily(product, s, e, opener, now_utc=now, sleep=sleep, pace=pace, retries=retries,
                                    timeout=timeout)

    cached = read_coinbase_cache(f) if f.exists() else None
    if offline:
        if cached is None:
            raise DataError(f"{product}: no readable cache, and Coinbase was unreachable earlier in this run")
        return cached[(cached.index >= lo) & (cached.index < today)].astype(float)
    full = cached is None
    gaps = gap_dates(cached.index) if cached is not None else []
    if f.exists() and cached is None:
        note(f"{product}: cache {f.name} was unreadable or corrupt; fetched again")
    elif gaps and not set(gaps) <= set(m.get("gaps") or []) and m.get("full_fetch") != today.date().isoformat():
        note(f"{product}: cache has {len(gaps)} missing days; fetched again")
        full = True
    if full:
        df = get(lo)
        m.update(full_fetch=today.date().isoformat(), history_from=lo.date().isoformat())
        known = gap_dates(df[df.index < today].index)          # holes in Coinbase's own history: not refetched
        if known:
            m["gaps"] = known
        else:
            m.pop("gaps", None)
    else:
        parts = [cached]
        asked = pd.Timestamp(m.get("history_from") or cached.index[0])
        if lo < min(asked, cached.index[0]):
            parts.insert(0, get(lo, cached.index[0] - pd.Timedelta(days=1)))
            m["history_from"] = lo.date().isoformat()
        if cached.index[-1] < last_closed:
            parts.append(get(cached.index[-1] + pd.Timedelta(days=1)))
        parts = [x for x in parts if len(x)]
        df = pd.concat(parts) if len(parts) > 1 else parts[0]
        df = df[~df.index.duplicated(keep="last")].sort_index()
    df = df[df.index < today]
    keep = df[df.index + pd.Timedelta(days=1) + SETTLE <= pd.Timestamp(now).tz_convert(None)]
    if len(keep) and (cached is None or len(keep) != len(cached) or keep.index[-1] != cached.index[-1]
                      or keep.index[0] != cached.index[0]):
        cols = keep.reindex(columns=OHLC + ["volume"])
        cols["volume"] = cols["volume"].fillna(0.0)
        _write_atomic(f, cols.to_csv(index_label="date", date_format="%Y-%m-%d"))
    if m != (meta.get(product.upper()) or {}):
        meta[product.upper()] = m
        _write_atomic(d / "meta.json", json.dumps(meta, indent=1, sort_keys=True))
    return df[df.index >= lo].astype(float)


def coinbase_products(now_utc=None, opener=None, *, base=None, pace=None, sleep=time.sleep, retries: int = RETRIES,
                      timeout: float = TIMEOUT_S) -> dict:
    """Coinbase Exchange products (GET /products), cached for the UTC day in <state>/cache/coinbase/products.json:
    {products: {ID: {base, quote, online}}, fetched_at, error}. A failed fetch falls back to an older cache (with
    `error` set); `products` is None when there is neither."""
    now = cal.as_utc(now_utc)
    f = coinbase_cache_dir(base) / "products.json"
    try:
        old = json.loads(f.read_text(encoding="utf-8"))
        if not isinstance(old, dict) or not isinstance(old.get("products"), dict):
            old = None
    except (OSError, ValueError):
        old = None
    if old and str(old.get("fetched_at", ""))[:10] == now.date().isoformat():
        return dict(old, error=None)
    try:
        (PACER if pace is None else pace)()
        rows = _get_json(COINBASE_PRODUCTS, opener or urllib.request.urlopen, sleep, retries, timeout)
        if not isinstance(rows, list):
            raise DataError(f"unexpected response {str(rows)[:120]}")
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        err = f"Coinbase product list: {type(exc).__name__}: {exc}"
        return dict(old, error=err) if old else dict(products=None, fetched_at=None, error=err)
    prods = {}
    for r in rows:
        if isinstance(r, dict) and r.get("id"):
            prods[str(r["id"]).upper()] = dict(
                base=str(r.get("base_currency") or "").upper(), quote=str(r.get("quote_currency") or "").upper(),
                online=str(r.get("status") or "online").lower() == "online" and not r.get("trading_disabled"))
    out = dict(products=prods, fetched_at=now.strftime("%Y-%m-%dT%H:%M:%SZ"))
    _write_atomic(f, json.dumps(out, sort_keys=True))
    return dict(out, error=None)


def median_dollar_volume(df: pd.DataFrame, n: int = 30) -> float | None:
    """Median close x volume over the last `n` bars (Coinbase volume is in coin units), or None without volume."""
    if df is None or "volume" not in df.columns or not len(df):
        return None
    t = df.iloc[-n:]
    v = (pd.to_numeric(t["close"], errors="coerce") * pd.to_numeric(t["volume"], errors="coerce")).dropna()
    return float(v.median()) if len(v) else None


# ------------------------------------------------------------------ Robinhood inbox

def unwrap_mcp(response):
    """The structured tool result from a saved MCP response: the object itself, {"structuredContent": {...}},
    {"content": [{"type": "text", "text": "<json>"}]}, a bare content list, or a JSON string."""
    r = response
    if isinstance(r, str):
        r = json.loads(r)
    if isinstance(r, dict) and r.get("isError"):
        raise ValueError("the tool returned an error")
    if isinstance(r, dict) and isinstance(r.get("structuredContent"), (dict, list)):
        return r["structuredContent"]
    content = r.get("content") if isinstance(r, dict) else r if isinstance(r, list) else None
    if isinstance(content, list) and content and all(isinstance(c, dict) and "type" in c for c in content):
        texts = [c.get("text", "") for c in content if c.get("type") == "text"]
        if not texts:
            raise ValueError("MCP content has no text block")
        return json.loads("".join(texts))
    return r


def _rh_items(raw) -> list[dict]:
    """The per-symbol entries of a get_equity_historicals result (screener.data.from_robinhood_json shapes)."""
    if isinstance(raw, dict) and isinstance(raw.get("data"), (dict, list)):
        raw = raw["data"]
    if isinstance(raw, dict) and raw.get("symbol") and isinstance(raw.get("historicals") or raw.get("bars"), list):
        items = [raw]
    elif isinstance(raw, dict):
        items = raw.get("results") or raw.get("historicals") or {
            k: v for k, v in raw.items() if isinstance(v, list) and k not in ("not_found", "results", "historicals")}
    else:
        items = raw
    if isinstance(items, dict):
        items = [{"symbol": k, "bars": v} for k, v in items.items() if isinstance(v, list)]
    if not isinstance(items, list):
        raise ValueError("unrecognised get_equity_historicals shape")
    if items and all(isinstance(it, dict) and "begins_at" in it for it in items):      # flat bars
        grouped: dict[str, list] = {}
        for b in items:
            grouped.setdefault(str(b.get("symbol", "")).upper(), []).append(b)
        items = [{"symbol": k, "bars": v} for k, v in grouped.items()]
    return [it for it in items if isinstance(it, dict)]


def _truthy(v) -> bool:
    return v is True or str(v).strip().lower() in ("true", "1")


def _parse_capture_time(ts):
    try:
        t = pd.Timestamp(ts)
    except (ValueError, TypeError):
        return None
    if pd.isna(t):
        return None
    return (t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")).to_pydatetime()


def _with_bar_dates(bars: pd.DataFrame) -> pd.DataFrame:
    """A 'date' column from begins_at: the UTC date for a 00:00Z stamp, else the New York date (handles '-04:00' /
    '-05:00' offsets across a DST change, which pandas 3 refuses to mix)."""
    if "begins_at" not in bars.columns:
        return bars
    t = pd.to_datetime(bars["begins_at"].astype(str), utc=True, format="ISO8601", errors="coerce")
    midnight = (t == t.dt.normalize())
    ny = t.dt.tz_convert("America/New_York").dt.tz_localize(None).dt.normalize()
    utc = t.dt.tz_localize(None).dt.normalize()
    out = bars.drop(columns=["begins_at"])
    out["date"] = utc.where(midnight, ny).dt.strftime("%Y-%m-%d")
    return out


def load_robinhood_bars(inbox_dir, symbols=None, now_utc=None, issues: list | None = None) -> dict[str, pd.DataFrame]:
    """Daily bars per symbol from saved get_equity_historicals captures (SPEC section 8).

    Captures are merged in captured_at order and the newest capture's bar wins; an older capture whose overlapping
    closes differ by more than 1% (a split since) is ignored. Only interval 'day', regular bounds and split-adjusted
    requests are used. Interpolated bars and bars after the last closed session are dropped, judged at both now and the
    capture's captured_at (a capture taken mid-session holds that session's bar half-formed). Reasons for skipped
    captures are appended to `issues` if given."""
    note = issues.append if issues is not None else (lambda _m: None)
    want = {s.upper() for s in symbols} if symbols else None
    now = cal.as_utc(now_utc)
    asof = pd.Timestamp(cal.last_closed_equity_session(now))
    caps = []
    for f in sorted(Path(inbox_dir).glob("*get_equity_historicals*.json")):
        try:
            cap = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            note(f"{f.name}: unreadable capture ({exc.__class__.__name__})")
            continue
        if isinstance(cap, dict) and str(cap.get("tool", "")).endswith("get_equity_historicals"):
            caps.append((str(cap.get("captured_at", "")), f.name, cap))
    parts: dict[str, list[tuple[str, pd.DataFrame]]] = {}
    for ts, name, cap in sorted(caps, key=lambda c: (c[0], c[1])):
        at = _parse_capture_time(ts)
        cap_asof = None if at is None else min(asof, pd.Timestamp(cal.last_closed_equity_session(min(at, now))))
        adj = str((cap.get("tool_input") or {}).get("adjustment_type") or "split").lower()
        if adj != "split":
            note(f"{name}: adjustment_type '{adj}' - request adjustment_type='split'")
            continue
        try:
            items = _rh_items(unwrap_mcp(cap.get("response")))
        except (ValueError, TypeError, AttributeError) as exc:
            note(f"{name}: {exc}")
            continue
        for it in items:
            sym = str(it.get("symbol") or "").upper()
            if not sym or (want is not None and sym not in want):
                continue
            interval = str(it.get("interval") or "day").lower()
            if interval not in ("day", "1d", "daily"):
                note(f"{name} {sym}: interval '{interval}' is not daily - request interval='day'")
                continue
            bounds = str(it.get("bounds") or "regular").lower()
            if bounds != "regular":
                note(f"{name} {sym}: bounds '{bounds}' - request regular-hours bars")
                continue
            bars = [b for b in (it.get("bars") or it.get("historicals") or []) if isinstance(b, dict)]
            bars = [b for b in bars if not _truthy(b.get("interpolated", False))]
            if not bars:
                continue
            try:
                df = normalise(_with_bar_dates(pd.DataFrame(bars)))
            except (ValueError, TypeError) as exc:
                note(f"{name} {sym}: {exc}")
                continue
            if cap_asof is None:                   # unknown capture time: its last bar may have been forming
                df = df.iloc[:-1]
                note(f"{name} {sym}: no readable captured_at; its last bar is dropped")
            else:
                df = df[df.index <= cap_asof]
            parts.setdefault(sym, []).append((name, df))
    out = {}
    for sym, dfs in parts.items():
        merged = None
        for name, df in reversed(dfs):             # newest capture first
            if merged is None:
                merged = df
                continue
            common = df.index.intersection(merged.index)
            if len(common) and (df.close[common] / merged.close[common] - 1).abs().max() > 0.01:
                note(f"{name} {sym}: closes differ from a newer capture (split or adjustment change); ignored")
                continue
            merged = pd.concat([merged, df[~df.index.isin(merged.index)]]).sort_index()
        if len(merged):
            out[sym] = merged.astype(float)
    return out


# ------------------------------------------------------------------ yfinance, CSV

def fetch_yfinance(symbol: str, start, now_utc=None, asset_class: str = "equity") -> pd.DataFrame:
    """Split-adjusted OHLC from yfinance (auto_adjust=False; 'Adj Close' is never used). Optional dependency.
    Bars after the last closed bar of `asset_class` are dropped (crypto: the UTC day; stocks: the NYSE session)."""
    try:
        import yfinance as yf
    except ImportError as exc:
        raise DataError("yfinance is not installed (pip install yfinance)") from exc
    raw = yf.download(symbol, start=str(_day(start).date()), auto_adjust=False, actions=False, progress=False)
    if raw is None or len(raw) == 0:
        raise DataError(f"yfinance returned no rows for {symbol}")
    if isinstance(raw.columns, pd.MultiIndex):
        lvl = next((i for i in range(raw.columns.nlevels) if symbol in raw.columns.get_level_values(i)), None)
        if lvl is None:
            raise DataError(f"yfinance frame has no {symbol} columns")
        raw = raw.xs(symbol, axis=1, level=lvl)
    raw = raw.loc[:, [c for c in raw.columns if str(c).strip().lower() != "adj close"]]
    df = normalise(raw)
    last = cal.last_closed_crypto_bar(now_utc) if asset_class == "crypto" else cal.last_closed_equity_session(now_utc)
    return df[df.index <= pd.Timestamp(last)]


def load_csv(path) -> pd.DataFrame:
    """A local OHLC CSV (TradingView candle export, etc.). A glob picks the newest match by mtime."""
    p = Path(path)
    if not p.is_absolute():
        p = REPO / p
    if any(ch in str(p) for ch in "*?["):
        hits = sorted(_glob.glob(str(p)), key=lambda x: Path(x).stat().st_mtime)
        if not hits:
            raise DataError(f"no CSV matches {path}")
        p = Path(hits[-1])
    df = normalise(pd.read_csv(p))
    df.attrs["path"] = str(p)
    return df


# ------------------------------------------------------------------ dispatch

def history_days(asset: dict, cfg: dict) -> int:
    """Calendar days of history to request: >= min_bars + 150 bars (crypto at least ~2 years, stocks >= 700 days)."""
    n = max(int(cfg.get("limits", {}).get("min_bars", DEFAULT_LIMITS["min_bars"])),
            int(asset.get("min_bars") or 0)) + 150          # a universe asset may need more (min_history_bars)
    if asset.get("class") == "crypto" and asset["signal"].get("feed") == "coinbase":
        return max(n, 730)
    return max(math.ceil(n * 7 / 5) + 30, 700)


def get_bars(asset: dict, cfg: dict, now_utc=None, inbox_dir=None, offline: bool = False) -> pd.DataFrame:
    """Closed daily bars for an asset's signal feed. Raises DataError when the feed yields nothing. `offline`:
    Coinbase from the cache only (coinbase_daily_cached)."""
    s = asset["signal"]
    feed, sym = s.get("feed"), s.get("symbol")
    now = cal.as_utc(now_utc)
    start = now.date() - timedelta(days=history_days(asset, cfg))
    if feed == "coinbase":
        df = coinbase_daily_cached(sym, start, now, offline=offline)
    elif feed == "robinhood":
        issues: list[str] = []
        got = load_robinhood_bars(inbox_dir or paths()["inbox"], [sym], now, issues)
        if sym.upper() not in got:
            why = "; ".join(issues[-3:]) or "no get_equity_historicals capture in the inbox"
            raise DataError(f"{asset['name']}: no Robinhood daily bars for {sym} ({why}); run fetch-list")
        df = got[sym.upper()]
    elif feed == "yfinance":
        df = fetch_yfinance(sym, start, now, asset.get("class", "equity"))
    elif feed == "csv":
        if not s.get("path"):
            raise DataError(f"{asset['name']}: csv feed needs signal.path")
        df = load_csv(s["path"])
    else:
        raise DataError(f"{asset['name']}: unknown feed {feed!r}")
    if df.empty:
        raise DataError(f"{asset['name']}: feed {feed} returned no bars")
    return df


# ------------------------------------------------------------------ checks

def check_bars(df: pd.DataFrame, expected_last, min_bars: int, asset_class: str = "equity") -> dict:
    """Data checks before a signal is trusted. Errors block the asset; warnings go to the digest.
    `asset_class` ('equity' or 'crypto') sets the gap tolerance."""
    errors: list[str] = []
    warnings: list[str] = []
    if df is None or len(df) == 0:
        return dict(errors=["no bars"], warnings=warnings)
    cols = {str(c).lower(): c for c in df.columns}
    missing = [c for c in OHLC if c not in cols]
    if missing:
        return dict(errors=[f"missing columns {missing}"], warnings=warnings)
    d = pd.DataFrame({c: pd.to_numeric(df[cols[c]], errors="coerce") for c in OHLC}, index=pd.DatetimeIndex(df.index))
    idx = d.index
    exp = _day(expected_last).date()
    last = idx[-1].date()
    if last != exp:
        errors.append(f"last bar is {last}, expected {exp}")
    if len(d) < min_bars:
        errors.append(f"only {len(d)} bars, need {min_bars}")
    bad = d.isna().any(axis=1) | (d <= 0).any(axis=1)
    if bad.any():
        errors.append(f"{int(bad.sum())} bars with NaN or non-positive prices (first {idx[bad.to_numpy()][0].date()})")
    top, bot = d[["open", "close"]].max(axis=1), d[["open", "close"]].min(axis=1)
    hl = (d.high < top * (1 - 1e-9)) | (d.low > bot * (1 + 1e-9))
    if hl.any():
        errors.append(f"{int(hl.sum())} bars with high/low outside open/close (first {idx[hl.to_numpy()][0].date()})")
    if idx.has_duplicates:
        errors.append(f"duplicate dates: {sorted({str(x.date()) for x in idx[idx.duplicated()]})[:5]}")
    if not idx.is_monotonic_increasing:
        errors.append("dates are not ascending")
    tail = d.iloc[-301:]
    ratio = (tail.close / tail.close.shift(1)).iloc[1:]
    for t, r in ratio.items():
        hit = next((k for k in SPLIT_RATIOS if abs(r / k - 1) <= 0.03), None) if np.isfinite(r) else None
        if hit is not None:
            errors.append(f"{t.date()}: close ratio {r:.3f} is near {hit:.3g} (missed split? use split-adjusted data)")

    h, lo, c = (d[x].to_numpy(dtype=float) for x in ("high", "low", "close"))
    if len(d) >= 11 and np.isfinite(h).all() and np.isfinite(lo).all() and np.isfinite(c).all():
        prior = atr(h[:-1], lo[:-1], c[:-1], 10)[-1]
        tr = true_range(h, lo, c)[-1]
        if np.isfinite(prior) and prior > 0 and tr > 4 * prior:
            warnings.append(f"{last}: true range {tr:.6g} is {tr / prior:.1f}x the prior ATR10 "
                            "(big wick: check TradingView before approving)")
    max_gap = 1 if asset_class == "crypto" else 5
    gaps = pd.Series(idx[-300:]).diff().dt.days
    for i in np.flatnonzero(gaps.to_numpy() > max_gap):
        warnings.append(f"gap of {int(gaps.iloc[i])} days before {idx[-300:][i].date()}")
    return dict(errors=errors, warnings=warnings)
