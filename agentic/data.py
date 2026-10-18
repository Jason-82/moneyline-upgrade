"""Bar feeds for the signal job and the data checks that gate it.

Every feed returns a DataFrame indexed by naive, normalised dates (name 'date') with float open/high/low/close
(volume optional), ascending, one row per bar, closed bars only. Prices must be split-adjusted, not
dividend-adjusted (see analysis_2026/moneyline_ref.py).
"""
from __future__ import annotations

import glob as _glob
import json
import math
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
USER_AGENT = "moneyline-agentic/1.0"
COINBASE_PAGE = 300
RETRIES = 3
BACKOFF_S = 1.0
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

def _get_json(url: str, opener, sleep, retries: int = RETRIES):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    for k in range(retries + 1):
        try:
            with opener(req, timeout=30) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if k == retries or not (e.code == 429 or 500 <= e.code < 600):
                raise
        except (urllib.error.URLError, TimeoutError):
            if k == retries:
                raise
        sleep(BACKOFF_S * 2 ** k)


def fetch_coinbase_daily(product: str, start, end=None, opener=None, *, now_utc=None, sleep=time.sleep) -> pd.DataFrame:
    """Daily candles (labelled by the 00:00 UTC open) from Coinbase Exchange's public API, paginated backwards in
    300-candle pages. The forming bar (date >= today UTC) is dropped. `opener` defaults to urllib.request.urlopen."""
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
        page = _get_json(f"{COINBASE_CANDLES.format(product=product)}?{q}", opener, sleep)
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
    n = int(cfg.get("limits", {}).get("min_bars", DEFAULT_LIMITS["min_bars"])) + 150
    if asset.get("class") == "crypto" and asset["signal"].get("feed") == "coinbase":
        return max(n, 730)
    return max(math.ceil(n * 7 / 5) + 30, 700)


def get_bars(asset: dict, cfg: dict, now_utc=None, inbox_dir=None) -> pd.DataFrame:
    """Closed daily bars for an asset's signal feed. Raises DataError when the feed yields nothing."""
    s = asset["signal"]
    feed, sym = s.get("feed"), s.get("symbol")
    now = cal.as_utc(now_utc)
    start = now.date() - timedelta(days=history_days(asset, cfg))
    if feed == "coinbase":
        df = fetch_coinbase_daily(sym, start, now_utc=now)
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
