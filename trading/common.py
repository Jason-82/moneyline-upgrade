from __future__ import annotations

import hashlib
import json
import math
import os
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any


class TradingError(ValueError):
    """Fail-closed input, policy or state validation error."""


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


def stamp(value: str | datetime) -> datetime:
    out = value if isinstance(value, datetime) else datetime.fromisoformat(value.replace("Z", "+00:00"))
    if out.tzinfo is None:
        raise TradingError("Timestamp must include a timezone")
    return out.astimezone(timezone.utc)


def iso(value: str | datetime) -> str:
    return stamp(value).isoformat().replace("+00:00", "Z")


def number(value: Any, *, nonnegative: bool = True) -> Decimal:
    try:
        out = Decimal(str(value))
    except (InvalidOperation, TypeError) as exc:
        raise TradingError("Invalid decimal") from exc
    if not out.is_finite() or (nonnegative and out < 0):
        raise TradingError("Invalid decimal range")
    return out


def quantity(value: Any) -> int:
    out = number(value)
    if out != out.to_integral_value() or out <= 0:
        raise TradingError("Only positive whole-share quantities are supported")
    return int(out)


def symbol(value: str) -> str:
    import re
    if not isinstance(value, str) or not re.fullmatch(r"[A-Z][A-Z0-9.\-]{0,9}", value):
        raise TradingError("Invalid stock symbol")
    return value


def read_json(path: str | Path) -> dict:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def private_dir(path: str | Path) -> Path:
    out = Path(path)
    out.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(out, 0o700)
    return out


def private_json(path: str | Path, value: dict) -> None:
    out = Path(path)
    private_dir(out.parent)
    temporary = out.with_name(out.name + ".tmp")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, out)
    os.chmod(out, 0o600)
