"""Configuration and state paths. Standard library only: the Claude Code hooks import this module.

The real config lives at <state>/config.json (default state dir: <repo>/private/agentic, gitignored; override with the
AGENTIC_STATE_DIR environment variable). agentic/config.example.json is the committed template
(`.venv/Scripts/python.exe -m agentic init` copies it). The config holds account numbers, so it must never be committed.
"""
from __future__ import annotations

import copy
import json
import math
import os
import re
import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
EXAMPLE = Path(__file__).resolve().parent / "config.example.json"

DEFAULT_MODES = {
    "immediate": [{"weight": 1.0, "n_entry": 1, "n_exit": 1}],
    "split": [{"weight": 0.5, "n_entry": 1, "n_exit": 1}, {"weight": 0.5, "n_entry": 5, "n_exit": 5}],
    "confirm5": [{"weight": 1.0, "n_entry": 5, "n_exit": 5}],
}

DEFAULT_LIMITS = {
    "max_order_usd": 500.0,          # per order notional cap
    "max_day_usd": 1500.0,           # placed notional per calendar day (ET), buys and sells
    "max_asset_frac": 0.30,          # of capital, per asset
    "max_crypto_frac": 0.60,         # of capital, all crypto-signal assets together (they flip red together)
    "min_order_usd": 5.0,            # skip smaller trades
    "rebalance_band_frac": 0.25,     # trade only if |target - current| > band x the asset's full allocation
    "equity_collar_frac": 0.005,     # limit = ask x (1 + collar) for buys, bid x (1 - collar) for sells
    "crypto_collar_frac": 0.01,
    "collar_ladder": [1, 2, 4],      # multipliers for plan --attempt 1/2/3
    "max_collar_frac": 0.03,
    "quote_max_age_min": 15,         # captured quotes older than this cannot be used for a plan
    "snapshot_max_age_min": 30,      # positions / portfolio / open orders captures
    "plan_valid_min_crypto": 360,    # crypto plans expire after 6 h
    "min_bars": 300,                 # history needed before a signal is trusted
}

VALID_CLASSES = ("crypto", "equity")
VALID_SOURCES = ("computed", "tv_export")
VALID_FEEDS = ("coinbase", "robinhood", "yfinance", "csv")
VALID_VEHICLES = ("crypto", "equity")
ENTRY_POLICIES = ("join", "join_recent", "fresh_only")
ALLOC_METHODS = ("fixed", "slots")
PRIORITIES = ("crypto_first", "equity_first", "newest_flip", "config_order")

# Joining a green run that started before we act (HANDOFF 5.4). Global block; an asset may override any key.
# max_join_rise_frac 0.50: no new buy once the close is more than 50% above the flip close (README section 9,
# analysis_2026/results_late_entry); null turns the cap off.
DEFAULT_ENTRY = {"policy": "join_recent", "max_join_bars": 20, "max_join_rise_frac": 0.50, "start_date": None}
# "fixed" (per-asset alloc_frac) when the block is absent, so older configs keep their sizing.
DEFAULT_ALLOCATION = {"method": "fixed", "slot_frac": 0.20, "priority": "crypto_first"}

# Crypto universe (README section 10): every coin Robinhood offers, filtered, each traded through its US spot ETF
# where one is mapped and confirmed tradable on the account, else directly. Off when the block is absent.
# Stablecoins and wrapped / pegged tokens have no trend to follow (universe.py also drops any coin whose last 90
# closes stay within 3% of their median, so an unlisted stablecoin is caught too).
DEFAULT_EXCLUDE = ("USDC", "USDT", "DAI", "PYUSD", "USDP", "TUSD", "GUSD", "FDUSD", "USDS", "EURC",
                   "WBTC", "WETH", "CBBTC", "CBETH", "STETH", "PAXG", "XAUT")
DEFAULT_ETF_MAP = {"BTC": "IBIT", "ETH": "ETHA", "SOL": "BSOL", "XRP": "XRPC", "LTC": "LTCC", "NEAR": "NRR"}
UNIVERSE_SOURCES = ("robinhood", "list")
# min_dollar_volume_usd: median daily close x volume on Coinbase over the last 30 closed bars. max_assets 30: the
# MoneyLine's crypto edge was measured on the top-20 basket incl. dead coins; small coins lost money even with the
# signal in 2022-25 (HANDOFF 5.11). min_history_bars None = limits.min_bars.
DEFAULT_UNIVERSE_CRYPTO = {"enabled": False, "source": "robinhood", "symbols": [], "exclude": list(DEFAULT_EXCLUDE),
                           "mode": "split", "entry": None, "min_history_bars": None,
                           "min_dollar_volume_usd": 5_000_000, "max_assets": 30, "etf_map": dict(DEFAULT_ETF_MAP),
                           "prefer_etf": True, "direct_crypto": True}
COIN_CODE = re.compile(r"^[A-Z0-9]{1,15}$")
TICKER = re.compile(r"^[A-Z][A-Z0-9.]{0,9}$")


class ConfigError(ValueError):
    pass


def cli_command() -> str:
    """The command that runs the CLI with the current interpreter, for messages to the user and to Claude (a Git Bash
    command on Windows, a POSIX shell command elsewhere, run from the repo root): the repo venv's interpreter as a
    relative path (`.venv/Scripts/python.exe -m agentic`), else on Windows this interpreter's path with forward
    slashes (`python3` there is often the Microsoft Store stub), else `python3 -m agentic`."""
    exe = Path(os.path.abspath(sys.executable or "python3"))
    try:
        return f"{exe.relative_to(REPO).as_posix()} -m agentic"
    except ValueError:
        pass
    if os.name == "nt" and sys.executable:
        p = exe.as_posix()
        return f'"{p}" -m agentic' if " " in p else f"{p} -m agentic"
    return "python3 -m agentic"


def state_dir() -> Path:
    """AGENTIC_STATE_DIR (a relative value resolves against the repo root, so the hooks and the CLI agree whatever
    their working directory) or <repo>/private/agentic."""
    env = os.environ.get("AGENTIC_STATE_DIR")
    if not env:
        return REPO / "private" / "agentic"
    p = Path(env).expanduser()
    return p if p.is_absolute() else (REPO / p).resolve()


def paths(base: Path | None = None) -> dict[str, Path]:
    b = Path(base) if base is not None else state_dir()
    return {
        "base": b,
        "config": b / "config.json",
        "inbox": b / "inbox",                # raw Robinhood MCP tool results, saved by the PostToolUse hook
        "signals": b / "signals",            # signals_<YYYY-MM-DD>.json
        "plans": b / "plans",                # plan_<plan_id>.json
        "plan_current": b / "plan_current.json",
        "digests": b / "digests",
        "journal": b / "journal.jsonl",      # every place/cancel/preview call and its result
        "ledger": b / "ledger.json",         # placed notional per day
        "positions_ref": b / "positions_reconciled.json",
        "hook_log": b / "hook.log",
        "STOP": b / "STOP",                  # kill switch: no new orders at all
        "FLATTEN": b / "FLATTEN",            # sells toward zero only
        "BLOCK_BUYS": b / "BLOCK_BUYS",      # set by reconcile/data checks; exits still allowed
        "strategy_start": b / "strategy_start.json",   # first live plan's date (entry policy fresh_only)
        "cache": b / "cache",                # public market data (Coinbase candles and product list)
    }


def ensure_dirs(base: Path | None = None) -> dict[str, Path]:
    p = paths(base)
    for k in ("base", "inbox", "signals", "plans", "digests"):
        p[k].mkdir(parents=True, exist_ok=True)
    return p


def _merge(default: dict, override: dict) -> dict:
    out = copy.deepcopy(default)
    for k, v in (override or {}).items():
        out[k] = v
    return out


def _bool(d: dict, key: str, default: bool, where: str) -> bool:
    """A JSON true/false (a quoted "false" would be truthy, so anything else is an error)."""
    v = d.get(key, default)
    if not isinstance(v, bool):
        raise ConfigError(f"{where}{key} must be true or false (JSON booleans, unquoted), not {v!r}")
    d[key] = v
    return v


def _sleeve_qty(v) -> dict:
    if not isinstance(v, dict):
        raise ConfigError("sleeve_initial_qty must be an object {VEHICLE_SYMBOL: quantity}")
    out = {}
    for k, q in v.items():
        if str(k).startswith("_"):
            continue
        try:
            f = float(q)
        except (TypeError, ValueError):
            f = float("nan")
        if isinstance(q, bool) or not (f >= 0 and f != float("inf")):
            raise ConfigError(f"sleeve_initial_qty.{k} must be a number >= 0")
        out[str(k).upper().strip()] = f
    return out


def _frac(v, where: str, lo: float = 0.0, lo_open: bool = True) -> float:
    """A JSON number in (lo, 1] (or [lo, 1] with lo_open=False)."""
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v > 1 or v < lo \
            or (lo_open and v == lo):
        raise ConfigError(f"{where} must be a number in {'(' if lo_open else '['}{lo:g}, 1], not {v!r}")
    return float(v)


def _entry(e, where: str, full: bool) -> dict:
    """Validate an entry block; `full` fills the defaults (the global block), else only the keys given (an asset's
    override)."""
    if not isinstance(e, dict):
        raise ConfigError(f"{where} must be an object like {json.dumps(DEFAULT_ENTRY)}")
    e = {k: v for k, v in e.items() if not str(k).startswith("_")}
    bad = sorted(set(e) - set(DEFAULT_ENTRY))
    if bad:
        raise ConfigError(f"{where}: unknown keys {bad}; allowed: {sorted(DEFAULT_ENTRY)}")
    out = {**DEFAULT_ENTRY, **e} if full else dict(e)
    if "policy" in out and out["policy"] not in ENTRY_POLICIES:
        raise ConfigError(f"{where}.policy must be one of {ENTRY_POLICIES}, not {out['policy']!r}")
    n = out.get("max_join_bars", 0)
    if isinstance(n, bool) or not isinstance(n, int) or n < 0:
        raise ConfigError(f"{where}.max_join_bars must be a whole number of bars >= 0, not {n!r}")
    r = out.get("max_join_rise_frac")
    if r is not None and (isinstance(r, bool) or not isinstance(r, (int, float)) or not math.isfinite(r) or r < 0):
        raise ConfigError(f"{where}.max_join_rise_frac must be null or a number >= 0 (0.10 = 10%), not {r!r}")
    d = out.get("start_date")
    if d is not None:
        try:
            ok = isinstance(d, str) and len(d) == 10 and date.fromisoformat(d).isoformat() == d
        except ValueError:
            ok = False
        if not ok:
            raise ConfigError(f"{where}.start_date must be null or an ISO date YYYY-MM-DD, not {d!r}")
    return out


def _allocation(a, limits: dict) -> dict:
    if not isinstance(a, dict):
        raise ConfigError("allocation must be an object like "
                          '{"method": "slots", "slot_frac": 0.20, "priority": "crypto_first"}')
    a = {k: v for k, v in a.items() if not str(k).startswith("_")}
    bad = sorted(set(a) - {*DEFAULT_ALLOCATION, "class_max_frac"})
    if bad:
        raise ConfigError(f"allocation: unknown keys {bad}")
    out = {**DEFAULT_ALLOCATION, **a}
    if out["method"] not in ALLOC_METHODS:
        raise ConfigError(f"allocation.method must be one of {ALLOC_METHODS}, not {out['method']!r}")
    if out["priority"] not in PRIORITIES:
        raise ConfigError(f"allocation.priority must be one of {PRIORITIES}, not {out['priority']!r}")
    out["slot_frac"] = _frac(out["slot_frac"], "allocation.slot_frac")
    if out["method"] == "slots" and out["slot_frac"] > float(limits["max_asset_frac"]) + 1e-12:
        raise ConfigError(f"allocation.slot_frac {out['slot_frac']:g} exceeds limits.max_asset_frac "
                          f"{limits['max_asset_frac']}")
    caps = a.get("class_max_frac")
    if caps is None:
        caps = {}
    if not isinstance(caps, dict):
        raise ConfigError('allocation.class_max_frac must be an object like {"crypto": 0.60, "equity": 1.0}')
    caps = {k: v for k, v in caps.items() if not str(k).startswith("_")}
    if set(caps) - set(VALID_CLASSES):
        raise ConfigError(f"allocation.class_max_frac: classes must be in {VALID_CLASSES}")
    if "crypto" not in caps:             # backward compatible: limits.max_crypto_frac, read as older configs had it
        try:                             # (a number or numeric string; above 1 = no cap)
            old = float(limits["max_crypto_frac"])
        except (TypeError, ValueError):
            old = float("nan")
        if not math.isfinite(old) or old < 0:
            raise ConfigError(f"limits.max_crypto_frac must be a number >= 0, not {limits['max_crypto_frac']!r}")
        caps["crypto"] = min(old, 1.0)
    out["class_max_frac"] = {k: _frac(caps.get(k, 1.0), f"allocation.class_max_frac.{k}", lo_open=False)
                             for k in VALID_CLASSES}
    return out


def _codes(v, where: str, pattern=COIN_CODE) -> list[str]:
    if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
        raise ConfigError(f"{where} must be a list of codes like [\"DOGE\", \"LINK\"]")
    out = []
    for x in v:
        k = x.strip().upper()
        if not pattern.match(k):
            raise ConfigError(f"{where}: {x!r} is not a coin code")
        if k not in out:
            out.append(k)
    return out


def _universe(u, c: dict) -> dict:
    """Validate the `universe` block; {"crypto": {...}} with every default filled (enabled false when absent)."""
    if u is None:
        u = {}
    if not isinstance(u, dict):
        raise ConfigError('universe must be an object like {"crypto": {"enabled": true}}')
    u = {k: v for k, v in u.items() if not str(k).startswith("_")}
    if set(u) - {"crypto"}:
        raise ConfigError(f"universe: unknown keys {sorted(set(u) - {'crypto'})}; only \"crypto\" exists")
    raw = u.get("crypto") or {}
    if not isinstance(raw, dict):
        raise ConfigError("universe.crypto must be an object")
    raw = {k: v for k, v in raw.items() if not str(k).startswith("_")}
    bad = sorted(set(raw) - set(DEFAULT_UNIVERSE_CRYPTO))
    if bad:
        raise ConfigError(f"universe.crypto: unknown keys {bad}; allowed: {sorted(DEFAULT_UNIVERSE_CRYPTO)}")
    w = "universe.crypto."
    out = {**copy.deepcopy(DEFAULT_UNIVERSE_CRYPTO), **raw}
    for k in ("enabled", "prefer_etf", "direct_crypto"):
        _bool(out, k, DEFAULT_UNIVERSE_CRYPTO[k], w)
    if out["source"] not in UNIVERSE_SOURCES:
        raise ConfigError(f"{w}source must be one of {UNIVERSE_SOURCES}, not {out['source']!r}")
    out["symbols"] = _codes(out["symbols"], w + "symbols")
    out["exclude"] = _codes(out["exclude"], w + "exclude")
    if out["mode"] not in c["modes"]:
        raise ConfigError(f"{w}mode: unknown mode {out['mode']!r}; defined: {sorted(c['modes'])}")
    if out["entry"] is not None:
        out["entry"] = _entry(out["entry"], w + "entry", full=False)
    n = out["min_history_bars"]
    if n is None:
        n = int(c["limits"]["min_bars"])
    if isinstance(n, bool) or not isinstance(n, int) or n < 30:
        raise ConfigError(f"{w}min_history_bars must be null (= limits.min_bars) or a whole number >= 30, not {n!r}")
    out["min_history_bars"] = n
    v = out["min_dollar_volume_usd"]
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0:
        raise ConfigError(f"{w}min_dollar_volume_usd must be a number >= 0, not {v!r}")
    out["min_dollar_volume_usd"] = float(v)
    m = out["max_assets"]
    if isinstance(m, bool) or not isinstance(m, int) or not 1 <= m <= 200:
        raise ConfigError(f"{w}max_assets must be a whole number from 1 to 200, not {m!r}")
    em = out["etf_map"]
    if not isinstance(em, dict):
        raise ConfigError(f'{w}etf_map must be an object like {{"BTC": "IBIT"}}')
    etfs: dict[str, str] = {}
    for coin, etf in em.items():
        if str(coin).startswith("_") or etf is None:         # null drops a mapping
            continue
        k = str(coin).strip().upper()
        t = str(etf).strip().upper() if isinstance(etf, str) else ""
        if not COIN_CODE.match(k) or not TICKER.match(t):
            raise ConfigError(f"{w}etf_map: {coin!r}: {etf!r} must map a coin code to an ETF ticker")
        if t in etfs.values():
            raise ConfigError(f"{w}etf_map: {t} is mapped to more than one coin")
        etfs[k] = t
    out["etf_map"] = etfs
    return {"crypto": out}


def validate(cfg: dict) -> dict:
    """Fill defaults and check the structure. Returns a new dict; raises ConfigError."""
    if not isinstance(cfg, dict):
        raise ConfigError("config must be a JSON object")
    c = copy.deepcopy(cfg)
    c["limits"] = _merge(DEFAULT_LIMITS, c.get("limits", {}))
    modes = _merge(DEFAULT_MODES, {k: v for k, v in c.get("modes", {}).items() if not k.startswith("_")})
    for name, tranches in modes.items():
        if not isinstance(tranches, list) or not tranches:
            raise ConfigError(f"mode {name}: needs a non-empty list of tranches")
        tot = 0.0
        for t in tranches:
            if not {"weight", "n_entry", "n_exit"} <= set(t):
                raise ConfigError(f"mode {name}: each tranche needs weight, n_entry, n_exit")
            if not (0 < float(t["weight"]) <= 1) or int(t["n_entry"]) < 1 or int(t["n_exit"]) < 1:
                raise ConfigError(f"mode {name}: weight in (0, 1], n_entry/n_exit >= 1")
            tot += float(t["weight"])
        if abs(tot - 1.0) > 1e-9:
            raise ConfigError(f"mode {name}: tranche weights must sum to 1 (got {tot})")
    c["modes"] = modes
    _bool(c, "live", False, "")
    acct = c.setdefault("account", {})
    _bool(acct, "approvals_required", True, "account.")
    c["sleeve_initial_qty"] = _sleeve_qty(c.get("sleeve_initial_qty") or {})
    c.setdefault("tax", {"st_rate": 0.35, "lt_rate": 0.20})
    c.setdefault("wash_sale_block_symbols", [])
    cap = c.setdefault("capital", {})
    if float(cap.get("max_usd", 0)) <= 0:
        raise ConfigError("capital.max_usd must be > 0 (the most this sleeve may deploy)")
    c["entry"] = _entry(c.get("entry", {}), "entry", full=True)
    c["allocation"] = _allocation(c.get("allocation", {}), c["limits"])
    c["universe"] = _universe(c.get("universe"), c)
    names = set()
    alloc = 0.0
    for a in c.get("assets", []):
        n = a.get("name")
        if not n or n in names:
            raise ConfigError(f"asset name missing or duplicated: {n!r}")
        names.add(n)
        if a.get("class") not in VALID_CLASSES:
            raise ConfigError(f"{n}: class must be one of {VALID_CLASSES}")
        if a.get("mode", "immediate") not in modes:
            raise ConfigError(f"{n}: unknown mode {a.get('mode')!r}; defined: {sorted(modes)}")
        a.setdefault("mode", "immediate")
        _bool(a, "enabled", False, f"{n}: ")
        s = a.get("signal") or {}
        if s.get("source", "computed") not in VALID_SOURCES:
            raise ConfigError(f"{n}: signal.source must be one of {VALID_SOURCES}")
        s.setdefault("source", "computed")
        if s["source"] == "computed" and s.get("feed") not in VALID_FEEDS:
            raise ConfigError(f"{n}: signal.feed must be one of {VALID_FEEDS}")
        if s["source"] == "tv_export" and not s.get("path"):
            raise ConfigError(f"{n}: tv_export needs signal.path (a glob of TradingView CSV exports)")
        if s["source"] == "tv_export" and a["mode"] not in ("immediate", "split", "confirm5"):
            raise ConfigError(f"{n}: tv_export supports modes immediate / split / confirm5 only")
        if not s.get("symbol") and s.get("feed") != "csv" and s["source"] == "computed":
            raise ConfigError(f"{n}: signal.symbol missing")
        a["signal"] = s
        v = a.get("vehicle") or {}
        if v.get("type") not in VALID_VEHICLES or not v.get("symbol"):
            raise ConfigError(f"{n}: vehicle needs type in {VALID_VEHICLES} and a symbol")
        _bool(v, "fractional", False, f"{n}: vehicle.")
        a["vehicle"] = v
        f = float(a.get("alloc_frac", 0))
        if not (0 <= f <= c["limits"]["max_asset_frac"] + 1e-12):
            raise ConfigError(f"{n}: alloc_frac must be within [0, max_asset_frac={c['limits']['max_asset_frac']}]")
        a["alloc_frac"] = f
        if "entry" in a:
            a["entry"] = _entry(a["entry"], f"{n}: entry", full=False)
        if a["enabled"]:
            alloc += f
    if alloc > 1.0 + 1e-9 and c["allocation"]["method"] == "fixed":
        raise ConfigError(f"enabled assets allocate {alloc:.2f} > 1.0 of capital (or use allocation.method slots)")
    return c


def load_config(path: str | Path | None = None) -> dict:
    p = Path(path) if path else paths()["config"]
    if not p.exists():
        raise ConfigError(f"no config at {p}; run `{cli_command()} init` and edit it")
    return validate(json.loads(p.read_text(encoding="utf-8-sig")))     # -sig: a "UTF-8 with BOM" file too


def crypto_universe(cfg: dict) -> dict:
    """The validated universe.crypto block (all defaults, enabled false, for a config that has none)."""
    u = (cfg.get("universe") or {}).get("crypto")
    return u if isinstance(u, dict) and "etf_map" in u else _universe(None, {"limits": DEFAULT_LIMITS,
                                                                                  "modes": DEFAULT_MODES})["crypto"]


def direct_crypto_possible(cfg: dict) -> bool:
    """An enabled asset trades a coin directly, or the crypto universe may (crypto captures are then required)."""
    u = crypto_universe(cfg)
    return any(a.get("enabled") and (a.get("vehicle") or {}).get("type") == "crypto" for a in cfg.get("assets", [])) \
        or (u["enabled"] and u["direct_crypto"])


def tranches_for(asset: dict, cfg: dict) -> list[dict]:
    return [dict(weight=float(t["weight"]), n_entry=int(t["n_entry"]), n_exit=int(t["n_exit"]))
            for t in cfg["modes"][asset["mode"]]]
